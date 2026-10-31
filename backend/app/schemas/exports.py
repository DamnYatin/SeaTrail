"""
Export package schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ExportCreateRequest(BaseModel):
    justification: str = Field(..., min_length=10)
    include_bsa_certificate: bool = True
    encrypt: bool = False


class ExportBuildRequest(BaseModel):
    passphrase: Optional[str] = None


class ExportResponse(BaseModel):
    id: str
    evidence_id: str
    case_id: str
    approval_request_id: Optional[str] = None
    requested_by: str
    approved_by: Optional[str] = None
    encrypted: bool
    package_sha256: str
    package_size: int
    created_at: datetime
    download_count: int

    class Config:
        from_attributes = True
