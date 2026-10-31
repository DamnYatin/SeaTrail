"""
FastAPI dependency providers for authentication, RBAC authorization, and case-isolation.
"""

from typing import Callable, List, Optional
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models.cases import Case, CaseMember
from app.models.users import User, UserRole
from app.security.permissions import Permission, has_permission
from app.security.tokens import decode_token
from app.services.audit_chain import AuditAction, append_independent

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: Session = Depends(get_db),
) -> User:
    """Extract and validate the currently authenticated user from Bearer JWT."""
    if not creds or not creds.credentials:
        raise AppError(code="UNAUTHORIZED", message="Authentication credentials missing", status_code=status.HTTP_401_UNAUTHORIZED)

    payload = decode_token(creds.credentials, expected_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise AppError(code="INVALID_TOKEN", message="Token payload missing subject", status_code=status.HTTP_401_UNAUTHORIZED)

    user = session.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User inactive or does not exist", status_code=status.HTTP_401_UNAUTHORIZED)

    # Attach user to request state for request logging
    request.state.current_user = user
    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    """Dependency ensuring user belongs to one of the specified roles."""
    def role_checker(request: Request, user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            ip = request.client.host if request.client else None
            append_independent(
                actor=user,
                action=AuditAction.ACCESS_DENIED,
                payload={"reason": "ROLE_MISMATCH", "required": [r.value for r in allowed_roles]},
                ip=ip,
            )
            raise AppError(
                code="FORBIDDEN",
                message=f"Access requires one of roles: {[r.value for r in allowed_roles]}",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return user
    return role_checker


def require_permission(perm: Permission) -> Callable:
    """Dependency verifying role has the declared permission."""
    def perm_checker(request: Request, user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, perm):
            ip = request.client.host if request.client else None
            append_independent(
                actor=user,
                action=AuditAction.ACCESS_DENIED,
                payload={"reason": "PERMISSION_DENIED", "permission": perm.value},
                ip=ip,
            )
            raise AppError(
                code="FORBIDDEN",
                message=f"Role {user.role.value} lacks required permission: {perm.value}",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return user
    return perm_checker


def get_case_with_access(
    case_id: str,
    user: User,
    session: Session,
    request: Optional[Request] = None,
    require_lead: bool = False,
    allow_observer: bool = True,
) -> Case:
    """
    Enforce case access isolation rules:
    - ADMIN has NO access to cases or evidence (separation of duties).
    - SUPERVISOR and AUDITOR have global read access to all cases.
    - INVESTIGATOR and CUSTODIAN must be explicit case members.
    - If require_lead is True, user must be the case lead or SUPERVISOR.
    - Audits ACCESS_DENIED on unauthorized attempts.
    """
    ip = request.client.host if request and request.client else None

    # ADMIN cannot access cases or evidence
    if user.role == UserRole.ADMIN:
        append_independent(
            actor=user,
            action=AuditAction.ACCESS_DENIED,
            case_id=case_id,
            payload={"reason": "ADMIN_CANNOT_VIEW_CASES"},
            ip=ip,
        )
        raise AppError(
            code="FORBIDDEN",
            message="Administrators cannot view case or evidence content (separation of duties)",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    case = session.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise AppError(code="CASE_NOT_FOUND", message=f"Case {case_id} not found", status_code=status.HTTP_404_NOT_FOUND)

    # Global roles
    if user.role in (UserRole.SUPERVISOR, UserRole.AUDITOR):
        if require_lead and user.role != UserRole.SUPERVISOR:
            append_independent(
                actor=user,
                action=AuditAction.ACCESS_DENIED,
                case_id=case_id,
                payload={"reason": "LEAD_REQUIRED"},
                ip=ip,
            )
            raise AppError(code="FORBIDDEN", message="Action requires Case Lead status", status_code=status.HTTP_403_FORBIDDEN)
        return case

    # Membership check for INVESTIGATOR / CUSTODIAN
    member = (
        session.query(CaseMember)
        .filter(CaseMember.case_id == case_id, CaseMember.user_id == user.id)
        .first()
    )

    if not member:
        append_independent(
            actor=user,
            action=AuditAction.ACCESS_DENIED,
            case_id=case_id,
            payload={"reason": "NOT_A_CASE_MEMBER"},
            ip=ip,
        )
        raise AppError(
            code="FORBIDDEN",
            message="You are not an assigned member of this case",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if require_lead and member.case_role.value != "LEAD":
        append_independent(
            actor=user,
            action=AuditAction.ACCESS_DENIED,
            case_id=case_id,
            payload={"reason": "LEAD_REQUIRED"},
            ip=ip,
        )
        raise AppError(
            code="FORBIDDEN",
            message="Action requires Case Lead status",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if not allow_observer and member.case_role.value == "OBSERVER":
        append_independent(
            actor=user,
            action=AuditAction.ACCESS_DENIED,
            case_id=case_id,
            payload={"reason": "OBSERVER_ACTION_DENIED"},
            ip=ip,
        )
        raise AppError(
            code="FORBIDDEN",
            message="Observers have read-only privileges",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return case
