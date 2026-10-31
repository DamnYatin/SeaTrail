"""
Hash-chained append-only audit log service.
Implements canonical entry serialization, SHA-256 chained hashing,
concurrency serialization via PostgreSQL advisory lock, and verification.
"""

import enum
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.models.audit import AuditCheckpoint, AuditLog
from app.models.users import User

ADVISORY_LOCK_ID = 8492049102948102


class AuditAction(str, enum.Enum):
    CHAIN_GENESIS = "CHAIN_GENESIS"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    LOGOUT = "LOGOUT"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    CASE_CREATED = "CASE_CREATED"
    CASE_MEMBER_ADDED = "CASE_MEMBER_ADDED"
    CASE_MEMBER_REMOVED = "CASE_MEMBER_REMOVED"
    CASE_CLOSED = "CASE_CLOSED"
    EVIDENCE_REGISTERED = "EVIDENCE_REGISTERED"
    INTAKE_HASH_VERIFIED = "INTAKE_HASH_VERIFIED"
    INTAKE_REJECTED = "INTAKE_REJECTED"
    EVIDENCE_VIEWED = "EVIDENCE_VIEWED"
    EVIDENCE_DOWNLOADED = "EVIDENCE_DOWNLOADED"
    EVIDENCE_LIST_EXPORTED = "EVIDENCE_LIST_EXPORTED"
    HASH_VERIFIED = "HASH_VERIFIED"
    HASH_MISMATCH = "HASH_MISMATCH"
    LABEL_PRINTED = "LABEL_PRINTED"
    EVIDENCE_ANNOTATED = "EVIDENCE_ANNOTATED"
    PERSON_ADDED = "PERSON_ADDED"
    EVENT_ADDED = "EVENT_ADDED"
    NOTE_ADDED = "NOTE_ADDED"
    EVIDENCE_LINKED = "EVIDENCE_LINKED"
    EVIDENCE_LINK_REVOKED = "EVIDENCE_LINK_REVOKED"
    TRANSFER_REQUESTED = "TRANSFER_REQUESTED"
    TRANSFER_ACKNOWLEDGED = "TRANSFER_ACKNOWLEDGED"
    TRANSFER_REJECTED = "TRANSFER_REJECTED"
    TRANSFER_CANCELLED = "TRANSFER_CANCELLED"
    TRANSFER_DISPUTED = "TRANSFER_DISPUTED"
    ACK_OVERDUE = "ACK_OVERDUE"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_EXECUTED = "APPROVAL_EXECUTED"
    LEGAL_HOLD_PLACED = "LEGAL_HOLD_PLACED"
    LEGAL_HOLD_RELEASED = "LEGAL_HOLD_RELEASED"
    RETENTION_UPDATED = "RETENTION_UPDATED"
    EVIDENCE_DISPOSED = "EVIDENCE_DISPOSED"
    CUSTODY_REPORT_GENERATED = "CUSTODY_REPORT_GENERATED"
    EXPORT_PACKAGE_BUILT = "EXPORT_PACKAGE_BUILT"
    EXPORT_PACKAGE_DOWNLOADED = "EXPORT_PACKAGE_DOWNLOADED"
    BSA_CERTIFICATE_GENERATED = "BSA_CERTIFICATE_GENERATED"
    CHAIN_VERIFIED = "CHAIN_VERIFIED"
    CHAIN_BROKEN = "CHAIN_BROKEN"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    ALERT_RAISED = "ALERT_RAISED"
    ALERT_STATUS_CHANGED = "ALERT_STATUS_CHANGED"
    ACCESS_DENIED = "ACCESS_DENIED"


@dataclass
class ChainResult:
    ok: bool
    checked: int
    head_seq: int
    head_hash: str
    first_broken_seq: int | None = None
    reason: str | None = None


