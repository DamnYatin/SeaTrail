"""
Dual authorization request and decision schemas.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.models.approvals import ApprovalKind, ApprovalStatus


class ApprovalCreate(BaseModel):
    kind: ApprovalKind
    justification: str
    evidence_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class ApprovalDecision(BaseModel):
    decision_note: str


class ApprovalResponse(BaseModel):
    id: str
    kind: ApprovalKind
    case_id: str
    case_number: Optional[str] = None
    evidence_id: Optional[str] = None
    evidence_number: Optional[str] = None
    requested_by: str
    requester_name: Optional[str] = None
    justification: str
    payload: Optional[Dict[str, Any]] = None
    status: ApprovalStatus
    decided_by: Optional[str] = None
    decider_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    expires_at: datetime
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
