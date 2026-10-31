"""
Custody report schemas.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ReportVerifyRequest(BaseModel):
    report: Dict[str, Any]


class ReportVerifyResponse(BaseModel):
    valid: bool
    signature_valid: bool
    report_hash_valid: bool
    audit_entries_match: bool
    details: Dict[str, Any] = {}
