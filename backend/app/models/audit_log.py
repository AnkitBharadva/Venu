"""SQLAlchemy ORM models for source documents, tamper-evident audit log, and deliverables."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship

# Dialect-agnostic types with native PostgreSQL JSONB and UUID optimizations
UUID_TYPE = Uuid().with_variant(UUID(as_uuid=True), "postgresql")
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    doc_id = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    original_filename = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=False)
    checksum = Column(String(64), nullable=False, index=True)
    encrypted_file_path = Column(String(1024), nullable=False)
    raw_text = Column(Text, nullable=True)
    structural_metadata = Column(JSON_TYPE, default=dict)
    uploader_id = Column(String(128), nullable=False, default="operator_default", index=True)
    upload_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    outputs = relationship("GeneratedOutput", back_populates="source_document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="source_document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index")
    understanding = relationship("DocumentUnderstanding", back_populates="source_document", uselist=False, cascade="all, delete-orphan")


ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(ID_TYPE, primary_key=True, autoincrement=True)
    actor = Column(String(128), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    doc_id = Column(UUID_TYPE, ForeignKey("source_documents.doc_id", ondelete="SET NULL"), nullable=True, index=True)
    output_id = Column(UUID_TYPE, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    source_hash = Column(String(64), nullable=True)
    details = Column(JSON_TYPE, default=dict)
    prev_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False)


class GeneratedOutput(Base):
    __tablename__ = "generated_outputs"

    output_id = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID_TYPE, ForeignKey("source_documents.doc_id", ondelete="RESTRICT"), nullable=False, index=True)
    deliverable_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    content = Column(JSON_TYPE, nullable=False)
    citations = Column(JSON_TYPE, nullable=False, default=list)
    format_metadata = Column(JSON_TYPE, default=dict)
    encrypted_file_path = Column(String(1024), nullable=True)
    reviewer_id = Column(String(128), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    source_document = relationship("SourceDocument", back_populates="outputs")
    edit_history = relationship(
        "OutputEditHistory",
        back_populates="output",
        cascade="all, delete-orphan",
        order_by="OutputEditHistory.timestamp.asc()",
    )


class OutputEditHistory(Base):
    """Immutable audit diff record of every reviewer edit and sentence/section review action."""

    __tablename__ = "output_edit_history"

    id = Column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    output_id = Column(
        UUID_TYPE,
        ForeignKey("generated_outputs.output_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    actor = Column(String(128), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)  # 'edit_sentence', 'accept_sentence', 'reject_sentence', etc.
    target_type = Column(String(32), nullable=False)  # 'sentence', 'section', 'deliverable'
    target_id = Column(String(128), nullable=True)  # sentence_id or section_index
    target_index = Column(Integer, nullable=True)
    before_content = Column(Text, nullable=False)
    after_content = Column(Text, nullable=False)
    diff_summary = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    output = relationship("GeneratedOutput", back_populates="edit_history")

