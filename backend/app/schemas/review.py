"""Pydantic schemas for Phase 5: Review, Approval, Export & Encryption Verification."""

import uuid
from datetime import datetime
from typing import Any

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
