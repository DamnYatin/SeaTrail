"""
In-process background scheduler using APScheduler (single worker).
Runs periodic chain verification, checkpoint creation, and anomaly checks.
"""

from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db import get_db_session
from app.logging import logger
from app.models.alerts import AlertSeverity
from app.models.integrity import IntegrityState
from app.services import anomaly, audit_chain, checkpoints
from app.services.audit_chain import AuditAction, append

_scheduler: BackgroundScheduler | None = None


def run_scheduled_chain_check():
    """
    Scheduled chain verification job:
    Updates integrity_state table. Does NOT write audit entry if OK.
    Writes CHAIN_BROKEN and raises CRITICAL alert on failure.
    """
    with get_db_session() as session:
        res = audit_chain.verify_chain(session)
        now = datetime.now(UTC)

        state = session.query(IntegrityState).filter(IntegrityState.id == 1).first()
        if not state:
            state = IntegrityState(id=1)
            session.add(state)

        state.last_chain_check_at = now
        state.chain_ok = res.ok
        state.head_seq = res.head_seq
        state.broken_seq = res.first_broken_seq
        state.broken_reason = res.reason

        if not res.ok:
            audit_entry = append(
                session=session,
                actor=None,
                action=AuditAction.CHAIN_BROKEN,
                payload={
                    "first_broken_seq": res.first_broken_seq,
                    "reason": res.reason,
                    "head_seq": res.head_seq,
                },
            )
            anomaly.create_or_dedupe_alert(
                session=session,
                rule="CHAIN_BROKEN",
                severity=AlertSeverity.CRITICAL,
                explanation=f"Audit chain verification failure at seq #{res.first_broken_seq}: {res.reason}",
                details={"broken_seq": res.first_broken_seq, "reason": res.reason},
                audit_seqs=[audit_entry.seq],
                dedupe_key=f"CHAIN_BROKEN:{res.first_broken_seq}:{res.reason}",
            )


def run_scheduled_checkpoint():
    """Periodically create signed Ed25519 checkpoint."""
    with get_db_session() as session:
        checkpoints.create_checkpoint(session)


def run_scheduled_anomaly_sweep():
    """Periodically check for SLA overdue transfers and access bursts."""
    with get_db_session() as session:
        anomaly.check_missing_acknowledgements(session)
        anomaly.check_burst_access(session)
        anomaly.check_repeated_denied(session)


def start_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Chain check
    _scheduler.add_job(
        run_scheduled_chain_check,
        trigger=IntervalTrigger(minutes=settings.CHAIN_VERIFY_INTERVAL_MINUTES),
        id="chain_check",
        name="Scheduled Audit Chain Integrity Check",
        replace_existing=True,
    )

    # Checkpoints
    _scheduler.add_job(
        run_scheduled_checkpoint,
        trigger=IntervalTrigger(minutes=settings.CHECKPOINT_INTERVAL_MINUTES),
        id="checkpoints",
        name="Scheduled Cryptographic Checkpoint Creation",
        replace_existing=True,
    )

    # Anomaly checks
    _scheduler.add_job(
        run_scheduled_anomaly_sweep,
        trigger=IntervalTrigger(minutes=1),
        id="anomaly_sweep",
        name="Periodic Anomaly Rules Sweep",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("apscheduler_started")


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("apscheduler_shutdown")
