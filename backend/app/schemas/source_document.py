"""Normalized SourceDocument schema and API request/response models."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StructuralMetadata(BaseModel):
    """Detailed structural metadata preserving document layout and multimedia segments."""

    model_config = ConfigDict(extra="allow")

    headings: list[dict[str, Any]] = Field(default_factory=list, description="Extracted headings and hierarchies")
    pages: list[dict[str, Any]] = Field(default_factory=list, description="Per-page content layout and offsets")
    timestamps: list[dict[str, Any]] = Field(default_factory=list, description="Audio/Video segment timestamps")
    total_pages: int | None = Field(default=None, description="Page or slide count")
    duration_seconds: float | None = Field(default=None, description="Audio or video duration")
    confidence_score: float = Field(default=1.0, description="Confidence score of extraction/transcription (0.0 - 1.0)")
    low_confidence: bool = Field(default=False, description="Flag indicating OCR/ASR uncertainty")
    warnings: list[str] = Field(default_factory=list, description="Parser and confidence warning notes")


class SourceDocumentResponse(BaseModel):
    """Normalized document schema as mandated by Phase 1 specification."""

    model_config = ConfigDict(from_attributes=True)

    doc_id: uuid.UUID = Field(..., description="Unique document identifier")
    original_filename: str = Field(..., description="Uploaded file name")
    content_type: str = Field(..., description="Normalized MIME content type")
    raw_text: str = Field(..., description="Clean, extracted normalized text")
    structural_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Headings, pages, timestamps, confidence metrics and low-confidence flags",
    )
    upload_timestamp: datetime = Field(..., description="UTC timestamp of file upload")
    uploader_id: str = Field(..., description="Identity of uploading operator")
    checksum: str = Field(..., description="SHA-256 cryptographic hash of raw input file")


class DocumentUploadResponse(BaseModel):
    """Response returned upon successful file ingestion."""

    status: str = Field(default="success")
    document: SourceDocumentResponse
    encrypted_storage_verified: bool = Field(
        default=True,
        description="True if raw file was verified encrypted at-rest on disk",
    )
    audit_entry_recorded: bool = Field(
        default=True,
        description="True if tamper-evident audit row was committed",
    )


class DocumentSummary(BaseModel):
    """Summary item for document listing."""

    model_config = ConfigDict(from_attributes=True)

    doc_id: uuid.UUID
    original_filename: str
    content_type: str
    upload_timestamp: datetime
    uploader_id: str
    checksum: str
    char_count: int = 0
    low_confidence: bool = False


class BatchUploadItem(BaseModel):
    """Result of an individual file in a batch upload."""

    filename: str
    status: str = "success"
    doc_id: uuid.UUID | None = None
    document: SourceDocumentResponse | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    """Aggregate response for multi-file batch upload."""

    status: str = "success"
    total_files: int
    successful_count: int
    failed_count: int
    items: list[BatchUploadItem]
