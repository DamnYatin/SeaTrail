"""
Audit log, chain verification, and checkpoint schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    seq: int
    ts: datetime
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    case_id: Optional[str] = None
    case_number: Optional[str] = None
    evidence_id: Optional[str] = None
    evidence_number: Optional[str] = None
    payload: Dict[str, Any]
    ip: Optional[str] = None
    prev_hash: str
    entry_hash: str

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    items: List[AuditEntryResponse]
    total: int
    head_seq: int
    chain_ok: bool


class AuditVerifyResponse(BaseModel):
    ok: bool
    checked: int
    head_seq: int
    head_hash: str
    first_broken_seq: Optional[int] = None
    reason: Optional[str] = None


class CheckpointResponse(BaseModel):
    id: str
    seq_to: int
    head_hash: str
    signature_b64: str
    public_key_id: str
    created_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class SweepRunResponse(BaseModel):
    id: str
    kind: str
    started_by: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    total: int
    checked: int
    failed: int
    status: str

    class Config:
        from_attributes = True
