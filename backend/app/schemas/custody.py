"""
Custody transfer request and response schemas.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.models.custody import TransferStatus


class TransferCreate(BaseModel):
    to_user_id: Optional[str] = None
    to_location: str
    reason: str
    is_external: bool = False
    external_party: Optional[str] = None


class TransferResponse(BaseModel):
    id: str
    evidence_id: str
    evidence_number: Optional[str] = None
    item_name: Optional[str] = None
    from_user_id: str
    from_user_name: Optional[str] = None
    to_user_id: Optional[str] = None
    to_user_name: Optional[str] = None
    to_location: str
    reason: str
    is_external: bool
    external_party: Optional[str] = None
    status: TransferStatus
    approval_request_id: Optional[str] = None
    hash_at_send: str
    requested_at: datetime
    ack_due_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    hash_at_receipt: Optional[str] = None
    receipt_verified: Optional[bool] = None

    class Config:
        from_attributes = True


class TransferRejectRequest(BaseModel):
    reason: str
