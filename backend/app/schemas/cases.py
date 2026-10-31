"""
Case management and membership schemas.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.models.cases import CaseClassification, CaseMemberRole, CaseStatus


class CaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    classification: CaseClassification = CaseClassification.CONFIDENTIAL
    lead_user_id: Optional[str] = None
    retention_policy_id: Optional[str] = None


class CaseResponse(BaseModel):
    id: str
    case_number: str
    name: str
    description: Optional[str] = None
    status: CaseStatus
    classification: CaseClassification
    lead_user_id: str
    evidence_counter: int
    legal_hold: bool
    legal_hold_reason: Optional[str] = None
    retention_policy_id: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    created_by: str

    class Config:
        from_attributes = True


class CaseMemberCreate(BaseModel):
    user_id: str
    case_role: CaseMemberRole = CaseMemberRole.MEMBER


class CaseMemberResponse(BaseModel):
    case_id: str
    user_id: str
    case_role: CaseMemberRole
    added_by: str
    added_at: datetime
    user_email: Optional[str] = None
    user_name: Optional[str] = None

    class Config:
        from_attributes = True


class CaseTimelineItem(BaseModel):
    id: str
    type: str  # EVENT, REGISTRATION, TRANSFER, ACKNOWLEDGEMENT, ANNOTATION, APPROVAL
    title: str
    description: Optional[str] = None
    occurred_at: datetime
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    details: Optional[dict] = None
