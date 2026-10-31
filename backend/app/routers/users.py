"""
User management endpoints (ADMIN only).
"""

from typing import List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.errors import AppError
from app.models.users import User, UserRole
from app.schemas.users import UserCreate, UserResponse, UserUpdate
from app.security.passwords import hash_password, validate_password_complexity
from app.services.audit_chain import AuditAction, append

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("", response_model=List[UserResponse])
def list_users(
    session: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> List[UserResponse]:
    """List all user accounts in the system."""
    return session.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreate,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> UserResponse:
    """Create a new user account with validated password complexity."""
    email_clean = str(req.email).strip().lower()
    ip = request.client.host if request.client else None

    existing = session.query(User).filter(User.email == email_clean).first()
    if existing:
        raise AppError(code="EMAIL_EXISTS", message=f"User with email {email_clean} already exists", status_code=status.HTTP_409_CONFLICT)

    if not validate_password_complexity(req.password):
        raise AppError(
            code="WEAK_PASSWORD",
            message="Password does not meet complexity requirements (minimum 10 chars, letter and number required)",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(
        email=email_clean,
        full_name=req.full_name.strip(),
        role=req.role,
        password_hash=hash_password(req.password),
        is_active=True,
    )
    session.add(user)
    session.flush()

    append(
        session=session,
        actor=admin,
        action=AuditAction.USER_CREATED,
        payload={"created_user_id": user.id, "email": user.email, "role": user.role.value},
        ip=ip,
    )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    req: UserUpdate,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> UserResponse:
    """Update user attributes (role, active status, name, or password)."""
    ip = request.client.host if request.client else None
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message=f"User {user_id} not found", status_code=status.HTTP_404_NOT_FOUND)

    changes = {}
    if req.full_name is not None:
        user.full_name = req.full_name.strip()
        changes["full_name"] = user.full_name

    if req.role is not None:
        user.role = req.role
        changes["role"] = user.role.value

    if req.is_active is not None:
        user.is_active = req.is_active
        changes["is_active"] = user.is_active

    if req.password is not None:
        if not validate_password_complexity(req.password):
            raise AppError(
                code="WEAK_PASSWORD",
                message="Password does not meet complexity requirements",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user.password_hash = hash_password(req.password)
        changes["password_reset"] = True

    append(
        session=session,
        actor=admin,
        action=AuditAction.USER_UPDATED,
        payload={"updated_user_id": user.id, "changes": changes},
        ip=ip,
    )

    return user
