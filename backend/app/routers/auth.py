"""
Authentication routes: login, token refresh, logout, and current user profile.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.errors import AppError
from app.logging import logger
from app.models.users import User
from app.schemas.auth import LoginRequest, LoginResponse, RefreshResponse, UserProfileResponse
from app.security.passwords import verify_password
from app.security.tokens import create_access_token, create_refresh_token, decode_token
from app.services.audit_chain import AuditAction, append, append_independent

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user credentials, enforce lockout after threshold failures,
    set httpOnly refresh cookie and return access token.
    """
    email_clean = req.email.strip().lower()
    ip = request.client.host if request.client else None
    now = datetime.now(timezone.utc)

    user = session.query(User).filter(User.email == email_clean).first()

    # Generic invalid credentials message to prevent account enumeration
    invalid_err = AppError(
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
        status_code=status.HTTP_401_UNAUTHORIZED,
    )

    if not user or not user.is_active:
        append_independent(
            actor=None,
            action=AuditAction.LOGIN_FAILED,
            payload={"attempted_email": email_clean, "reason": "UNKNOWN_OR_INACTIVE"},
            ip=ip,
        )
        raise invalid_err

    # Check lockout
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() / 60)
        append_independent(
            actor=user,
            action=AuditAction.LOGIN_FAILED,
            payload={"reason": "ACCOUNT_LOCKED", "remaining_minutes": remaining},
            ip=ip,
        )
        raise AppError(
            code="ACCOUNT_LOCKED",
            message=f"Account temporarily locked due to multiple failed attempts. Try again in {remaining + 1} minutes.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Verify password
    if not verify_password(req.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.LOGIN_MAX_FAILURES:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            session.commit()
            append_independent(
                actor=user,
                action=AuditAction.ACCOUNT_LOCKED,
                payload={"failures": user.failed_login_count, "lockout_minutes": settings.LOGIN_LOCKOUT_MINUTES},
                ip=ip,
            )
            raise AppError(
                code="ACCOUNT_LOCKED",
                message=f"Account locked due to {settings.LOGIN_MAX_FAILURES} consecutive failed attempts.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        else:
            session.commit()
            append_independent(
                actor=user,
                action=AuditAction.LOGIN_FAILED,
                payload={"attempted_email": email_clean, "failures": user.failed_login_count},
                ip=ip,
            )
            raise invalid_err

    # Password verified: reset failure count
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now

    access_token = create_access_token(user.id, user.email, user.role.value)
    refresh_token = create_refresh_token(user.id)

    # Set httpOnly refresh cookie
    response.set_cookie(
        key="sealtrail_refresh",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_REFRESH_DAYS * 86400,
        path="/api/v1/auth",
    )

    append(
        session=session,
        actor=user,
        action=AuditAction.LOGIN_SUCCESS,
        payload={"email": user.email, "role": user.role.value},
        ip=ip,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    request: Request,
    response: Response,
    sealtrail_refresh: Optional[str] = Cookie(None),
    session: Session = Depends(get_db),
) -> RefreshResponse:
    """Silent refresh of access token using httpOnly cookie."""
    if not sealtrail_refresh:
        raise AppError(code="UNAUTHORIZED", message="Refresh token missing", status_code=status.HTTP_401_UNAUTHORIZED)

    payload = decode_token(sealtrail_refresh, expected_type="refresh")
    user_id = payload.get("sub")

    user = session.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User inactive or deleted", status_code=status.HTTP_401_UNAUTHORIZED)

    new_access = create_access_token(user.id, user.email, user.role.value)
    new_refresh = create_refresh_token(user.id)

    response.set_cookie(
        key="sealtrail_refresh",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_REFRESH_DAYS * 86400,
        path="/api/v1/auth",
    )

    return RefreshResponse(access_token=new_access, token_type="bearer")


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Log out current user and clear refresh cookie."""
    ip = request.client.host if request.client else None
    response.delete_cookie(key="sealtrail_refresh", path="/api/v1/auth")

    append(
        session=session,
        actor=user,
        action=AuditAction.LOGOUT,
        payload={"email": user.email},
        ip=ip,
    )
    return {"status": "ok", "message": "Successfully logged out"}


@router.get("/me", response_model=UserProfileResponse)
def me(user: User = Depends(get_current_user)) -> UserProfileResponse:
    """Return currently authenticated user profile."""
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )
