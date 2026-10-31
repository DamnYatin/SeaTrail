"""
Custody report schemas.
"""

from typing import Any

from pydantic import BaseModel


class ReportVerifyRequest(BaseModel):
    report: dict[str, Any]


class ReportVerifyResponse(BaseModel):
    valid: bool
    signature_valid: bool
    report_hash_valid: bool
    audit_entries_match: bool
    details: dict[str, Any] = {}
