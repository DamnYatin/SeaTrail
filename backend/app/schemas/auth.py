"""
Authentication request and response schemas.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr

from app.models.users import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    role: UserRole


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
