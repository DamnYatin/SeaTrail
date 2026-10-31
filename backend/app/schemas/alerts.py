"""
Security anomaly alerts request and response schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.alerts import AlertSeverity, AlertStatus


class AlertResponse(BaseModel):
    id: str
    rule: str
    severity: AlertSeverity
    case_id: str | None = None
    case_number: str | None = None
    evidence_id: str | None = None
    evidence_number: str | None = None
    details: dict[str, Any]
    explanation: str
    audit_seqs: list[int]
    status: AlertStatus
    dedupe_key: str
    created_at: datetime
    acknowledged_by: str | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None

    class Config:
        from_attributes = True


class AlertResolveRequest(BaseModel):
    resolution_note: str
