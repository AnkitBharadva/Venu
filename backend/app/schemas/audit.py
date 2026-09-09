"""Audit log and hash-chain verification schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Schema representing an immutable audit log record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str
    action: str
    doc_id: uuid.UUID | None = None
    output_id: uuid.UUID | None = None
    timestamp: datetime
    source_hash: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str


class AuditVerificationResponse(BaseModel):
    """Result of full cryptographic hash chain verification."""

    valid: bool
    total_records: int
    latest_hash: str | None = None
    status: str
    error: str | None = None
    record_id: int | None = None
