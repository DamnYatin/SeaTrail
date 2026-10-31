"""
Case management, memberships, and retention policy models.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CaseClassification(str, enum.Enum):
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"
    INTERNAL = "INTERNAL"


class CaseMemberRole(str, enum.Enum):
    LEAD = "LEAD"
    MEMBER = "MEMBER"
    OBSERVER = "OBSERVER"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(timezone.utc)


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    retain_days = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_number = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(CaseStatus), default=CaseStatus.OPEN, nullable=False)
    classification = Column(
        Enum(CaseClassification),
        default=CaseClassification.CONFIDENTIAL,
        nullable=False,
    )
    lead_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    evidence_counter = Column(Integer, default=0, nullable=False)
    legal_hold = Column(Boolean, default=False, nullable=False)
    legal_hold_reason = Column(Text, nullable=True)
    retention_policy_id = Column(String(36), ForeignKey("retention_policies.id"), nullable=True)
    opened_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)

    members = relationship("CaseMember", back_populates="case", cascade="all, delete-orphan")


class CaseMember(Base):
    __tablename__ = "case_members"

    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    case_role = Column(Enum(CaseMemberRole), default=CaseMemberRole.MEMBER, nullable=False)
    added_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="members")
