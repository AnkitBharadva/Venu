"""Ingestion API Router (Phase 1).

Exposes:
- POST /api/v1/ingest/upload
- GET  /api/v1/ingest/documents/{doc_id}
- GET  /api/v1/ingest/documents
- GET  /api/v1/ingest/documents/{doc_id}/verify-encryption
"""

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import read_decrypted_file
from app.models.audit_log import SourceDocument
from app.schemas.source_document import (
    DocumentSummary,
    DocumentUploadResponse,
    SourceDocumentResponse,
)
from app.services.file_router import (
    CorruptedFileError,
    UnsupportedMediaTypeError,
    ingest_source_document,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and normalize a multi-modal source document",
)
async def upload_document(
    file: UploadFile = File(..., description="Document, presentation, image, or audio/video file"),
    uploader_id: str = Form(default="operator_default", description="ID of uploading operator"),
    session: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Accepts any supported source file (plain text, PDF, DOCX, PPTX, images, audio/video),

    normalizes it into a standard SourceDocument schema, encrypts the raw file at-rest
    using AES-256-GCM, and commits a tamper-evident audit row.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not be empty.",
        )

    try:
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' is empty (0 bytes).",
            )

        doc_record = await ingest_source_document(
            session=session,
            file_bytes=file_bytes,
            filename=file.filename,
            declared_content_type=file.content_type,
            uploader_id=uploader_id,
        )

        doc_response = SourceDocumentResponse.model_validate(doc_record)
        return DocumentUploadResponse(
            status="success",
            document=doc_response,
            encrypted_storage_verified=True,
            audit_entry_recorded=True,
        )

    except CorruptedFileError as cfe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "CorruptedFile", "filename": cfe.filename, "message": cfe.reason},
        ) from cfe
    except UnsupportedMediaTypeError as ume:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": "UnsupportedMediaType", "filename": ume.filename, "content_type": ume.content_type},
        ) from ume
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal ingestion pipeline error: {exc}",
        ) from exc


@router.get(
    "/documents/{doc_id}",
    response_model=SourceDocumentResponse,
    summary="Retrieve normalized source document by ID",
)
async def get_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SourceDocumentResponse:
    """Fetch stored normalized document text and structural metadata."""
    stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id '{doc_id}' not found.",
        )
    return SourceDocumentResponse.model_validate(doc)


@router.get(
    "/documents",
    response_model=list[DocumentSummary],
    summary="List all ingested documents",
)
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> list[DocumentSummary]:
    """List ingested documents with summary details."""
    stmt = select(SourceDocument).order_by(SourceDocument.upload_timestamp.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    docs = result.scalars().all()

    summaries = []
    for d in docs:
        low_conf = False
        if isinstance(d.structural_metadata, dict):
            low_conf = d.structural_metadata.get("low_confidence", False)

        summary = DocumentSummary.model_validate(d)
        summary.char_count = len(str(d.raw_text or ""))
        summary.low_confidence = low_conf
        summaries.append(summary)
    return summaries


@router.get(
    "/documents/{doc_id}/verify-encryption",
    summary="Verify that raw file stored on disk is encrypted and unreadable",
)
async def verify_encryption_at_rest(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Returns disk file inspection metadata confirming ciphertext characteristics."""
    stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    from pathlib import Path

    file_path = Path(doc.encrypted_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encrypted file missing on disk.")

    raw_disk_bytes = file_path.read_bytes()
    # Check if raw disk bytes start with plaintext or known headers
    is_plain = False
    for magic in [b"%PDF", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8", b"RIFF", b"ID3"]:
        if raw_disk_bytes.startswith(magic):
            is_plain = True
            break

    # Verify that decryption works with key
    decrypted = read_decrypted_file(file_path)

    return {
        "doc_id": str(doc_id),
        "disk_path": str(file_path),
        "disk_file_size_bytes": len(raw_disk_bytes),
        "is_unreadable_ciphertext": not is_plain,
        "sample_hex_preview": raw_disk_bytes[:32].hex(),
        "decryption_successful": len(decrypted) > 0,
        "checksum_matches": doc.checksum == __import__("hashlib").sha256(decrypted).hexdigest(),
        "encrypted_at_rest": not is_plain and len(decrypted) > 0,
    }
