"""Pydantic schemas for Phase 5: Review, Approval, Export & Encryption Verification."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RequestApprovalRequest(BaseModel):
    """Operator request to submit a deliverable for formal reviewer approval."""

    notes: str | None = Field(default=None, description="Operator notes or context for reviewer")


class ApprovalActionRequest(BaseModel):
    """Reviewer decision payload for approving or rejecting a deliverable."""

    reviewer_notes: str | None = Field(
        default=None,
        description="Reviewer rationale, compliance notes, or rejection reason",
    )


class ExportDeliverableRequest(BaseModel):
    """Request payload to export an approved deliverable in a standard format."""

    export_format: str = Field(
        default="markdown",
        description="Target export format: markdown, json, html, or text",
    )


class ExportDeliverableResponse(BaseModel):
    """Export result containing rendered content, cryptographic checksum, and encrypted file path."""

    output_id: uuid.UUID
    doc_id: uuid.UUID
    deliverable_type: str
    export_format: str
    exported_filename: str
    checksum_sha256: str
    exported_content: str
    encrypted_export_path: str
    export_timestamp: datetime
    actor: str
    audit_logged: bool = True


class OutputEncryptionVerificationResponse(BaseModel):
    """Verification proof confirming that an output deliverable is encrypted at rest using AES-256-GCM."""

    model_config = ConfigDict(extra="ignore")

    output_id: uuid.UUID
    verified: bool
    encrypted_at_rest: bool
    algorithm: str = "AES-256-GCM"
    file_path: str
    file_size_bytes: int | None = None
    ciphertext_sha256: str | None = None
    deliverable_type: str | None = None
    status: str | None = None
    error: str | None = None


class EditSentenceRequest(BaseModel):
    """Reviewer edit payload for modifying a specific sentence with diff tracking."""

    sentence_id: str = Field(..., description="ID of the sentence being modified (e.g. sent_0_1)")
    new_text: str = Field(..., min_length=1, description="Replacement text for the sentence")
    notes: str | None = Field(default=None, description="Reviewer justification or editorial notes")


class ReviewSentenceRequest(BaseModel):
    """Reviewer decision payload for accepting or rejecting a single sentence."""

    sentence_id: str = Field(..., description="ID of the sentence being reviewed")
    decision: str = Field(..., description="'accept' or 'reject'")
    notes: str | None = Field(default=None, description="Reviewer comments or compliance notes")


class ReviewSectionRequest(BaseModel):
    """Reviewer decision payload for accepting or rejecting an entire content block."""

    block_index: int = Field(..., ge=0, description="Zero-based index of the section/block")
    decision: str = Field(..., description="'accept' or 'reject'")
    notes: str | None = Field(default=None, description="Reviewer comments or compliance notes")


class EditHistoryItemResponse(BaseModel):
    """Individual audit diff item showing before/after state and unified diff."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    output_id: uuid.UUID
    version: int
    actor: str
    action: str
    target_type: str
    target_id: str | None = None
    target_index: int | None = None
    before_content: str
    after_content: str
    diff_summary: str | None = None
    timestamp: datetime


class OutputReviewSummaryResponse(BaseModel):
    """Reviewer summary metrics for a deliverable."""

    output_id: uuid.UUID
    status: str
    total_sentences: int
    accepted_sentences: int
    rejected_sentences: int
    edited_sentences: int
    pending_sentences: int
    can_export: bool
    history_count: int

