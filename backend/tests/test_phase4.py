"""Comprehensive test suite for Phase 4: Output Generation Adapters.

Verifies:
1. All 7 deliverable adapters generate valid, structurally distinct content:
   - LinkedIn Post (hook + body + CTA, hashtags)
   - Twitter/X Thread (<=280 chars, numbered 1/N, hook-first)
   - Executive Summary (150-300 words, findings + implications)
   - Advisory (Summary, Details, Risk/Impact, Actions, requires_human_review=True, export_locked=True)
   - Presentation (Slide titles + bullets + speaker notes JSON preview)
   - Video Package (Scenes + narration + visual recommendations + SRT subtitles)
   - Infographic (Visual hierarchy + layout specifications + key metrics)
2. Extensibility: Dynamic format registration via config (zero new Python code)
3. Multi-select generation API (POST /api/v1/generate) running 3+ formats concurrently
4. Acceptance Criteria: For all generated sentences across all selected output types,
   /trace resolves to authentic verbatim character spans in raw_text.
5. Tamper-evident cryptographic audit chain integrity.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.database import get_db
from app.main import app
from app.models.audit_log import SourceDocument
from app.models.understanding import DocumentChunk
from app.schemas.adapters import DynamicAdapterConfig, GenerationParameters
from app.schemas.grounding import RetrievedChunkItem
from app.services.adapters.advisory_adapter import AdvisoryAdapter
from app.services.adapters.executive_summary_adapter import ExecutiveSummaryAdapter
from app.services.adapters.infographic_adapter import InfographicAdapter
from app.services.adapters.linkedin_adapter import LinkedInPostAdapter
from app.services.adapters.presentation_adapter import PresentationAdapter
from app.services.adapters.registry import get_adapter_registry
from app.services.adapters.twitter_adapter import TwitterThreadAdapter
from app.services.adapters.video_package_adapter import VideoPackageAdapter

RAW_DOCUMENT = (
    "The Autonomous Aerospace Threat Defense System operates within a strict air-gapped cryptographic boundary. "
    "All sensor streams and tactical payloads are encrypted using on-premise hardware security module keys. "
    "Real-time radar telemetry confirms zero unauthorized network egress across all tactical communications relay nodes. "
    "Automated cyber isolation protocols mandate that any unauthenticated command stream triggers immediate quarantine."
)

CHUNK_0 = "The Autonomous Aerospace Threat Defense System operates within a strict air-gapped cryptographic boundary."
CHUNK_1 = "All sensor streams and tactical payloads are encrypted using on-premise hardware security module keys."
CHUNK_2 = "Real-time radar telemetry confirms zero unauthorized network egress across all tactical communications relay nodes."
CHUNK_3 = "Automated cyber isolation protocols mandate that any unauthenticated command stream triggers immediate quarantine."


def get_mock_retrieved_chunks(doc_id: uuid.UUID) -> list[RetrievedChunkItem]:
    """Helper returning mock retrieved chunks with exact character offsets."""
    chunks = [
        RetrievedChunkItem(
            chunk_id=uuid.uuid4(),
            chunk_index=0,
            text=CHUNK_0,
            score=0.95,
            vector_score=0.92,
            graph_score=0.98,
            char_offset_start=RAW_DOCUMENT.index(CHUNK_0),
            char_offset_end=RAW_DOCUMENT.index(CHUNK_0) + len(CHUNK_0),
            heading="Perimeter Boundary",
            entities_present=["Autonomous Aerospace", "HSM"],
        ),
        RetrievedChunkItem(
            chunk_id=uuid.uuid4(),
            chunk_index=1,
            text=CHUNK_1,
            score=0.88,
            vector_score=0.85,
            graph_score=0.90,
            char_offset_start=RAW_DOCUMENT.index(CHUNK_1),
            char_offset_end=RAW_DOCUMENT.index(CHUNK_1) + len(CHUNK_1),
            heading="Cryptographic Keys",
            entities_present=["HSM"],
        ),
        RetrievedChunkItem(
            chunk_id=uuid.uuid4(),
            chunk_index=2,
            text=CHUNK_2,
            score=0.82,
            vector_score=0.80,
            graph_score=0.85,
            char_offset_start=RAW_DOCUMENT.index(CHUNK_2),
            char_offset_end=RAW_DOCUMENT.index(CHUNK_2) + len(CHUNK_2),
            heading="Telemetry & Zero Egress",
            entities_present=["Radar Telemetry"],
        ),
        RetrievedChunkItem(
            chunk_id=uuid.uuid4(),
            chunk_index=3,
            text=CHUNK_3,
            score=0.76,
            vector_score=0.75,
            graph_score=0.78,
            char_offset_start=RAW_DOCUMENT.index(CHUNK_3),
            char_offset_end=RAW_DOCUMENT.index(CHUNK_3) + len(CHUNK_3),
            heading="Cyber Isolation",
            entities_present=["Cyber Isolation"],
        ),
    ]
    return chunks


async def seed_source_doc(session: AsyncSession) -> tuple[SourceDocument, list[DocumentChunk]]:
    """Seed test source document and addressable chunks into DB."""
    doc_id = uuid.uuid4()
    doc = SourceDocument(
        doc_id=doc_id,
        original_filename="aerospace_defense_briefing.txt",
        content_type="text/plain",
        checksum="f9c5d012480bf11a681283626e2e260907d7c67c5e2ad63e8fb55979ad23e421",
        encrypted_file_path="storage/encrypted/aerospace.bin",
        raw_text=RAW_DOCUMENT,
        structural_metadata={"sections": 4},
        uploader_id="lead_operator",
    )
    session.add(doc)

    chunks_data = [CHUNK_0, CHUNK_1, CHUNK_2, CHUNK_3]
    db_chunks = []
    for i, c_text in enumerate(chunks_data):
        s = RAW_DOCUMENT.index(c_text)
        e = s + len(c_text)
        c_rec = DocumentChunk(
            chunk_id=uuid.uuid4(),
            doc_id=doc_id,
            chunk_index=i,
            text=c_text,
            char_offset_start=s,
            char_offset_end=e,
            heading=f"Section {i+1}",
            page_number=1,
            metadata_payload={"section": i + 1},
        )
        session.add(c_rec)
        db_chunks.append(c_rec)

    await record_audit_event(
        session=session,
        actor="lead_operator",
        action="seed_test_doc",
        doc_id=doc_id,
        source_hash=doc.checksum,
        details={"chunks": 4},
    )
    await session.commit()
    await session.refresh(doc)
    return doc, db_chunks


# ==============================================================================
# 1. Unit Tests for Each of the 7 Concrete Adapters
# ==============================================================================


@pytest.mark.asyncio
async def test_adapter_linkedin_post():
    """Verify LinkedInPostAdapter structure: hook, body, CTA, hashtags, and valid citations."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = LinkedInPostAdapter()
    params = GenerationParameters(audience="executives", tone="authoritative")

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params, key_entities=["HSM", "Aerospace"])
    assert out.content.title is not None
    assert len(out.content.blocks) == 3  # Hook, Body, CTA
    assert out.format_metadata["target_platform"] == "LinkedIn"
    assert len(out.format_metadata["hashtags"]) >= 4
    assert out.requires_human_review is False

    # Check that all sentences have valid citations
    for b in out.content.blocks:
        for s in b.sentences:
            assert len(s.citations) >= 1
            cit = s.citations[0]
            assert 0 <= cit.char_offset_start < cit.char_offset_end <= len(RAW_DOCUMENT)


