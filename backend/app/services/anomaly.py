"""
Explainable security anomaly rules and alerts engine.
No machine learning; strictly rule-based detection with proof links to audit sequences.
"""

import zoneinfo
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alerts import Alert, AlertSeverity, AlertStatus
from app.models.audit import AuditLog
from app.models.custody import CustodyTransfer, TransferStatus
from app.services.audit_chain import AuditAction, append


def create_or_dedupe_alert(
    session: Session,
    rule: str,
    severity: AlertSeverity,
    explanation: str,
    details: dict[str, Any],
    audit_seqs: list[int],
    dedupe_key: str,
    case_id: str | None = None,
    evidence_id: str | None = None,
) -> Alert | None:
    """Create alert if dedupe_key not already OPEN or ACKNOWLEDGED."""
    existing = (
        session.query(Alert)
        .filter(
            Alert.dedupe_key == dedupe_key,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
        .first()
    )
    if existing:
        return existing

    alert = Alert(
        rule=rule,
        severity=severity,
        case_id=case_id,
        evidence_id=evidence_id,
        details=details,
        explanation=explanation,
        audit_seqs=audit_seqs,
        status=AlertStatus.OPEN,
        dedupe_key=dedupe_key,
    )
    session.add(alert)
    session.flush()

    append(
        session=session,
        actor=None,
        action=AuditAction.ALERT_RAISED,
        case_id=case_id,
        evidence_id=evidence_id,
        payload={
            "alert_id": alert.id,
            "rule": rule,
            "severity": severity.value,
            "explanation": explanation,
        },
    )
    return alert


def check_missing_acknowledgements(session: Session) -> list[Alert]:
    """Flag transfers past SLA."""
    now = datetime.now(UTC)
    pending_transfers = (
        session.query(CustodyTransfer)
        .filter(
            CustodyTransfer.status == TransferStatus.PENDING_ACK, CustodyTransfer.ack_due_at < now
        )
        .all()
    )

    alerts = []
    for tr in pending_transfers:
        overdue_minutes = int((now - tr.ack_due_at).total_seconds() / 60)
        double_sla = settings.ACK_SLA_MINUTES * 2
        severity = AlertSeverity.HIGH if overdue_minutes >= double_sla else AlertSeverity.MEDIUM

        req_audit = (
            session.query(AuditLog.seq)
            .filter(AuditLog.action == "TRANSFER_REQUESTED", AuditLog.evidence_id == tr.evidence_id)
            .order_by(desc(AuditLog.seq))
            .first()
        )
        seqs = [req_audit[0]] if req_audit else []

        dedupe_key = f"MISSING_ACK:{tr.id}:{severity.value}"
        explanation = (
            f"Transfer {tr.id} is overdue by {overdue_minutes} minutes "
            f"(SLA is {settings.ACK_SLA_MINUTES}m)."
        )
        alt = create_or_dedupe_alert(
            session=session,
            rule="MISSING_ACK",
            severity=severity,
            explanation=explanation,
            details={"transfer_id": tr.id, "overdue_minutes": overdue_minutes},
            audit_seqs=seqs,
            dedupe_key=dedupe_key,
            evidence_id=tr.evidence_id,
        )
        if alt:
            alerts.append(alt)
    return alerts


def check_burst_access(session: Session) -> list[Alert]:
    """Detect more than BURST_VIEW_THRESHOLD views/downloads within BURST_WINDOW_MINUTES."""
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=settings.BURST_WINDOW_MINUTES)

    user_bursts = (
        session.query(AuditLog.actor_id, func.count(AuditLog.seq))
        .filter(
            AuditLog.action.in_(["EVIDENCE_VIEWED", "EVIDENCE_DOWNLOADED"]),
            AuditLog.ts >= window_start,
            AuditLog.actor_id is not None,
        )
        .group_by(AuditLog.actor_id)
        .having(func.count(AuditLog.seq) >= settings.BURST_VIEW_THRESHOLD)
        .all()
    )

    alerts = []
    for actor_id, count in user_bursts:
        recent_seqs = (
            session.query(AuditLog.seq)
            .filter(
                AuditLog.actor_id == actor_id,
                AuditLog.action.in_(["EVIDENCE_VIEWED", "EVIDENCE_DOWNLOADED"]),
                AuditLog.ts >= window_start,
            )
            .all()
        )
        seq_list = [s[0] for s in recent_seqs]

        window_bucket = now.strftime("%Y%m%d%H%M")[:11]  # 5-minute bucket for dedupe
        dedupe_key = f"BURST_ACCESS:{actor_id}:{window_bucket}"
        explanation = (
            f"User {actor_id} performed {count} evidence view/download operations "
            f"within {settings.BURST_WINDOW_MINUTES} minutes (threshold: {settings.BURST_VIEW_THRESHOLD})."
        )
        alt = create_or_dedupe_alert(
            session=session,
            rule="BURST_ACCESS",
            severity=AlertSeverity.MEDIUM,
            explanation=explanation,
            details={"actor_id": actor_id, "operations_count": count},
            audit_seqs=seq_list,
            dedupe_key=dedupe_key,
        )
        if alt:
            alerts.append(alt)
    return alerts


