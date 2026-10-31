"""
Case management, membership assignments, and merged chronological incident timeline.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_case_with_access, get_current_user, require_permission
from app.errors import AppError
from app.models.audit import AuditLog
from app.models.cases import Case, CaseMember, CaseMemberRole, CaseStatus
from app.models.links import CaseEvent
from app.models.users import User, UserRole
from app.schemas.cases import (
    CaseCreate,
    CaseMemberCreate,
    CaseMemberResponse,
    CaseResponse,
    CaseTimelineItem,
)
from app.security.permissions import Permission
from app.services.audit_chain import AuditAction, append

router = APIRouter(prefix="/api/v1/cases", tags=["Cases"])


def generate_case_number(session: Session) -> str:
    """Generate case number in SL{yy}-{seq:04d} format."""
    yy = datetime.now(UTC).strftime("%y")
    count = session.query(func.count(Case.id)).scalar() or 0
    return f"SL{yy}-{(count + 1):04d}"


@router.get("", response_model=list[CaseResponse])
def list_cases(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CaseResponse]:
    """
    List accessible cases based on caller role:
    - ADMIN cannot view cases (separation of duties -> 403).
    - SUPERVISOR and AUDITOR view all cases.
    - INVESTIGATOR and CUSTODIAN view cases where they hold membership.
    """
    if user.role == UserRole.ADMIN:
        from app.services.audit_chain import append_independent

        ip = request.client.host if request.client else None
        append_independent(
            actor=user,
            action=AuditAction.ACCESS_DENIED,
            payload={"reason": "ADMIN_CANNOT_VIEW_CASES"},
            ip=ip,
        )
        raise AppError(
            code="FORBIDDEN",
            message="Administrators cannot view cases or evidence (separation of duties)",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if user.role in (UserRole.SUPERVISOR, UserRole.AUDITOR):
        return session.query(Case).order_by(Case.opened_at.desc()).all()

    # Members only
    user_case_ids = (
        session.query(CaseMember.case_id).filter(CaseMember.user_id == user.id).subquery()
    )
    return (
        session.query(Case)
        .filter(Case.id.in_(select(user_case_ids)))
        .order_by(Case.opened_at.desc())
        .all()
    )


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    req: CaseCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CREATE_CASE)),
) -> CaseResponse:
    """Create a new case, assign case number, and register creator as Lead."""
    ip = request.client.host if request.client else None
    case_number = generate_case_number(session)
    lead_id = req.lead_user_id or user.id

    case = Case(
        case_number=case_number,
        name=req.name.strip(),
        description=req.description.strip() if req.description else None,
        classification=req.classification,
        status=CaseStatus.OPEN,
        lead_user_id=lead_id,
        evidence_counter=0,
        retention_policy_id=req.retention_policy_id,
        created_by=user.id,
    )
    session.add(case)
    session.flush()

    # Add creator as LEAD member
    member = CaseMember(
        case_id=case.id,
        user_id=lead_id,
        case_role=CaseMemberRole.LEAD,
        added_by=user.id,
    )
    session.add(member)

    append(
        session=session,
        actor=user,
        action=AuditAction.CASE_CREATED,
        case_id=case.id,
        payload={"case_number": case.case_number, "name": case.name, "lead_user_id": lead_id},
        ip=ip,
    )

    return case


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseResponse:
    """Get case details subject to case isolation authorization."""
    return get_case_with_access(case_id, user, session, request=request)


@router.post("/{case_id}/close", response_model=CaseResponse)
def close_case(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseResponse:
    """Close an open case (Case Lead or Supervisor only)."""
    ip = request.client.host if request.client else None
    case = get_case_with_access(case_id, user, session, request=request, require_lead=True)

    if case.status == CaseStatus.CLOSED:
        return case

    case.status = CaseStatus.CLOSED
    case.closed_at = datetime.now(UTC)

    append(
        session=session,
        actor=user,
        action=AuditAction.CASE_CLOSED,
        case_id=case.id,
        payload={"case_number": case.case_number, "closed_at": case.closed_at.isoformat()},
        ip=ip,
    )
    return case


@router.get("/{case_id}/members", response_model=list[CaseMemberResponse])
def get_members(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CaseMemberResponse]:
    """List members assigned to the case."""
    get_case_with_access(case_id, user, session, request=request)
    members = session.query(CaseMember).filter(CaseMember.case_id == case_id).all()
    results = []
    for m in members:
        u = session.query(User).filter(User.id == m.user_id).first()
        results.append(
            CaseMemberResponse(
                case_id=m.case_id,
                user_id=m.user_id,
                case_role=m.case_role,
                added_by=m.added_by,
                added_at=m.added_at,
                user_email=u.email if u else None,
                user_name=u.full_name if u else None,
            )
        )
    return results


@router.post(
    "/{case_id}/members", response_model=CaseMemberResponse, status_code=status.HTTP_201_CREATED
)
def add_member(
    case_id: str,
    req: CaseMemberCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseMemberResponse:
    """Add a user to the case (Lead or Supervisor only)."""
    ip = request.client.host if request.client else None
    case = get_case_with_access(case_id, user, session, request=request, require_lead=True)

    target_user = (
        session.query(User).filter(User.id == req.user_id, User.is_active.is_(True)).first()
    )
    if not target_user:
        raise AppError(
            code="USER_NOT_FOUND",
            message=f"User {req.user_id} not found or inactive",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    existing = (
        session.query(CaseMember)
        .filter(CaseMember.case_id == case_id, CaseMember.user_id == req.user_id)
        .first()
    )
    if existing:
        raise AppError(
            code="MEMBER_EXISTS",
            message="User is already a member of this case",
            status_code=status.HTTP_409_CONFLICT,
        )

    member = CaseMember(
        case_id=case_id,
        user_id=req.user_id,
        case_role=req.case_role,
        added_by=user.id,
    )
    session.add(member)
    session.flush()

    append(
        session=session,
        actor=user,
        action=AuditAction.CASE_MEMBER_ADDED,
        case_id=case.id,
        payload={"added_user_id": req.user_id, "role": req.case_role.value},
        ip=ip,
    )

    return CaseMemberResponse(
        case_id=member.case_id,
        user_id=member.user_id,
        case_role=member.case_role,
        added_by=member.added_by,
        added_at=member.added_at,
        user_email=target_user.email,
        user_name=target_user.full_name,
    )


@router.delete("/{case_id}/members/{user_id}")
def remove_member(
    case_id: str,
    user_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove a member from the case (Lead or Supervisor only)."""
    ip = request.client.host if request.client else None
    case = get_case_with_access(case_id, user, session, request=request, require_lead=True)

    member = (
        session.query(CaseMember)
        .filter(CaseMember.case_id == case_id, CaseMember.user_id == user_id)
        .first()
    )
    if not member:
        raise AppError(
            code="MEMBER_NOT_FOUND",
            message="User is not a member of this case",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    session.delete(member)

    append(
        session=session,
        actor=user,
        action=AuditAction.CASE_MEMBER_REMOVED,
        case_id=case.id,
        payload={"removed_user_id": user_id},
        ip=ip,
    )
    return {"status": "ok", "message": "Member removed successfully"}


@router.get("/{case_id}/timeline", response_model=list[CaseTimelineItem])
def get_timeline(
    case_id: str,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CaseTimelineItem]:
    """
    Get merged chronological timeline for the case.
    Merges manually logged case events and immutable audit chain entries.
    """
    get_case_with_access(case_id, user, session, request=request)

    timeline: list[CaseTimelineItem] = []

    # 1. Fetch Case Events
    events = session.query(CaseEvent).filter(CaseEvent.case_id == case_id).all()
    for ev in events:
        creator = session.query(User).filter(User.id == ev.created_by).first()
        timeline.append(
            CaseTimelineItem(
                id=ev.id,
                type="EVENT",
                title=ev.title,
                description=ev.description,
                occurred_at=ev.occurred_at,
                actor_id=ev.created_by,
                actor_name=creator.full_name if creator else None,
            )
        )

    # 2. Fetch Relevant Audit Entries for this case
    relevant_actions = {
        "EVIDENCE_REGISTERED": "Evidence Registered",
        "TRANSFER_REQUESTED": "Transfer Requested",
        "TRANSFER_ACKNOWLEDGED": "Custody Acknowledged",
        "EVIDENCE_ANNOTATED": "Annotation Added",
        "APPROVAL_GRANTED": "Approval Granted",
        "CASE_CLOSED": "Case Closed",
    }
    audit_entries = (
        session.query(AuditLog)
        .filter(AuditLog.case_id == case_id, AuditLog.action.in_(list(relevant_actions.keys())))
        .all()
    )
    for entry in audit_entries:
        actor = (
            session.query(User).filter(User.id == entry.actor_id).first()
            if entry.actor_id
            else None
        )
        timeline.append(
            CaseTimelineItem(
                id=f"audit-{entry.seq}",
                type=entry.action,
                title=relevant_actions.get(entry.action, entry.action),
                description=None,
                occurred_at=entry.ts,
                actor_id=entry.actor_id,
                actor_name=actor.full_name if actor else "System",
                details=entry.payload,
            )
        )

    timeline.sort(key=lambda item: item.occurred_at, reverse=True)
    return timeline
