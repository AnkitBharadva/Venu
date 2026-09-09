"""SQLAlchemy ORM models for Phase 2: Document Chunks and Document Understanding."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.audit_log import JSON_TYPE, UUID_TYPE, Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentChunk(Base):
    """Semantically coherent text span preserving exact character offsets and layout provenance."""

    __tablename__ = "document_chunks"

    chunk_id = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID_TYPE, ForeignKey("source_documents.doc_id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)
    char_offset_start = Column(Integer, nullable=False, index=True)
    char_offset_end = Column(Integer, nullable=False, index=True)
    page_number = Column(Integer, nullable=True)
    heading = Column(String(512), nullable=True)
    timestamp_start = Column(Float, nullable=True)
    timestamp_end = Column(Float, nullable=True)
    metadata_payload = Column(JSON_TYPE, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    source_document = relationship("SourceDocument", back_populates="chunks")


class DocumentUnderstanding(Base):
    """Structured understanding, entity extractions, and knowledge graph mappings."""

    __tablename__ = "document_understandings"

    id = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    doc_id = Column(
        UUID_TYPE,
        ForeignKey("source_documents.doc_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    objective = Column(Text, nullable=False)
    topics = Column(JSON_TYPE, default=list, nullable=False)
    key_entities = Column(JSON_TYPE, default=list, nullable=False)
    sensitive_terms = Column(JSON_TYPE, default=list, nullable=False)
    relationships = Column(JSON_TYPE, default=list, nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    source_document = relationship("SourceDocument", back_populates="understanding")
