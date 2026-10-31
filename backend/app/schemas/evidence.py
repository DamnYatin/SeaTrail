"""
Evidence request, response, and verification schemas.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from app.models.evidence import EvidenceStatus, EvidenceType, IntegrityStateEnum


class EvidenceVerificationInfo(BaseModel):
    server_sha256: str
    client_sha256: str | None = None
    readback_sha256: str
    match: bool


class EvidenceCreateMetadata(BaseModel):
    type: EvidenceType
    item_name: str
    description: str | None = None
    source_description: str | None = None
    collected_by_user_id: str | None = None
    collected_at: datetime | None = None
    acquisition_method: str | None = None
    acquisition_tool: str | None = None
    device_make: str | None = None
    device_model: str | None = None
    device_serial: str | None = None
    parent_evidence_id: str | None = None
    current_location: str | None = "Evidence Locker A"


class EvidenceResponse(BaseModel):
    id: str
    evidence_number: str
    case_id: str
    case_number: str | None = None
    case_name: str | None = None
    parent_evidence_id: str | None = None
    type: EvidenceType
    item_name: str
    description: str | None = None
    source_description: str | None = None
    collected_by_user_id: str
    collected_by_name: str | None = None
    collected_at: datetime
    acquisition_method: str | None = None
    acquisition_tool: str | None = None
    device_make: str | None = None
    device_model: str | None = None
    device_serial: str | None = None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    client_sha256: str | None = None
    storage_bucket: str
    storage_key: str
    storage_version_id: str | None = None
    intake_at: datetime
    intake_by: str
    current_custodian_id: str
    current_custodian_name: str | None = None
    current_location: str
    status: EvidenceStatus
    integrity_state: IntegrityStateEnum
    last_verified_at: datetime
    legal_hold: bool
    retention_until: date | None = None
    label_print_count: int
    disposed_at: datetime | None = None
    verification: EvidenceVerificationInfo | None = None

    class Config:
        from_attributes = True


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EvidenceVerifyResponse(BaseModel):
    status: IntegrityStateEnum
    match: bool
    pinned_object_hash: str | None
    live_object_hash: str | None
    object_replaced: bool
    audit_hash_match: bool
    details: dict[str, Any]