def format_iso_utc(dt: datetime) -> str:
    """Format datetime as ISO-8601 UTC string with microseconds and Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonicalize_entry(
    seq: int,
    ts_str: str,
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    case_id: str | None,
    evidence_id: str | None,
    payload: dict[str, Any],
    ip: str | None,
) -> bytes:
    """
    Produce canonical bytes representation of audit log entry.
    Dictionary keys sorted, compact separators, no ASCII escape, UTF-8.
    """
    doc = {
        "action": str(action),
        "actor_id": str(actor_id) if actor_id else None,
        "actor_role": str(actor_role) if actor_role else None,
        "case_id": str(case_id) if case_id else None,
        "evidence_id": str(evidence_id) if evidence_id else None,
        "ip": str(ip) if ip else None,
        "payload": payload,
        "seq": int(seq),
        "ts": ts_str,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_entry_hash(prev_hash: str, canonical_bytes: bytes) -> str:
    """Compute entry_hash = SHA256( bytes.fromhex(prev_hash) || canonical_bytes )."""
    prev_bytes = bytes.fromhex(prev_hash)
    hasher = hashlib.sha256()
    hasher.update(prev_bytes)
    hasher.update(canonical_bytes)
    return hasher.hexdigest()


def ensure_genesis_entry(session: Session) -> AuditLog:
    """Ensure seq=1 CHAIN_GENESIS row exists."""
    existing = session.query(AuditLog).filter_by(seq=1).first()
    if existing:
        return existing

    genesis_ts = datetime(2026, 1, 1, 0, 0, 0, 0, tzinfo=UTC)
    ts_str = format_iso_utc(genesis_ts)
    prev_hash = "0" * 64
    payload = {"system": "SealTrail", "version": "1.0.0"}

    canonical_bytes = canonicalize_entry(
        seq=1,
        ts_str=ts_str,
        actor_id=None,
        actor_role=None,
        action=AuditAction.CHAIN_GENESIS.value,
        case_id=None,
        evidence_id=None,
        payload=payload,
        ip=None,
    )
    entry_hash = compute_entry_hash(prev_hash, canonical_bytes)

    genesis = AuditLog(
        seq=1,
        ts=genesis_ts,
        actor_id=None,
        actor_role=None,
        action=AuditAction.CHAIN_GENESIS.value,
        case_id=None,
        evidence_id=None,
        payload=payload,
        ip=None,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    session.add(genesis)
    session.flush()
    return genesis


def append(
    session: Session,
    actor: Any | None,
    action: AuditAction,
    case_id: str | None = None,
    evidence_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    custom_ts: datetime | None = None,
) -> AuditLog:
    """
    Append an entry to the audit log inside the current transaction.
    Takes PostgreSQL advisory transaction lock if on PostgreSQL.
    """
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID}
        )

    # Read last entry
    last_entry = session.query(AuditLog).order_by(desc(AuditLog.seq)).first()
    if last_entry is None:
        next_seq = 1
        prev_hash = "0" * 64
    else:
        next_seq = last_entry.seq + 1
        prev_hash = last_entry.entry_hash

    entry_dt = custom_ts or datetime.now(UTC)
    ts_str = format_iso_utc(entry_dt)

    actor_id = None
    actor_role = None
    if actor:
        if isinstance(actor, User):
            actor_id = actor.id
            actor_role = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
        elif isinstance(actor, dict):
            actor_id = actor.get("id")
            actor_role = actor.get("role")
        elif hasattr(actor, "id"):
            actor_id = str(actor.id)
            actor_role = str(getattr(actor, "role", ""))

    payload_clean = payload or {}

    canonical_bytes = canonicalize_entry(
        seq=next_seq,
        ts_str=ts_str,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action.value if hasattr(action, "value") else str(action),
        case_id=case_id,
        evidence_id=evidence_id,
        payload=payload_clean,
        ip=ip,
    )
    entry_hash = compute_entry_hash(prev_hash, canonical_bytes)

    entry = AuditLog(
        seq=next_seq,
        ts=entry_dt,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action.value if hasattr(action, "value") else str(action),
        case_id=case_id,
        evidence_id=evidence_id,
        payload=payload_clean,
        ip=ip,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    session.add(entry)
    session.flush()
    return entry


def append_independent(
    actor: Any | None,
    action: AuditAction,
    case_id: str | None = None,
    evidence_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Append in its own transaction (for failed logins, access denied, etc.)."""
    with get_db_session() as session:
        entry = append(
            session=session,
            actor=actor,
            action=action,
            case_id=case_id,
            evidence_id=evidence_id,
            payload=payload,
            ip=ip,
        )
        return entry


