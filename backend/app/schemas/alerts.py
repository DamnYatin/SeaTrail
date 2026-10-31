"""
Security anomaly alerts request and response schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.models.alerts import AlertSeverity, AlertStatus


class AlertResponse(BaseModel):
    id: str
    rule: str
    severity: AlertSeverity
    case_id: Optional[str] = None
    case_number: Optional[str] = None
    evidence_id: Optional[str] = None
    evidence_number: Optional[str] = None
    details: Dict[str, Any]
    explanation: str
    audit_seqs: List[int]
    status: AlertStatus
    dedupe_key: str
    created_at: datetime
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None

    class Config:
        from_attributes = True


class AlertResolveRequest(BaseModel):
    resolution_note: str
