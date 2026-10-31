"""
Dual-authorization approvals engine.
Enforces two-person integrity on sensitive workflows: EXTERNAL_TRANSFER,
EXPORT_PACKAGE, LEGAL_HOLD_RELEASE, and DISPOSAL.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.models.users import User, UserRole
from app.services.audit_chain import AuditAction, append


def create_approval_request(
    session: Session,
    case_id: str,
    kind: ApprovalKind,
    requester: User,
    justification: str,
    evidence_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
) -> ApprovalRequest:
    """Create a pending dual-authorization request."""
    if len(justification.strip()) < 10:
        raise AppError(
            code="INVALID_JUSTIFICATION",
            message="Justification must be at least 10 characters",
            status_code=400,
        )

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.APPROVAL_EXPIRY_HOURS)

    req = ApprovalRequest(
        kind=kind,
        case_id=case_id,
        evidence_id=evidence_id,
        requested_by=requester.id,
        justification=justification.strip(),
        payload=payload or {},
        status=ApprovalStatus.PENDING,
        expires_at=expires_at,
    )
    session.add(req)
    session.flush()

    append(
        session=session,
        actor=requester,
        action=AuditAction.APPROVAL_REQUESTED,
        case_id=case_id,
        evidence_id=evidence_id,
        payload={"approval_id": req.id, "kind": req.kind.value, "justification": req.justification},
        ip=ip,
    )
    return req


def decide_approval_request(
    session: Session,
    request_id: str,
    decider: User,
    approve: bool,
    decision_note: str,
    ip: str | None = None,
) -> ApprovalRequest:
    """
    Decide an approval request (Supervisor only, cannot approve own request).
    """
    req = session.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise AppError(
            code="APPROVAL_NOT_FOUND", message="Approval request not found", status_code=404
        )

    if req.status != ApprovalStatus.PENDING:
        raise AppError(
            code="APPROVAL_NOT_PENDING",
            message=f"Approval request is {req.status.value}",
            status_code=400,
        )

    now = datetime.now(UTC)
    expires_at = req.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < now:
        req.status = ApprovalStatus.EXPIRED
        session.commit()
        raise AppError(
            code="APPROVAL_EXPIRED", message="Approval request has expired", status_code=400
        )

    # Check caller is supervisor
    if decider.role != UserRole.SUPERVISOR:
        raise AppError(
            code="FORBIDDEN", message="Only supervisors can decide approvals", status_code=403
        )

    # Check two-person rule: decider cannot be requester
    if req.requested_by == decider.id:
        raise AppError(
            code="DUAL_AUTHORIZATION_VIOLATION",
            message="Dual authorization violation: You cannot decide your own approval request",
            status_code=403,
        )

    req.decided_by = decider.id
    req.decided_at = now
    req.decision_note = decision_note.strip()
    req.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED

    action = AuditAction.APPROVAL_GRANTED if approve else AuditAction.APPROVAL_REJECTED
    append(
        session=session,
        actor=decider,
        action=action,
        case_id=req.case_id,
        evidence_id=req.evidence_id,
        payload={
            "approval_id": req.id,
            "kind": req.kind.value,
            "requester_id": req.requested_by,
            "decision_note": req.decision_note,
        },
        ip=ip,
    )

    # If external transfer was approved, advance the custody transfer to PENDING_ACK
    if approve and req.kind == ApprovalKind.EXTERNAL_TRANSFER:
        from app.models.custody import CustodyTransfer, TransferStatus

        transfer = (
            session.query(CustodyTransfer)
            .filter(CustodyTransfer.approval_request_id == req.id)
            .first()
        )
        if transfer and transfer.status == TransferStatus.PENDING_APPROVAL:
            transfer.status = TransferStatus.PENDING_ACK
            transfer.ack_due_at = now + timedelta(minutes=settings.ACK_SLA_MINUTES)

    return req
