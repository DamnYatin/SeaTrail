"""
Case management and membership schemas.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.cases import CaseClassification, CaseMemberRole, CaseStatus


class CaseCreate(BaseModel):
    name: str
    description: str | None = None
    classification: CaseClassification = CaseClassification.CONFIDENTIAL
    lead_user_id: str | None = None
    retention_policy_id: str | None = None


class CaseResponse(BaseModel):
    id: str
    case_number: str
    name: str
    description: str | None = None
    status: CaseStatus
    classification: CaseClassification
    lead_user_id: str
    evidence_counter: int
    legal_hold: bool
    legal_hold_reason: str | None = None
    retention_policy_id: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None
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
    user_email: str | None = None
    user_name: str | None = None

    class Config:
        from_attributes = True


class CaseTimelineItem(BaseModel):
    id: str
    type: str  # EVENT, REGISTRATION, TRANSFER, ACKNOWLEDGEMENT, ANNOTATION, APPROVAL
    title: str
    description: str | None = None
    occurred_at: datetime
    actor_id: str | None = None
    actor_name: str | None = None
    details: dict | None = None
