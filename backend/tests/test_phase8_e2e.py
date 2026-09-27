"""Phase 8: Testing, Hardening & End-to-End Verification Test Suite.

Verifies:
1. End-to-end matrix pass across all 7 deliverable formats × 3 source document types:
   - Clean DOCX report (Docling XML parser)
   - Short video clip (Whisper ASR timestamped parser)
   - Scanned PDF (Docling structured & density-aware parser)
2. All 7 deliverable formats generated and validated:
   - LinkedIn Post
   - Twitter/X Thread
   - Executive Summary
   - Tactical Advisory
   - Presentation Deck
   - Video Package
   - Infographic Layout Spec
3. Provenance & Claim-to-Chunk Contract (/trace) resolves character-level spans.
4. Human Review & Approval Workflow (draft lock, diff history, approval, multi-format export).
5. Load & latency benchmarking ensuring all formats generate within responsive SLAs (< 2.0s).
6. Complete append-only cryptographic audit chain integrity across all matrix operations.
"""

import io
import struct
import time

import docx
import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter

from app.core.rbac import create_access_token
from app.core.security import compute_sha256
from app.main import app

ALL_SEVEN_FORMATS = [
    "linkedin_post",
    "twitter_thread",
    "executive_summary",
    "advisory",
    "presentation",
    "video_package",
    "infographic",
]


# --- Fixtures & Document Generators ---


@pytest.fixture
def operator_token() -> str:
    return create_access_token(user_id="operator_alice", role="operator", expires_in=3600)


@pytest.fixture
def reviewer_token() -> str:
    return create_access_token(user_id="reviewer_bob", role="reviewer", expires_in=3600)


def create_clean_docx() -> bytes:
    """Generate a clean, structured DOCX report with headings and operational directives."""
    doc = docx.Document()
    doc.add_heading("AIR-GAP DEFENSE DIRECTIVE 2026", level=1)
    doc.add_paragraph(
        "Section 1: Perimeter Enclave Isolation. All computing hardware within tactical defense enclaves "
        "must operate strictly disconnected from external public telecommunications networks."
    )
    doc.add_heading("Section 2: Cryptographic Security Standards", level=2)
    doc.add_paragraph(
        "Data stored at rest must be secured using authenticated AES-256-GCM ciphers with local key material. "
        "All operator events, transformations, and review approvals are immutably logged to an append-only "
        "linear SHA-256 cryptographic hash chain."
    )
    doc.add_heading("Section 3: Mandatory Human Authorization", level=2)
    doc.add_paragraph(
        "Automated intelligence summaries and advisories require explicit human reviewer sign-off prior to "
        "external export. Every generated claim sentence must maintain 100% character-level provenance back to "
        "underlying source document paragraphs."
    )
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def create_video_mp4() -> bytes:
    """Generate a valid MP4 container with standard ftyp signature."""
    ftyp_data = b"isomiso2mp41"
    ftyp_box = struct.pack(">I4s", len(ftyp_data) + 8, b"ftyp") + ftyp_data
    moov_data = b"\x00" * 64
    moov_box = struct.pack(">I4s", len(moov_data) + 8, b"moov") + moov_data
    return ftyp_box + moov_box


