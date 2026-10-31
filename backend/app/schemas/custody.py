"""
Custody transfer request and response schemas.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.custody import TransferStatus


class TransferCreate(BaseModel):
    to_user_id: str | None = None
    to_location: str
    reason: str
    is_external: bool = False
    external_party: str | None = None


class TransferResponse(BaseModel):
    id: str
    evidence_id: str
    evidence_number: str | None = None
    item_name: str | None = None
    from_user_id: str
    from_user_name: str | None = None
    to_user_id: str | None = None
    to_user_name: str | None = None
    to_location: str
    reason: str
    is_external: bool
    external_party: str | None = None
    status: TransferStatus
    approval_request_id: str | None = None
    hash_at_send: str
    requested_at: datetime
    ack_due_at: datetime | None = None
    acknowledged_at: datetime | None = None
    hash_at_receipt: str | None = None
    receipt_verified: bool | None = None

    class Config:
        from_attributes = True


class TransferRejectRequest(BaseModel):
    reason: str
