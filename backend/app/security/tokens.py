"""
JWT token creation, validation, and decoding for access and refresh flows.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt

from app.config import settings
from app.errors import AppError


def create_access_token(user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            raise AppError(code="INVALID_TOKEN", message=f"Expected {expected_type} token", status_code=401)
        return payload
    except jwt.ExpiredSignatureError:
        raise AppError(code="TOKEN_EXPIRED", message="Token has expired", status_code=401)
    except jwt.InvalidTokenError:
        raise AppError(code="INVALID_TOKEN", message="Could not validate credentials", status_code=401)