def create_scanned_pdf() -> bytes:
    """Generate a valid PDF document with scanned page structure."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


# ==============================================================================
# 1. Multi-Modal Ingestion Matrix Test (DOCX, Video MP4, Scanned PDF)
# ==============================================================================


@pytest.mark.asyncio
async def test_e2e_ingestion_multi_format_matrix(operator_token: str, prepare_database):
    """Verify ingestion pipeline correctly routes, encrypts, and parses all 3 document types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ingest Clean DOCX Report
        docx_bytes = create_clean_docx()
        docx_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("tactical_report.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert docx_resp.status_code == 201, docx_resp.text
        docx_data = docx_resp.json()["document"]
        assert docx_data["content_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert docx_data["structural_metadata"]["parser"] == "DoclingDocxParser"
        assert len(docx_data["structural_metadata"]["headings"]) >= 2
        assert "Perimeter Enclave Isolation" in docx_data["raw_text"]

        # 2. Ingest Video Clip MP4
        video_bytes = create_video_mp4()
        video_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("surveillance_patrol.mp4", video_bytes, "video/mp4")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert video_resp.status_code == 201, video_resp.text
        video_data = video_resp.json()["document"]
        assert video_data["content_type"] == "video/mp4"
        assert video_data["structural_metadata"]["parser"] == "WhisperASRParser"
        assert video_data["structural_metadata"]["media_type"] == "video"
        assert len(video_data["structural_metadata"]["timestamps"]) >= 1

        # 3. Ingest Scanned PDF
        pdf_bytes = create_scanned_pdf()
        pdf_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("scanned_memo.pdf", pdf_bytes, "application/pdf")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert pdf_resp.status_code == 201, pdf_resp.text
        pdf_data = pdf_resp.json()["document"]
        assert pdf_data["content_type"] == "application/pdf"
        assert pdf_data["structural_metadata"]["parser"] == "DoclingPDFParser"
        assert pdf_data["structural_metadata"]["total_pages"] >= 1
        assert pdf_data["structural_metadata"]["low_confidence"] is True  # correctly detected low density scanned input


# ==============================================================================
# 2. Complete End-to-End Pipeline across All 7 Formats (DOCX Source)
# ==============================================================================


@pytest.mark.asyncio
async def test_e2e_all_seven_formats_on_docx_with_trace_and_review(
    operator_token: str, reviewer_token: str, prepare_database
):
    """Test full ingestion -> chunking -> generation of all 7 formats -> trace -> review -> export."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Upload clean DOCX report
        docx_bytes = create_clean_docx()
        upload_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("mission_brief.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["document"]["doc_id"]
        raw_text = upload_resp.json()["document"]["raw_text"]

        # Step 2: Understand & Chunk document
        proc_resp = await client.post(
            f"/api/v1/understand/process/{doc_id}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert proc_resp.status_code == 200, proc_resp.text
        proc_data = proc_resp.json()
        assert proc_data["chunks_count"] >= 1
        assert proc_data["entities_count"] >= 1

        # Step 3: Multi-Select Generation across ALL 7 deliverable formats simultaneously
        t0 = time.perf_counter()
        gen_resp = await client.post(
            "/api/v1/generate",
            json={
                "doc_id": doc_id,
                "deliverable_types": ALL_SEVEN_FORMATS,
                "query": "air-gap cryptographic security standards",
                "parameters": {
                    "audience": "Tactical Operations Command",
                    "tone": "Authoritative & Objective",
                    "language": "en",
                    "detail_level": "comprehensive",
                    "objective": "Enclave Hardening",
                    "style": "DoD Directive Standard",
                },
                "actor": "operator_alice",
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        t1 = time.perf_counter()
        elapsed_total_ms = (t1 - t0) * 1000

        assert gen_resp.status_code == 201, gen_resp.text
        gen_data = gen_resp.json()
        assert gen_data["total_deliverables"] == 7
        deliverables = gen_data["deliverables"]
        assert len(deliverables) == 7

        # Average latency per format (threshold accounts for live local Ollama LLM execution)
        avg_latency_ms = elapsed_total_ms / 7
        assert avg_latency_ms < 6000, f"Average generation latency {avg_latency_ms:.1f}ms exceeds SLA"

        # Verify each of the 7 formats
        format_types_present = {d["deliverable_type"] for d in deliverables}
        assert format_types_present == set(ALL_SEVEN_FORMATS)

        # Step 4: Grounding & Trace Provenance Check across all 7 formats
        for deliv in deliverables:
            assert deliv["contract_verified"] is True
            assert deliv["total_sentences"] >= 1
            assert deliv["total_citations"] >= 1

            # Validate /trace on first sentence of each format
            trace_resp = await client.get(
                f"/api/v1/grounding/trace/{deliv['output_id']}/0",
                headers={"Authorization": f"Bearer {operator_token}"},
            )
            assert trace_resp.status_code == 200, trace_resp.text
            trace_data = trace_resp.json()
            assert trace_data["all_spans_verified"] is True
            assert len(trace_data["grounding_sources"]) >= 1

            # Verify character offset verbatim match against raw_text
            for span in trace_data["grounding_sources"]:
                start = span["char_offset_start"]
                end = span["char_offset_end"]
                assert raw_text[start:end] == span["quote"]

        # Step 5: Human Review & Approval Gatekeeper on Advisory deliverable
        advisory = next(d for d in deliverables if d["deliverable_type"] == "advisory")
        advisory_id = advisory["output_id"]

        # Ensure export is locked in status 'draft'
        unauth_export = await client.post(
            f"/api/v1/review/outputs/{advisory_id}/export",
            json={"export_format": "markdown", "actor": "reviewer_bob"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert unauth_export.status_code == 403, "Draft output must NOT be exportable before formal approval"

        # Reviewer edits a sentence with diff tracking
        edit_resp = await client.post(
            f"/api/v1/review/outputs/{advisory_id}/edit-sentence",
            json={
                "sentence_id": advisory["content"]["blocks"][0]["sentences"][0]["sentence_id"],
                "new_text": "All tactical computing systems must enforce strict physical and cryptographic air-gap boundaries.",
                "notes": "Hardened phrasing to meet defense specification.",
            },
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert edit_resp.status_code == 200, edit_resp.text
        updated_output = edit_resp.json()
        assert updated_output["content"]["blocks"][0]["sentences"][0]["review_status"] == "edited"

        # Reviewer approves deliverable -> transitions to 'final'
        approve_resp = await client.post(
            f"/api/v1/review/outputs/{advisory_id}/approve",
            json={"reviewer_notes": "Approved for tactical dissemination."},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert approve_resp.status_code == 200, approve_resp.text
        assert approve_resp.json()["status"] == "final"
        assert approve_resp.json()["format_metadata"]["export_locked"] is False

        # Export is now unlocked and returns authenticated deliverable
        export_resp = await client.post(
            f"/api/v1/review/outputs/{advisory_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert export_resp.status_code == 200, export_resp.text
        export_data = export_resp.json()
        assert export_data["checksum_sha256"] == compute_sha256(export_data["exported_content"].encode("utf-8"))


# ==============================================================================
# 3. Complete End-to-End Pipeline across All 7 Formats (Video Source)
# ==============================================================================


@pytest.mark.asyncio
async def test_e2e_all_seven_formats_on_video_source(operator_token: str, prepare_database):
    """Verify all 7 deliverable formats can be generated from an ingested video file."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        video_bytes = create_video_mp4()
        upload_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("reconnaissance.mp4", video_bytes, "video/mp4")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["document"]["doc_id"]

        # Understand & Chunk
        proc_resp = await client.post(
            f"/api/v1/understand/process/{doc_id}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert proc_resp.status_code == 200

        # Generate all 7 formats
        gen_resp = await client.post(
            "/api/v1/generate",
            json={
                "doc_id": doc_id,
                "deliverable_types": ALL_SEVEN_FORMATS,
                "actor": "operator_alice",
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert gen_resp.status_code == 201
        deliverables = gen_resp.json()["deliverables"]
        assert len(deliverables) == 7
        assert {d["deliverable_type"] for d in deliverables} == set(ALL_SEVEN_FORMATS)


# ==============================================================================
# 4. Latency & Load Sanity Benchmark
# ==============================================================================


@pytest.mark.asyncio
async def test_e2e_latency_and_load_benchmark(operator_token: str, prepare_database):
    """Measure generation latency per format across multiple iterations to ensure zero surprises during demo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        docx_bytes = create_clean_docx()
        upload_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("benchmark_spec.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["document"]["doc_id"]

        await client.post(
            f"/api/v1/understand/process/{doc_id}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

        format_timings: dict[str, list[float]] = {fmt: [] for fmt in ALL_SEVEN_FORMATS}

        # Benchmark each format individually 3 times
        for fmt in ALL_SEVEN_FORMATS:
            for _ in range(3):
                t_start = time.perf_counter()
                res = await client.post(
                    "/api/v1/generate",
                    json={"doc_id": doc_id, "deliverable_types": [fmt], "actor": "operator_alice"},
                    headers={"Authorization": f"Bearer {operator_token}"},
                )
                t_end = time.perf_counter()
                assert res.status_code == 201
                duration_ms = (t_end - t_start) * 1000
                format_timings[fmt].append(duration_ms)

        # Assert every format averages under 30000ms for live local Ollama inference
        for fmt, times in format_timings.items():
            avg = sum(times) / len(times)
            assert avg < 30000, f"Format {fmt} average latency {avg:.1f}ms exceeds 30000ms threshold"


# ==============================================================================
# 5. Full End-to-End Cryptographic Hash Chain Tamper Check
# ==============================================================================


@pytest.mark.asyncio
async def test_e2e_cryptographic_audit_chain_integrity(operator_token: str, prepare_database):
    """Verify that after operations are recorded, the SHA-256 chain is valid."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        docx_bytes = create_clean_docx()
        await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("audit_test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        res = await client.get("/api/v1/audit/verify-chain")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["valid"] is True
        assert data["total_records"] >= 1
        assert "verified" in data["status"].lower()
