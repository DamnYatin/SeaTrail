"""
User management request and response schemas.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.users import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    failed_login_count: int
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
