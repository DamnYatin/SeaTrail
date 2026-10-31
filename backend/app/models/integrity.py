"""
Integrity state singleton and evidence sweep run models.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.db import Base


class IntegrityRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IntegrityRunKind(str, enum.Enum):
    EVIDENCE_SWEEP = "EVIDENCE_SWEEP"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class IntegrityState(Base):
    """Singleton table caching current audit chain health."""
    __tablename__ = "integrity_state"

    id = Column(Integer, primary_key=True, default=1)
    last_chain_check_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    chain_ok = Column(Boolean, default=True, nullable=False)
    head_seq = Column(BigInteger, default=0, nullable=False)
    broken_seq = Column(BigInteger, nullable=True)
    broken_reason = Column(String(255), nullable=True)


class IntegrityRun(Base):
    """Tracks background evidence verification sweeps."""
    __tablename__ = "integrity_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    kind = Column(
        Enum(IntegrityRunKind),
        default=IntegrityRunKind.EVIDENCE_SWEEP,
        nullable=False,
    )
    started_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    total = Column(Integer, default=0, nullable=False)
    checked = Column(Integer, default=0, nullable=False)
    failed = Column(Integer, default=0, nullable=False)
    status = Column(
        Enum(IntegrityRunStatus),
        default=IntegrityRunStatus.PENDING,
        nullable=False,
    )