def check_repeated_denied(session: Session) -> list[Alert]:
    """Detect DENIED_ATTEMPTS_THRESHOLD or more ACCESS_DENIED within DENIED_WINDOW_MINUTES."""
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=settings.DENIED_WINDOW_MINUTES)

    denied_users = (
        session.query(AuditLog.actor_id, func.count(AuditLog.seq))
        .filter(
            AuditLog.action == "ACCESS_DENIED",
            AuditLog.ts >= window_start,
            AuditLog.actor_id is not None,
        )
        .group_by(AuditLog.actor_id)
        .having(func.count(AuditLog.seq) >= settings.DENIED_ATTEMPTS_THRESHOLD)
        .all()
    )

    alerts = []
    for actor_id, count in denied_users:
        seqs = (
            session.query(AuditLog.seq)
            .filter(
                AuditLog.actor_id == actor_id,
                AuditLog.action == "ACCESS_DENIED",
                AuditLog.ts >= window_start,
            )
            .all()
        )
        seq_list = [s[0] for s in seqs]

        window_bucket = now.strftime("%Y%m%d%H")
        dedupe_key = f"REPEATED_DENIED:{actor_id}:{window_bucket}"
        explanation = (
            f"User {actor_id} had {count} access denied rejections "
            f"within {settings.DENIED_WINDOW_MINUTES} minutes (threshold: {settings.DENIED_ATTEMPTS_THRESHOLD})."
        )
        alt = create_or_dedupe_alert(
            session=session,
            rule="REPEATED_DENIED",
            severity=AlertSeverity.HIGH,
            explanation=explanation,
            details={"actor_id": actor_id, "denied_count": count},
            audit_seqs=seq_list,
            dedupe_key=dedupe_key,
        )
        if alt:
            alerts.append(alt)
    return alerts


def check_off_hours_access(
    session: Session, actor_id: str, action_name: str, audit_seq: int, ts: datetime
) -> Alert | None:
    """Synchronous check for access outside business hours in configured timezone."""
    try:
        tz = zoneinfo.ZoneInfo(settings.BUSINESS_TZ)
        local_ts = ts.astimezone(tz)
    except Exception:
        local_ts = ts

    start_h, start_m = map(int, settings.BUSINESS_HOURS_START.split(":"))
    end_h, end_m = map(int, settings.BUSINESS_HOURS_END.split(":"))

    current_min = local_ts.hour * 60 + local_ts.minute
    start_min = start_h * 60 + start_m
    end_min = end_h * 60 + end_m

    is_off_hours = current_min < start_min or current_min > end_min or local_ts.weekday() >= 5
    if is_off_hours:
        time_str = local_ts.strftime("%H:%M %Z")
        dedupe_key = f"OFF_HOURS:{actor_id}:{local_ts.strftime('%Y%m%d')}"
        explanation = (
            f"User {actor_id} accessed evidence at {time_str}, outside business hours "
            f"({settings.BUSINESS_HOURS_START} - {settings.BUSINESS_HOURS_END} {settings.BUSINESS_TZ})."
        )
        return create_or_dedupe_alert(
            session=session,
            rule="OFF_HOURS_ACCESS",
            severity=AlertSeverity.LOW,
            explanation=explanation,
            details={"actor_id": actor_id, "action": action_name, "local_time": time_str},
            audit_seqs=[audit_seq],
            dedupe_key=dedupe_key,
        )
    return None