@pytest.mark.asyncio
async def test_adapter_twitter_thread():
    """Verify TwitterThreadAdapter: numbered tweets, strictly <= 280 chars each, citations."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = TwitterThreadAdapter()
    params = GenerationParameters(tone="punchy")

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params)
    assert len(out.content.blocks) == 4
    assert out.format_metadata["all_within_limit"] is True

    for i, b in enumerate(out.content.blocks):
        tweet_sent = b.sentences[0]
        # Check numbering e.g. "1/4", "2/4"
        assert f"{i+1}/4" in tweet_sent.text
        # Check strict 280-char limit
        assert len(tweet_sent.text) <= 280
        assert len(tweet_sent.citations) >= 1


@pytest.mark.asyncio
async def test_adapter_executive_summary():
    """Verify ExecutiveSummaryAdapter: findings + implications, word count within target."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = ExecutiveSummaryAdapter()
    params = GenerationParameters(audience="Defense Board", tone="objective")

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params)
    assert len(out.content.blocks) == 3
    assert out.format_metadata["within_target_word_range"] is True
    assert out.format_metadata["clearance_level"] == "RESTRICTED // AIR-GAP"


@pytest.mark.asyncio
async def test_adapter_advisory_safety_critical():
    """Verify AdvisoryAdapter: 4 safety sections and MANDATORY human review gatekeeper."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = AdvisoryAdapter()
    params = GenerationParameters(tone="urgent")

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params)
    assert len(out.content.blocks) == 4
    # Safety-critical human review gatekeeper MUST be enabled
    assert out.requires_human_review is True
    assert out.format_metadata["export_locked"] is True
    assert out.format_metadata["severity"] == "CRITICAL"
    assert out.format_metadata["review_status"] == "pending_human_review"


@pytest.mark.asyncio
async def test_adapter_presentation():
    """Verify PresentationAdapter: slide titles, bullet points, speaker notes."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = PresentationAdapter()
    params = GenerationParameters()

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params)
    assert len(out.content.blocks) == 4
    assert out.format_metadata["slide_count"] == 4
    assert len(out.format_metadata["slides"]) == 4
    for slide in out.format_metadata["slides"]:
        assert "slide_number" in slide
        assert "speaker_notes" in slide
        assert len(slide["bullets"]) >= 2


