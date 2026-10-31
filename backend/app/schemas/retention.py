"""
Retention policies, legal holds, and disposal schemas.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class RetentionPolicyResponse(BaseModel):
    id: str
    name: str
    retain_days: int
    description: Optional[str] = None

    class Config:
        from_attributes = True


class RetentionPolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    retain_days: int = Field(..., ge=1)
    description: Optional[str] = None


class LegalHoldRequest(BaseModel):
    reason: str = Field(..., min_length=5)
    notes: Optional[str] = None


class LegalHoldReleaseRequest(BaseModel):
    justification: str = Field(..., min_length=10)


class DisposalRequest(BaseModel):
    justification: str = Field(..., min_length=10)


class RetentionDueItemResponse(BaseModel):
    evidence_id: str
    evidence_number: str
    item_name: str
    case_id: str
    case_number: Optional[str] = None
    retention_until: Optional[date] = None
    days_remaining: int
    legal_hold: bool
    status: str

    class Config:
        from_attributes = True
