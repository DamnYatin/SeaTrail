"""
User management request and response schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.models.users import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    failed_login_count: int
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
