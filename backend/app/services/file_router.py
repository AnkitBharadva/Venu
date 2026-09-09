"""File-Type Router and Ingestion Service for Multi-Modal Sources."""

import mimetypes
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.config import get_settings
from app.core.security import compute_sha256, save_encrypted_file
from app.models.audit_log import SourceDocument
from app.services.parsers.base import BaseParser, ParsedContent
from app.services.parsers.docling_parser import DoclingParser
from app.services.parsers.ocr_parser import OCRParser
from app.services.parsers.text_parser import TextParser
from app.services.parsers.whisper_parser import WhisperParser


class UnsupportedMediaTypeError(Exception):
    """Raised when an uploaded file format is not supported by the enclave."""

    def __init__(self, content_type: str, filename: str):
        super().__init__(f"Unsupported media type '{content_type}' for file '{filename}'.")
        self.content_type = content_type
        self.filename = filename


class CorruptedFileError(Exception):
    """Raised when an uploaded file is damaged, truncated, or unparseable."""

    def __init__(self, filename: str, reason: str):
        super().__init__(f"Corrupted or invalid file '{filename}': {reason}")
        self.filename = filename
        self.reason = reason


class FileRouter:
    """Detects content type and dispatches to Docling, PaddleOCR, Whisper, or Text parser."""

    def __init__(self):
        self.parsers: list[BaseParser] = [
            DoclingParser(),
            OCRParser(),
            WhisperParser(),
            TextParser(),
        ]

    def detect_content_type(self, file_bytes: bytes, filename: str, declared_type: str | None) -> str:
        """Inspect file magic bytes and filename extension to determine true MIME type."""
        lowered = filename.lower()

        # Magic signature inspection
        if file_bytes.startswith(b"%PDF"):
            return "application/pdf"
        elif file_bytes.startswith(b"PK\x03\x04"):
            if lowered.endswith((".docx", ".doc")):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if lowered.endswith((".pptx", ".ppt")):
                return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        elif file_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        elif file_bytes.startswith(b"RIFF") and b"WAVE" in file_bytes[:16]:
            return "audio/wav"
        elif file_bytes.startswith(b"ID3") or (
            len(file_bytes) > 2 and file_bytes[0] == 0xFF and (file_bytes[1] & 0xE0) == 0xE0
        ):
            return "audio/mpeg"
        elif b"ftyp" in file_bytes[:32]:
            return "video/mp4"

        # Fallback to declared content type if valid
        if declared_type and declared_type != "application/octet-stream":
            return declared_type

        # Guess from extension
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed

        if lowered.endswith((".md", ".markdown")):
            return "text/markdown"
        if lowered.endswith(".txt"):
            return "text/plain"

        return "application/octet-stream"

    async def route_and_parse(
        self, file_bytes: bytes, filename: str, declared_type: str | None = None
    ) -> tuple[str, ParsedContent]:
        """Determine file type, select appropriate parser, and extract normalized content."""
        content_type = self.detect_content_type(file_bytes, filename, declared_type)

        matched_parser: BaseParser | None = None
        for parser in self.parsers:
            if parser.can_handle(content_type, filename):
                matched_parser = parser
                break

        if not matched_parser:
            raise UnsupportedMediaTypeError(content_type, filename)

        try:
            parsed = await matched_parser.parse(file_bytes, filename, content_type)
            return content_type, parsed
        except ValueError as val_err:
            raise CorruptedFileError(filename, str(val_err)) from val_err
        except Exception as exc:
            raise CorruptedFileError(filename, f"Extraction failed: {exc}") from exc


# Global router instance
ingestion_router = FileRouter()


async def ingest_source_document(
    session: AsyncSession,
    file_bytes: bytes,
    filename: str,
    declared_content_type: str | None = None,
    uploader_id: str = "operator_default",
) -> SourceDocument:
    """Full Ingestion Pipeline (Phase 1):

    1. Validates non-empty payload.
    2. Computes SHA-256 checksum.
    3. Normalizes and parses content via FileRouter (Docling / PaddleOCR / Whisper / Text).
    4. Encrypts file at-rest (AES-256) and stores on disk.
    5. Appends tamper-evident audit record to Postgres audit_log.
    6. Persists SourceDocument record in database.
    """
    if not file_bytes:
        raise CorruptedFileError(filename, "File is completely empty (0 bytes).")

    settings = get_settings()

    # Step 1: Compute raw input file checksum
    checksum = compute_sha256(file_bytes)
    doc_id = uuid.uuid4()

    # Step 2: Route and extract normalized text + structural metadata
    content_type, parsed_content = await ingestion_router.route_and_parse(
        file_bytes=file_bytes,
        filename=filename,
        declared_type=declared_content_type,
    )

    # Step 3: Encrypt file at rest (AES-256-GCM) before writing to disk
    storage_dir = Path(settings.UPLOAD_STORAGE_PATH)
    storage_dir.mkdir(parents=True, exist_ok=True)
    target_path = storage_dir / f"{doc_id}.enc"
    encrypted_file_path = save_encrypted_file(file_bytes, target_path)

    # Enrich metadata with parser and confidence metrics
    metadata = dict(parsed_content.structural_metadata)
    metadata["confidence_score"] = parsed_content.confidence_score
    metadata["low_confidence"] = parsed_content.low_confidence
    metadata["warnings"] = parsed_content.warnings

    # Step 4: Persist SourceDocument in PostgreSQL
    doc_record = SourceDocument(
        doc_id=doc_id,
        original_filename=filename,
        content_type=content_type,
        checksum=checksum,
        encrypted_file_path=encrypted_file_path,
        raw_text=parsed_content.raw_text,
        structural_metadata=metadata,
        uploader_id=uploader_id,
    )
    session.add(doc_record)
    await session.flush()

    # Step 5: Append tamper-evident audit log entry (Task 4)
    audit_details = {
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": len(file_bytes),
        "parser": metadata.get("parser"),
        "confidence_score": parsed_content.confidence_score,
        "low_confidence": parsed_content.low_confidence,
        "warnings_count": len(parsed_content.warnings),
    }

    await record_audit_event(
        session=session,
        actor=uploader_id,
        action="upload",
        doc_id=doc_id,
        source_hash=checksum,
        details=audit_details,
    )

    await session.commit()
    await session.refresh(doc_record)
    return doc_record
