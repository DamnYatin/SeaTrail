"""
Audit log, chain verification, and checkpoint schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    seq: int
    ts: datetime
    actor_id: str | None = None
    actor_name: str | None = None
    actor_role: str | None = None
    action: str
    case_id: str | None = None
    case_number: str | None = None
    evidence_id: str | None = None
    evidence_number: str | None = None
    payload: dict[str, Any]
    ip: str | None = None
    prev_hash: str
    entry_hash: str

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    items: list[AuditEntryResponse]
    total: int
    head_seq: int
    chain_ok: bool


class AuditVerifyResponse(BaseModel):
    ok: bool
    checked: int
    head_seq: int
    head_hash: str
    first_broken_seq: int | None = None
    reason: str | None = None


class CheckpointResponse(BaseModel):
    id: str
    seq_to: int
    head_hash: str
    signature_b64: str
    public_key_id: str
    created_at: datetime
    created_by: str | None = None

    class Config:
        from_attributes = True


class SweepRunResponse(BaseModel):
    id: str
    kind: str
    started_by: str
    started_at: datetime
    finished_at: datetime | None = None
    total: int
    checked: int
    failed: int
    status: str

    class Config:
        from_attributes = True
