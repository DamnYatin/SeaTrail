"""
Dual authorization request and decision schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.approvals import ApprovalKind, ApprovalStatus


class ApprovalCreate(BaseModel):
    kind: ApprovalKind
    justification: str
    evidence_id: str | None = None
    payload: dict[str, Any] | None = None


class ApprovalDecision(BaseModel):
    decision_note: str


class ApprovalResponse(BaseModel):
    id: str
    kind: ApprovalKind
    case_id: str
    case_number: str | None = None
    evidence_id: str | None = None
    evidence_number: str | None = None
    requested_by: str
    requester_name: str | None = None
    justification: str
    payload: dict[str, Any] | None = None
    status: ApprovalStatus
    decided_by: str | None = None
    decider_name: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    expires_at: datetime
    executed_at: datetime | None = None

    class Config:
        from_attributes = True
