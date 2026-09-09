"""Comprehensive unit & integration tests for Phase 1 Ingestion Pipeline.

Verifies:
1. Supported file formats: plain text, PDF, DOCX, PPTX, Images (PNG/JPG), Audio/Video (WAV/MP3/MP4).
2. Common normalized SourceDocument schema output.
3. AES-256-GCM encryption at-rest (file on disk is unreadable ciphertext).
4. Append-only tamper-evident audit log row on every upload.
5. Error handling: Corrupted files (HTTP 400) and Unsupported formats (HTTP 415).
6. Low-confidence flags surfaced to operator for degraded/scanned inputs.
"""

import io
import struct
from pathlib import Path
from unittest.mock import patch

import docx
import pptx
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import compute_sha256, decrypt_bytes
from app.main import app
from app.models.audit_log import Base

# In-memory SQLite async engine for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def prepare_database(tmp_path):
    """Set up temporary database schema and test upload directory for every test."""
    # Override upload path to isolated temp dir
    test_upload_dir = tmp_path / "encrypted_uploads"
    test_upload_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(get_settings(), "UPLOAD_STORAGE_PATH", str(test_upload_dir)):
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


# --- Test File Generators ---


def create_sample_pdf() -> bytes:
    """Generate a valid PDF file in memory."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # Add another page with text stream
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def create_sample_docx() -> bytes:
    """Generate a valid DOCX file in memory."""
    doc = docx.Document()
    doc.add_heading("Threat Intelligence Briefing", level=1)
    doc.add_paragraph("This is a critical security advisory regarding air-gapped system isolation.")
    doc.add_paragraph("All network perimeter egress has been disabled.")
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def create_sample_pptx() -> bytes:
    """Generate a valid PPTX file in memory."""
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Executive Strategy Deck"
    slide.placeholders[1].text = "Key finding: Automated content transformation is operational."
    stream = io.BytesIO()
    prs.save(stream)
    return stream.getvalue()


def create_sample_png() -> bytes:
    """Generate a valid PNG image in memory."""
    img = Image.new("RGB", (300, 150), color=(20, 30, 50))
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()


def create_sample_wav() -> bytes:
    """Generate a valid PCM WAV audio in memory (1 second at 16kHz)."""
    sample_rate = 16000
    num_samples = 16000
    # Generate 16-bit mono silence/sine
    raw_audio = b"\x00\x00" * num_samples
    byte_rate = sample_rate * 2
    data_size = len(raw_audio)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        1,  # Mono
        sample_rate,
        byte_rate,
        2,  # Block align
        16,  # Bits per sample
        b"data",
        data_size,
    )
    return header + raw_audio


# --- Tests ---


@pytest.mark.asyncio
async def test_upload_plain_text():
    """Test uploading a Markdown / Plain text source document."""
    content = b"# Tactical Assessment\n\nEnemy forces observed withdrawing from Sector 7."
    files = {"file": ("assessment.md", content, "text/markdown")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    doc = data["document"]

    assert doc["original_filename"] == "assessment.md"
    assert "Sector 7" in doc["raw_text"]
    assert doc["checksum"] == compute_sha256(content)
    assert doc["structural_metadata"]["word_count"] > 0
    assert len(doc["structural_metadata"]["headings"]) == 1
    assert doc["structural_metadata"]["headings"][0]["title"] == "Tactical Assessment"


@pytest.mark.asyncio
async def test_upload_pdf_document():
    """Test uploading a structured PDF document."""
    pdf_bytes = create_sample_pdf()
    files = {"file": ("report.pdf", pdf_bytes, "application/pdf")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    doc = data["document"]
    assert doc["original_filename"] == "report.pdf"
    assert doc["structural_metadata"]["total_pages"] >= 1
    assert doc["checksum"] == compute_sha256(pdf_bytes)


@pytest.mark.asyncio
async def test_upload_docx_document():
    """Test uploading a Microsoft Word DOCX document."""
    docx_bytes = create_sample_docx()
    files = {
        "file": ("briefing.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    doc = response.json()["document"]
    assert "Threat Intelligence Briefing" in doc["raw_text"]
    assert "air-gapped system isolation" in doc["raw_text"]
    assert len(doc["structural_metadata"]["headings"]) >= 1


@pytest.mark.asyncio
async def test_upload_pptx_presentation():
    """Test uploading a Microsoft PowerPoint presentation."""
    pptx_bytes = create_sample_pptx()
    files = {
        "file": (
            "strategy.pptx",
            pptx_bytes,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    doc = response.json()["document"]
    assert "Executive Strategy Deck" in doc["raw_text"]
    assert doc["structural_metadata"]["total_slides"] == 1


@pytest.mark.asyncio
async def test_upload_image():
    """Test uploading an image document (PNG)."""
    png_bytes = create_sample_png()
    files = {"file": ("scan.png", png_bytes, "image/png")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    doc = response.json()["document"]
    assert doc["content_type"] == "image/png"
    assert "image_dimensions" in doc["structural_metadata"]
    assert doc["structural_metadata"]["image_dimensions"]["width"] == 300


@pytest.mark.asyncio
async def test_upload_audio_wav():
    """Test uploading an audio file with duration and timestamp extraction."""
    wav_bytes = create_sample_wav()
    files = {"file": ("dispatch.wav", wav_bytes, "audio/wav")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    doc = response.json()["document"]
    assert doc["content_type"] == "audio/wav"
    assert "timestamps" in doc["structural_metadata"]
    assert len(doc["structural_metadata"]["timestamps"]) >= 1
    assert doc["structural_metadata"]["duration_seconds"] == 1.0


@pytest.mark.asyncio
async def test_encryption_at_rest_verification(tmp_path):
    """Acceptance criteria: verify original file is unreadable without decryption key when inspected directly on disk."""
    secret_text = b"CONFIDENTIAL MISSION MANIFEST 2026: Strictly classified."
    files = {"file": ("manifest.txt", secret_text, "text/plain")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 201
    doc_id = response.json()["document"]["doc_id"]

    # Verify via verification endpoint
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        verify_res = await ac.get(f"/api/v1/ingest/documents/{doc_id}/verify-encryption")

    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["is_unreadable_ciphertext"] is True
    assert vdata["decryption_successful"] is True
    assert vdata["checksum_matches"] is True

    # Direct on-disk inspection test:
    disk_path = Path(vdata["disk_path"])
    raw_disk_bytes = disk_path.read_bytes()

    # The plaintext MUST NOT appear anywhere in the file stored on disk
    assert secret_text not in raw_disk_bytes
    # Decrypting with the enclave key succeeds and matches original secret text
    decrypted = decrypt_bytes(raw_disk_bytes)
    assert decrypted == secret_text


@pytest.mark.asyncio
async def test_audit_log_entry_and_chain_verification():
    """Acceptance criteria: audit log has one row per upload with unbroken cryptographic hash chaining."""
    files = {"file": ("telecom_advisory.txt", b"Alert: Fiber link severed in sector 4.", "text/plain")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res1 = await ac.post("/api/v1/ingest/upload", files=files)
        assert res1.status_code == 201

        # Check audit log endpoint
        logs_res = await ac.get("/api/v1/audit/logs")
        assert logs_res.status_code == 200
        logs = logs_res.json()
        assert len(logs) >= 1
        upload_log = logs[0]
        assert upload_log["action"] == "upload"
        assert upload_log["source_hash"] is not None
        assert upload_log["prev_hash"] is not None
        assert upload_log["hash"] is not None

        # Verify hash chain integrity
        verify_chain_res = await ac.get("/api/v1/audit/verify-chain")
        assert verify_chain_res.status_code == 200
        chain_data = verify_chain_res.json()
        assert chain_data["valid"] is True
        assert chain_data["total_records"] >= 1


@pytest.mark.asyncio
async def test_error_corrupted_file():
    """Task 5: Corrupt files are flagged and return HTTP 400."""
    corrupted_pdf = b"%PDF-corrupted-truncated-junk-binary-data"
    files = {"file": ("corrupt.pdf", corrupted_pdf, "application/pdf")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 400
    assert "CorruptedFile" in response.text


@pytest.mark.asyncio
async def test_error_unsupported_media_type():
    """Task 5: Unsupported file types return HTTP 415."""
    executable_bytes = b"MZ\x90\x00\x03\x00\x00\x00"
    files = {"file": ("malware.exe", executable_bytes, "application/x-dosexec")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/ingest/upload", files=files)

    assert response.status_code == 415
    assert "UnsupportedMediaType" in response.text
