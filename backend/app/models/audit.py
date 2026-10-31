"""
Append-only hash-chained audit log and signed checkpoints models.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, JSON, String, Text

from app.db import Base


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """
    Append-only cryptographic hash-chained audit log.
    Every row commits in the same transaction as the corresponding state mutation.
    """
    __tablename__ = "audit_log"

    seq = Column(BigInteger, primary_key=True, autoincrement=False)
    ts = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=True, index=True)
    payload = Column(JSON, nullable=False)
    ip = Column(String(45), nullable=True)
    prev_hash = Column(String(64), nullable=False)
    entry_hash = Column(String(64), nullable=False, index=True)


class AuditCheckpoint(Base):
    """
    Append-only cryptographic checkpoints signed with Ed25519.
    Provides external cryptographic binding across sequence numbers.
    """
    __tablename__ = "audit_checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    seq_to = Column(BigInteger, nullable=False, index=True)
    head_hash = Column(String(64), nullable=False)
    signature_b64 = Column(Text, nullable=False)
    public_key_id = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
