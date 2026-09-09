"""Base parser interface and common data structures for ingestion pipeline."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ParsedContent(BaseModel):
    """Normalized content extracted from an ingested source file."""

    raw_text: str = Field(..., description="Normalized, readable extracted text")
    structural_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved structural units: headings, pages, timestamps, slide notes",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence metric (0.0 to 1.0)",
    )
    low_confidence: bool = Field(
        default=False,
        description="Flag indicating OCR/ASR uncertainty or degraded source quality",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic notes surfaced to the operator for human review",
    )


class BaseParser(ABC):
    """Abstract base class for modular document and media parsers."""

    @abstractmethod
    def can_handle(self, content_type: str, filename: str) -> bool:
        """Return True if this parser supports the given content type or file extension."""
        pass

    @abstractmethod
    async def parse(self, file_bytes: bytes, filename: str, content_type: str) -> ParsedContent:
        """Parse raw file bytes and return normalized text and structural metadata.

        Raises:
            ValueError: If file is corrupted, empty, or unparseable.
        """
        pass
