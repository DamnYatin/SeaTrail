"""
Collaboration and linking models: Annotations, People, Case Events, Case Notes, and Evidence Links.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


class PersonRole(str, enum.Enum):
    SUSPECT = "SUSPECT"
    WITNESS = "WITNESS"
    VICTIM = "VICTIM"
    INVESTIGATOR = "INVESTIGATOR"
    EXPERT = "EXPERT"
    OTHER = "OTHER"


class LinkTargetType(str, enum.Enum):
    PERSON = "PERSON"
    EVENT = "EVENT"
    NOTE = "NOTE"
    EVIDENCE = "EVIDENCE"


def generate_uuid():
    return str(uuid.uuid4())


def utc_now():
    return datetime.now(UTC)


class Annotation(Base):
    """Append-only evidence annotations."""

    __tablename__ = "annotations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    body_sha256 = Column(String(64), nullable=False)
    parent_annotation_id = Column(String(36), ForeignKey("annotations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    author = relationship("User")


class Person(Base):
    """Persons of interest linked to cases."""

    __tablename__ = "people"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    role_in_case = Column(Enum(PersonRole), default=PersonRole.OTHER, nullable=False)
    contact = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class CaseEvent(Base):
    """Case milestone events forming the incident timeline."""

    __tablename__ = "case_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class CaseNote(Base):
    """Append-only case investigation notes."""

    __tablename__ = "case_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=True)
    body = Column(Text, nullable=False)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    author = relationship("User")


class EvidenceLink(Base):
    """Links connecting evidence to people, events, notes, or other evidence."""

    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "evidence_id",
            "target_type",
            "target_id",
            "relation",
            name="uq_evidence_link",
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=False, index=True)
    target_type = Column(Enum(LinkTargetType), nullable=False)
    target_id = Column(String(36), nullable=False, index=True)
    relation = Column(String(100), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(36), ForeignKey("users.id"), nullable=True)
