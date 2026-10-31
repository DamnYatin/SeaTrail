"""
Evidence request, response, and verification schemas.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.models.evidence import EvidenceStatus, EvidenceType, IntegrityStateEnum


class EvidenceVerificationInfo(BaseModel):
    server_sha256: str
    client_sha256: Optional[str] = None
    readback_sha256: str
    match: bool


class EvidenceCreateMetadata(BaseModel):
    type: EvidenceType
    item_name: str
    description: Optional[str] = None
    source_description: Optional[str] = None
    collected_by_user_id: Optional[str] = None
    collected_at: Optional[datetime] = None
    acquisition_method: Optional[str] = None
    acquisition_tool: Optional[str] = None
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    device_serial: Optional[str] = None
    parent_evidence_id: Optional[str] = None
    current_location: Optional[str] = "Evidence Locker A"


class EvidenceResponse(BaseModel):
    id: str
    evidence_number: str
    case_id: str
    case_number: Optional[str] = None
    case_name: Optional[str] = None
    parent_evidence_id: Optional[str] = None
    type: EvidenceType
    item_name: str
    description: Optional[str] = None
    source_description: Optional[str] = None
    collected_by_user_id: str
    collected_by_name: Optional[str] = None
    collected_at: datetime
    acquisition_method: Optional[str] = None
    acquisition_tool: Optional[str] = None
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    device_serial: Optional[str] = None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    client_sha256: Optional[str] = None
    storage_bucket: str
    storage_key: str
    storage_version_id: Optional[str] = None
    intake_at: datetime
    intake_by: str
    current_custodian_id: str
    current_custodian_name: Optional[str] = None
    current_location: str
    status: EvidenceStatus
    integrity_state: IntegrityStateEnum
    last_verified_at: datetime
    legal_hold: bool
    retention_until: Optional[date] = None
    label_print_count: int
    disposed_at: Optional[datetime] = None
    verification: Optional[EvidenceVerificationInfo] = None

    class Config:
        from_attributes = True


class EvidenceListResponse(BaseModel):
    items: List[EvidenceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EvidenceVerifyResponse(BaseModel):
    status: IntegrityStateEnum
    match: bool
    pinned_object_hash: Optional[str]
    live_object_hash: Optional[str]
    object_replaced: bool
    audit_hash_match: bool
    details: Dict[str, Any]
