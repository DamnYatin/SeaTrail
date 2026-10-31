"""
Dual authorization approval endpoints.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.errors import AppError
from app.models.approvals import ApprovalRequest, ApprovalStatus
from app.models.cases import Case
from app.models.evidence import EvidenceItem
from app.models.users import User, UserRole
from app.schemas.approvals import ApprovalDecision, ApprovalResponse
from app.services import approvals

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


def serialize_approval(session: Session, req: ApprovalRequest) -> ApprovalResponse:
    resp = ApprovalResponse.model_validate(req)
    case = session.query(Case).filter(Case.id == req.case_id).first()
    ev = (
        session.query(EvidenceItem).filter(EvidenceItem.id == req.evidence_id).first()
        if req.evidence_id
        else None
    )
    req_u = session.query(User).filter(User.id == req.requested_by).first()
    dec_u = (
        session.query(User).filter(User.id == req.decided_by).first() if req.decided_by else None
    )

    if case:
        resp.case_number = case.case_number
    if ev:
        resp.evidence_number = ev.evidence_number
    if req_u:
        resp.requester_name = req_u.full_name
    if dec_u:
        resp.decider_name = dec_u.full_name
    return resp


@router.get("", response_model=list[ApprovalResponse])
def list_approvals(
    status_filter: str | None = Query(None, alias="status"),
    mine: bool = Query(False),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApprovalResponse]:
    """List approval requests (filter by status or requests authored by caller)."""
    if user.role == UserRole.ADMIN:
        raise AppError(
            code="FORBIDDEN", message="Administrators cannot view approvals", status_code=403
        )

    query = session.query(ApprovalRequest)
    if mine:
        query = query.filter(ApprovalRequest.requested_by == user.id)
    if status_filter:
        query = query.filter(ApprovalRequest.status == status_filter)

    reqs = query.order_by(ApprovalRequest.expires_at.desc()).all()
    return [serialize_approval(session, r) for r in reqs]


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_request(
    approval_id: str,
    decision: ApprovalDecision,
    request: Request,
    session: Session = Depends(get_db),
    supervisor: User = Depends(require_role(UserRole.SUPERVISOR)),
) -> ApprovalResponse:
    """Approve dual-authorization request (Supervisor other than requester)."""
    ip = request.client.host if request.client else None
    req = approvals.decide_approval_request(
        session=session,
        request_id=approval_id,
        decider=supervisor,
        approve=True,
        decision_note=decision.decision_note,
        ip=ip,
    )
    return serialize_approval(session, req)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_request(
    approval_id: str,
    decision: ApprovalDecision,
    request: Request,
    session: Session = Depends(get_db),
    supervisor: User = Depends(require_role(UserRole.SUPERVISOR)),
) -> ApprovalResponse:
    """Reject dual-authorization request."""
    ip = request.client.host if request.client else None
    req = approvals.decide_approval_request(
        session=session,
        request_id=approval_id,
        decider=supervisor,
        approve=False,
        decision_note=decision.decision_note,
        ip=ip,
    )
    return serialize_approval(session, req)


@router.post("/{approval_id}/cancel", response_model=ApprovalResponse)
def cancel_request(
    approval_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApprovalResponse:
    """Cancel pending request by the original requester."""
    req = session.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not req:
        raise AppError(
            code="APPROVAL_NOT_FOUND", message="Approval request not found", status_code=404
        )

    if req.requested_by != user.id and user.role != UserRole.SUPERVISOR:
        raise AppError(
            code="FORBIDDEN",
            message="Only the requester or a supervisor can cancel",
            status_code=403,
        )

    if req.status != ApprovalStatus.PENDING:
        raise AppError(
            code="INVALID_STATE",
            message="Request cannot be cancelled in current status",
            status_code=400,
        )

    req.status = ApprovalStatus.CANCELLED
    ip = request.client.host if request.client else None
    from app.services.audit_chain import AuditAction, append

    append(
        session=session,
        actor=user,
        action=AuditAction.APPROVAL_REJECTED,
        case_id=req.case_id,
        evidence_id=req.evidence_id,
        payload={"approval_id": req.id, "cancelled": True},
        ip=ip,
    )
    return serialize_approval(session, req)