def verify_chain(session: Session) -> ChainResult:
    """
    Verify complete audit chain linkage, continuous sequences, and all signed checkpoints.
    Streams rows in chunks of 5000.
    """
    from app.services.checkpoints import verify_checkpoint

    total_rows = session.query(func.count(AuditLog.seq)).scalar() or 0
    if total_rows == 0:
        return ChainResult(ok=True, checked=0, head_seq=0, head_hash="0" * 64)

    batch_size = 5000
    expected_seq = 1
    expected_prev_hash = "0" * 64
    checked_count = 0
    head_hash = expected_prev_hash
    head_seq = 0

    recomputed_hashes: dict[int, str] = {}

    offset = 0
    while offset < total_rows:
        batch = (
            session.query(AuditLog)
            .order_by(AuditLog.seq.asc())
            .offset(offset)
            .limit(batch_size)
            .all()
        )
        if not batch:
            break

        for row in batch:
            checked_count += 1
            # Check seq continuity
            if row.seq != expected_seq:
                return ChainResult(
                    ok=False,
                    checked=checked_count - 1,
                    head_seq=expected_seq - 1,
                    head_hash=expected_prev_hash,
                    first_broken_seq=expected_seq,
                    reason="SEQ_GAP",
                )

            # Check prev_hash linkage
            if row.prev_hash != expected_prev_hash:
                return ChainResult(
                    ok=False,
                    checked=checked_count - 1,
                    head_seq=row.seq,
                    head_hash=expected_prev_hash,
                    first_broken_seq=row.seq,
                    reason="PREV_LINK_MISMATCH",
                )

            # Recompute entry hash
            ts_str = format_iso_utc(row.ts)
            canonical_bytes = canonicalize_entry(
                seq=row.seq,
                ts_str=ts_str,
                actor_id=row.actor_id,
                actor_role=row.actor_role,
                action=row.action,
                case_id=row.case_id,
                evidence_id=row.evidence_id,
                payload=row.payload,
                ip=row.ip,
            )
            recomputed = compute_entry_hash(row.prev_hash, canonical_bytes)
            if recomputed != row.entry_hash:
                return ChainResult(
                    ok=False,
                    checked=checked_count - 1,
                    head_seq=row.seq,
                    head_hash=expected_prev_hash,
                    first_broken_seq=row.seq,
                    reason="ENTRY_HASH_MISMATCH",
                )

            recomputed_hashes[row.seq] = row.entry_hash
            expected_prev_hash = row.entry_hash
            head_hash = row.entry_hash
            head_seq = row.seq
            expected_seq += 1

        offset += batch_size

    # Verify all audit checkpoints
    checkpoints = session.query(AuditCheckpoint).order_by(AuditCheckpoint.seq_to.asc()).all()
    for cp in checkpoints:
        expected_head = recomputed_hashes.get(cp.seq_to)
        if not expected_head or cp.head_hash != expected_head:
            return ChainResult(
                ok=False,
                checked=checked_count,
                head_seq=head_seq,
                head_hash=head_hash,
                first_broken_seq=cp.seq_to,
                reason="CHECKPOINT_HASH_MISMATCH",
            )
        if not verify_checkpoint(cp, expected_head):
            return ChainResult(
                ok=False,
                checked=checked_count,
                head_seq=head_seq,
                head_hash=head_hash,
                first_broken_seq=cp.seq_to,
                reason="CHECKPOINT_SIGNATURE_INVALID",
            )

    return ChainResult(
        ok=True,
        checked=checked_count,
        head_seq=head_seq,
        head_hash=head_hash,
    )
