"""
Custody transfer endpoints: initiate, acknowledge receipt, reject, and cancel.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_case_with_access, get_current_user
from app.errors import AppError
from app.models.cases import Case
from app.models.custody import CustodyTransfer, TransferStatus
from app.models.evidence import EvidenceItem
from app.models.users import User, UserRole
from app.schemas.custody import TransferCreate, TransferRejectRequest, TransferResponse
from app.services import custody

router = APIRouter(tags=["Custody Transfers"])


def serialize_transfer(session: Session, t: CustodyTransfer) -> TransferResponse:
    ev = session.query(EvidenceItem).filter(EvidenceItem.id == t.evidence_id).first()
    from_u = session.query(User).filter(User.id == t.from_user_id).first()
    to_u = session.query(User).filter(User.id == t.to_user_id).first() if t.to_user_id else None

    resp = TransferResponse.model_validate(t)
    if ev:
        resp.evidence_number = ev.evidence_number
        resp.item_name = ev.item_name
    if from_u:
        resp.from_user_name = from_u.full_name
    if to_u:
        resp.to_user_name = to_u.full_name
    return resp


@router.post("/api/v1/evidence/{evidence_id}/transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def request_transfer(
    evidence_id: str,
    req: TransferCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransferResponse:
    """Initiate an internal or external custody transfer."""
    item = session.query(EvidenceItem).filter(EvidenceItem.id == evidence_id).first()
    if not item:
        raise AppError(code="EVIDENCE_NOT_FOUND", message="Evidence not found", status_code=404)

    get_case_with_access(item.case_id, user, session, request=request)

    ip = request.client.host if request.client else None
    t = custody.initiate_transfer(
        session=session,
        evidence=item,
        sender=user,
        to_user_id=req.to_user_id,
        to_location=req.to_location,
        reason=req.reason,
        is_external=req.is_external,
        external_party=req.external_party,
        ip=ip,
    )
    return serialize_transfer(session, t)


@router.get("/api/v1/transfers", response_model=List[TransferResponse])
def list_transfers(
    status_filter: Optional[str] = Query(None, alias="status"),
    mine: bool = Query(False),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[TransferResponse]:
    """List transfers with status and role filters."""
    if user.role == UserRole.ADMIN:
        raise AppError(code="FORBIDDEN", message="Administrators cannot view custody transfers", status_code=403)

    query = session.query(CustodyTransfer)

    if mine:
        query = query.filter(or_(CustodyTransfer.from_user_id == user.id, CustodyTransfer.to_user_id == user.id))
    elif user.role not in (UserRole.SUPERVISOR, UserRole.AUDITOR):
        # Limit to cases user is member of
        from app.models.cases import CaseMember
        user_case_ids = session.query(CaseMember.case_id).filter(CaseMember.user_id == user.id).subquery()
        ev_subquery = session.query(EvidenceItem.id).filter(EvidenceItem.case_id.in_(user_case_ids)).subquery()
        query = query.filter(CustodyTransfer.evidence_id.in_(ev_subquery))

    if status_filter:
        query = query.filter(CustodyTransfer.status == status_filter)

    transfers = query.order_by(CustodyTransfer.requested_at.desc()).all()
    return [serialize_transfer(session, t) for t in transfers]


@router.post("/api/v1/transfers/{transfer_id}/acknowledge", response_model=TransferResponse)
def acknowledge_transfer_route(
    transfer_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransferResponse:
    """Acknowledge receipt of transferred evidence with hash re-verification."""
    ip = request.client.host if request.client else None
    t = custody.acknowledge_transfer(session, transfer_id, receiver=user, ip=ip)
    return serialize_transfer(session, t)


@router.post("/api/v1/transfers/{transfer_id}/reject", response_model=TransferResponse)
def reject_transfer_route(
    transfer_id: str,
    req: TransferRejectRequest,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransferResponse:
    """Reject pending custody transfer."""
    ip = request.client.host if request.client else None
    t = custody.reject_transfer(session, transfer_id, receiver=user, reason=req.reason, ip=ip)
    return serialize_transfer(session, t)


@router.post("/api/v1/transfers/{transfer_id}/cancel", response_model=TransferResponse)
def cancel_transfer_route(
    transfer_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransferResponse:
    """Cancel pending custody transfer by sender."""
    ip = request.client.host if request.client else None
    t = custody.cancel_transfer(session, transfer_id, sender=user, ip=ip)
    return serialize_transfer(session, t)
