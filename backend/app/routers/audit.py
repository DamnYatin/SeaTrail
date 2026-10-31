"""
Audit log, chain verification, and checkpoints router.
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.errors import AppError
from app.models.audit import AuditCheckpoint, AuditLog
from app.models.cases import Case
from app.models.evidence import EvidenceItem
from app.models.integrity import IntegrityState
from app.models.users import User
from app.schemas.audit import (
    AuditEntryResponse,
    AuditListResponse,
    AuditVerifyResponse,
    CheckpointResponse,
)
from app.security.permissions import Permission
from app.services import audit_chain, checkpoints
from app.services.audit_chain import AuditAction, append

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Log"])


def _to_entry_response(session: Session, entry: AuditLog) -> AuditEntryResponse:
    actor_name = None
    actor_role = entry.actor_role
    if entry.actor_id:
        u = session.query(User.full_name, User.role).filter(User.id == entry.actor_id).first()
        if u:
            actor_name = u[0]
            if not actor_role:
                actor_role = u[1].value

    case_num = None
    if entry.case_id:
        c = session.query(Case.case_number).filter(Case.id == entry.case_id).first()
        if c:
            case_num = c[0]

    ev_num = None
    if entry.evidence_id:
        e = session.query(EvidenceItem.evidence_number).filter(EvidenceItem.id == entry.evidence_id).first()
        if e:
            ev_num = e[0]

    return AuditEntryResponse(
        seq=entry.seq,
        ts=entry.ts,
        actor_id=entry.actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        action=entry.action,
        case_id=entry.case_id,
        case_number=case_num,
        evidence_id=entry.evidence_id,
        evidence_number=ev_num,
        payload=entry.payload or {},
        ip=entry.ip,
        prev_hash=entry.prev_hash,
        entry_hash=entry.entry_hash,
    )


@router.get("", response_model=AuditListResponse)
def list_audit_entries(
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    case_id: Optional[str] = Query(None),
    evidence_id: Optional[str] = Query(None),
    from_seq: Optional[int] = Query(None),
    to_seq: Optional[int] = Query(None),
    from_ts: Optional[datetime] = Query(None),
    to_ts: Optional[datetime] = Query(None),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_permission(Permission.READ_AUDIT_LOG)),
    session: Session = Depends(get_db),
):
    query = session.query(AuditLog)

    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if case_id:
        query = query.filter(AuditLog.case_id == case_id)
    if evidence_id:
        query = query.filter(AuditLog.evidence_id == evidence_id)
    if from_seq is not None:
        query = query.filter(AuditLog.seq >= from_seq)
    if to_seq is not None:
        query = query.filter(AuditLog.seq <= to_seq)
    if from_ts is not None:
        query = query.filter(AuditLog.ts >= from_ts)
    if to_ts is not None:
        query = query.filter(AuditLog.ts <= to_ts)

    total = query.count()

    order_col = desc(AuditLog.seq) if order == "desc" else asc(AuditLog.seq)
    offset = (page - 1) * page_size
    entries = query.order_by(order_col).offset(offset).limit(page_size).all()

    # Get chain integrity state
    state = session.query(IntegrityState).filter(IntegrityState.id == 1).first()
    head_entry = session.query(AuditLog.seq).order_by(desc(AuditLog.seq)).first()
    head_seq = head_entry[0] if head_entry else 0
    chain_ok = state.chain_ok if state else True

    items = [_to_entry_response(session, e) for e in entries]

    return AuditListResponse(
        items=items,
        total=total,
        head_seq=head_seq,
        chain_ok=chain_ok,
    )


@router.post("/verify", response_model=AuditVerifyResponse)
def verify_audit_chain(
    request: Request,
    current_user: User = Depends(require_permission(Permission.VERIFY_CHAIN)),
    session: Session = Depends(get_db),
):
    result = audit_chain.verify_chain(session)

    # Update integrity state
    state = session.query(IntegrityState).filter(IntegrityState.id == 1).first()
    if not state:
        state = IntegrityState(id=1)
        session.add(state)

    state.last_chain_check_at = datetime.now(timezone.utc)
    state.chain_ok = result.ok
    state.head_seq = result.head_seq
    state.broken_seq = result.first_broken_seq
    state.broken_reason = result.reason
    session.flush()

    ip = request.client.host if request.client else None
    action = AuditAction.CHAIN_VERIFIED if result.ok else AuditAction.CHAIN_BROKEN
    append(
        session=session,
        actor=current_user,
        action=action,
        payload={
            "ok": result.ok,
            "checked": result.checked,
            "head_seq": result.head_seq,
            "head_hash": result.head_hash,
            "first_broken_seq": result.first_broken_seq,
            "reason": result.reason,
        },
        ip=ip,
    )

    return AuditVerifyResponse(
        ok=result.ok,
        checked=result.checked,
        head_seq=result.head_seq,
        head_hash=result.head_hash,
        first_broken_seq=result.first_broken_seq,
        reason=result.reason,
    )


@router.get("/checkpoints", response_model=List[CheckpointResponse])
def list_checkpoints(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission(Permission.READ_AUDIT_LOG)),
    session: Session = Depends(get_db),
):
    cps = (
        session.query(AuditCheckpoint)
        .order_by(desc(AuditCheckpoint.seq_to))
        .limit(limit)
        .all()
    )
    return cps


@router.post("/checkpoints", response_model=CheckpointResponse)
def create_checkpoint_endpoint(
    request: Request,
    current_user: User = Depends(require_permission(Permission.VERIFY_CHAIN)),
    session: Session = Depends(get_db),
):
    cp = checkpoints.create_checkpoint(session, created_by=current_user.id)
    if not cp:
        raise AppError(code="EMPTY_CHAIN", message="Audit chain is empty; cannot create checkpoint", status_code=status.HTTP_400_BAD_REQUEST)

    ip = request.client.host if request.client else None
    append(
        session=session,
        actor=current_user,
        action=AuditAction.CHECKPOINT_CREATED,
        payload={
            "checkpoint_id": cp.id,
            "seq_to": cp.seq_to,
            "head_hash": cp.head_hash,
            "public_key_id": cp.public_key_id,
        },
        ip=ip,
    )
    return cp