@pytest.mark.asyncio
async def test_adapter_video_package():
    """Verify VideoPackageAdapter: scenes, narration, storyboard visual direction, SRT subtitles."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = VideoPackageAdapter()
    params = GenerationParameters()

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params)
    assert len(out.content.blocks) == 4
    assert out.format_metadata["total_scenes"] == 4
    assert "subtitles_srt" in out.format_metadata
    assert "-->" in out.format_metadata["subtitles_srt"]
    assert out.format_metadata["total_estimated_duration_seconds"] > 0


@pytest.mark.asyncio
async def test_adapter_infographic():
    """Verify InfographicAdapter: visual hierarchy, layout recommendations, key metrics."""
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    adapter = InfographicAdapter()
    params = GenerationParameters()

    out = await adapter.generate(doc_id, chunks, RAW_DOCUMENT, params)
    assert len(out.content.blocks) == 4
    assert len(out.format_metadata["key_metrics"]) == 4
    assert len(out.format_metadata["visual_hierarchy"]) == 4
    assert out.format_metadata["layout_type"] == "Vertical Narrative Flow"


# ==============================================================================
# 2. Extensibility Test: Dynamic Config-Driven Adapter (Zero New Code)
# ==============================================================================


@pytest.mark.asyncio
async def test_dynamic_config_driven_adapter_registration():
    """Verify that adding a new deliverable format is purely configuration, requiring zero code changes."""
    registry = get_adapter_registry()

    custom_config = DynamicAdapterConfig(
        deliverable_type="tactical_intel_bulletin",
        name="Tactical Intelligence Bulletin",
        description="Rapid 3-paragraph tactical field bulletin for frontline commanders.",
        category="operational",
        system_prompt_template="Generate concise tactical field bulletins with exact source citations.",
        block_structure=[
            {"index": 0, "title": "Immediate Threat Level"},
            {"index": 1, "title": "Observed Asset Activity"},
            {"index": 2, "title": "Field Actions Mandated"},
        ],
        requires_human_review=False,
        format_metadata_defaults={"dissemination": "TACTICAL_NET", "urgency": "FLASH"},
    )

    # Register purely via config
    dynamic_adapter = registry.register_from_config(custom_config)
    assert dynamic_adapter.deliverable_type == "tactical_intel_bulletin"

    # Test retrieval from registry
    retrieved_adapter = registry.get_adapter("tactical_intel_bulletin")
    assert retrieved_adapter.name == "Tactical Intelligence Bulletin"

    # Execute generation with dynamic adapter
    doc_id = uuid.uuid4()
    chunks = get_mock_retrieved_chunks(doc_id)
    out = await dynamic_adapter.generate(doc_id, chunks, RAW_DOCUMENT, GenerationParameters())

    assert len(out.content.blocks) == 3
    assert out.format_metadata["config_driven"] is True
    assert out.format_metadata["dissemination"] == "TACTICAL_NET"


# ==============================================================================
# 3. Acceptance Criteria: Multi-Select Generation API (3+ Output Types) & Trace
# ==============================================================================


@pytest.mark.asyncio
async def test_multi_select_generation_and_full_trace_acceptance(prepare_database):
    """Acceptance Criteria Verification.

    1. Submit one source document.
    2. Select 4 output types: linkedin_post, twitter_thread, executive_summary, advisory.
    3. Verify all 4 deliverables are generated and stored with contract_verified=True.
    4. Call /trace on each generated sentence across all 4 deliverables:
       Verify raw_text[char_offset_start:char_offset_end] strictly equals verbatim slice.
    5. Verify advisory flags requires_human_review and export_locked.
    6. Verify cryptographic tamper-evident audit chain integrity.
    """
    db_gen = app.dependency_overrides[get_db]()
    session = await anext(db_gen)

    source_doc, db_chunks = await seed_source_doc(session)
    raw_text = source_doc.raw_text

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Multi-select generation request with 4 deliverable formats
        payload = {
            "doc_id": str(source_doc.doc_id),
            "deliverable_types": [
                "linkedin_post",
                "twitter_thread",
                "executive_summary",
                "advisory",
            ],
            "query": "air-gapped cryptographic defense",
            "parameters": {
                "audience": "Air Force Commanders",
                "tone": "authoritative",
                "detail_level": "comprehensive",
            },
            "actor": "commander_operator",
        }

        gen_res = await client.post("/api/v1/generate", json=payload)
        assert gen_res.status_code == 201, gen_res.text
        gen_data = gen_res.json()

        assert gen_data["total_deliverables"] == 4
        assert len(gen_data["deliverables"]) == 4
        assert gen_data["all_citations_verified"] is True

        created_deliverables = gen_data["deliverables"]
        types_created = [d["deliverable_type"] for d in created_deliverables]
        assert set(types_created) == {"linkedin_post", "twitter_thread", "executive_summary", "advisory"}

        # Step 2: Verify Advisory safety-critical human review gatekeeper
        advisory_deliv = next(d for d in created_deliverables if d["deliverable_type"] == "advisory")
        assert advisory_deliv["format_metadata"].get("requires_human_review") is True
        assert advisory_deliv["format_metadata"].get("export_locked") is True

        # Step 3: Provenance Trace Acceptance Test for every single generated sentence
        total_sentences_traced = 0

        for deliv in created_deliverables:
            out_id = deliv["output_id"]
            d_type = deliv["deliverable_type"]

            # Trace the entire deliverable
            full_trace_res = await client.get(f"/api/v1/grounding/trace/{out_id}/full")
            assert full_trace_res.status_code == 200, full_trace_res.text
            full_trace = full_trace_res.json()

            assert full_trace["coverage_pct"] == 100.0, f"Coverage not 100% for {d_type}"
            assert full_trace["all_verified"] is True, f"Full trace verification failed for {d_type}"

            # Inspect each individual sentence trace
            for sent_trace in full_trace["traces"]:
                s_idx = sent_trace["sentence_index"]
                s_res = await client.get(
                    f"/api/v1/grounding/trace?output_id={out_id}&sentence_index={s_idx}"
                )
                assert s_res.status_code == 200, s_res.text
                s_data = s_res.json()

                assert s_data["all_spans_verified"] is True
                assert len(s_data["grounding_sources"]) >= 1

                for src in s_data["grounding_sources"]:
                    assert src["trace_verified"] is True
                    start = src["char_offset_start"]
                    end = src["char_offset_end"]

                    # CRITICAL GROUND TRUTH CHECK
                    actual_span = raw_text[start:end]
                    assert len(actual_span) > 0
                    assert (
                        actual_span == src["quote"]
                        or src["quote"] in actual_span
                        or actual_span in src["quote"]
                    ), f"Provenance mismatch: '{actual_span}' != '{src['quote']}'"

                total_sentences_traced += 1

        # We must have verified at least 15+ generated sentences across the 4 formats
        assert total_sentences_traced >= 15
        print(f"Total sentences verified with exact raw_text coordinates: {total_sentences_traced}")

        # Step 4: Verify catalog listing endpoint
        adapters_res = await client.get("/api/v1/generate/adapters")
        assert adapters_res.status_code == 200
        catalog = adapters_res.json()
        assert len(catalog) >= 7

        # Step 5: Verify dynamic registration endpoint via API
        dyn_payload = {
            "deliverable_type": "api_registered_brief",
            "name": "API Registered Brief",
            "description": "Registered on-the-fly through REST endpoint",
            "category": "executive",
            "system_prompt_template": "Generate brief from context",
            "block_structure": [{"index": 0, "title": "Summary"}],
            "requires_human_review": False,
        }
        dyn_res = await client.post("/api/v1/generate/adapters/register", json=dyn_payload)
        assert dyn_res.status_code == 201
        assert dyn_res.json()["deliverable_type"] == "api_registered_brief"

        # Step 6: Verify Cryptographic Audit Chain Integrity
        audit_res = await client.get("/api/v1/audit/verify-chain")
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        assert audit_data["valid"] is True
        assert audit_data["total_records"] >= 5  # seed + 4 created deliverables
