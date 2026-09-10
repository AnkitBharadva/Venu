"""Comprehensive test suite for Phase 3: Grounding & Retrieval Service.

Verifies:
1. Hard Claim-Citation Contract Enforcement (unit & API level):
   - Strict rejection of uncited claims (UncitedClaimViolationError).
   - Rejection of invalid or cross-document chunk references (InvalidCitationChunkError).
   - Rejection of mismatched quotes and offsets (GroundingQuoteMismatchError).
2. Hybrid Grounding Retrieval (/api/v1/grounding/retrieve):
   - Qdrant dense vector similarity merged with FalkorDB graph entity context.
   - Formatted merged context text ready for LLM generation adapters.
3. Provenance Claim-to-Chunk Trace Service (/api/v1/grounding/trace):
   - Sentence-level lookup mapping back to exact source chunk and character offsets.
   - Contextual before/after preview for UI tooltip inspection.
4. Acceptance Criteria: 10 sentences across 3 output types (executive_summary, advisory, linkedin_post)
   - Every single generated sentence resolves to an authentic, exact character slice in raw_text.
5. Cryptographic tamper-evident audit logging for all deliverable creation operations.
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
from app.schemas.grounding import (
    GroundedBlock,
    GroundedCitation,
    GroundedDeliverableContent,
    GroundedSentence,
)
from app.services.grounding.contract_enforcer import (
    GroundingContractEnforcer,
    GroundingContractError,
    GroundingQuoteMismatchError,
    InvalidCitationChunkError,
    UncitedClaimViolationError,
)

# Test Document Content
SAMPLE_DOC_TEXT = (
    "The Defense Intelligence Content Processing Platform operates in an air-gapped security perimeter "
    "with zero external network connectivity. Every uploaded document is encrypted at rest using local "
    "AES-256 keys derived from secure hardware. Semantic chunking divides raw text into structured addressable "
    "spans while preserving exact character offsets and metadata. A FalkorDB knowledge graph maps entity "
    "relationships and cross-chunk contextual dependencies across the intelligence corpus."
)

CHUNK_0_TEXT = (
    "The Defense Intelligence Content Processing Platform operates in an air-gapped security perimeter "
    "with zero external network connectivity."
)
CHUNK_1_TEXT = (
    "Every uploaded document is encrypted at rest using local AES-256 keys derived from secure hardware."
)
CHUNK_2_TEXT = (
    "Semantic chunking divides raw text into structured addressable spans while preserving exact character offsets and metadata."
)
CHUNK_3_TEXT = (
    "A FalkorDB knowledge graph maps entity relationships and cross-chunk contextual dependencies across the intelligence corpus."
)


# ==============================================================================
# 1. Unit Tests: GroundingContractEnforcer Hard Contract
# ==============================================================================


def test_contract_enforcer_rejects_empty_blocks():
    """Verify enforcer rejects deliverables with no content blocks."""
    doc_id = uuid.uuid4()
    content = GroundedDeliverableContent(title="Empty Doc", blocks=[])
    with pytest.raises(GroundingContractError, match="Deliverable content cannot be empty"):
        GroundingContractEnforcer.validate_deliverable(
            doc_id=doc_id, raw_text=SAMPLE_DOC_TEXT, valid_chunks={}, content=content
        )


def test_contract_enforcer_rejects_uncited_claims():
    """Verify hard contract: generation adapters cannot emit claims without citations."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        chunk_index=0,
        text=CHUNK_0_TEXT,
        char_offset_start=0,
        char_offset_end=len(CHUNK_0_TEXT),
    )

    content = GroundedDeliverableContent(
        title="Uncited Test",
        blocks=[
            GroundedBlock(
                block_index=0,
                sentences=[
                    # Sentence without citations triggers pydantic validation or enforcer
                    GroundedSentence.model_construct(
                        sentence_id="sent_0",
                        sentence_index=0,
                        text="This is an uncited rogue claim generated without provenance.",
                        citations=[],
                    )
                ],
            )
        ],
    )

    with pytest.raises(UncitedClaimViolationError) as exc_info:
        GroundingContractEnforcer.validate_deliverable(
            doc_id=doc_id,
            raw_text=SAMPLE_DOC_TEXT,
            valid_chunks={chunk_id: chunk},
            content=content,
        )
    assert "HARD CONTRACT VIOLATION" in exc_info.value.message
    assert "0 citations" in exc_info.value.message


def test_contract_enforcer_rejects_invalid_chunk_reference():
    """Verify enforcer rejects citations referencing non-existent chunk IDs."""
    doc_id = uuid.uuid4()
    foreign_chunk_id = uuid.uuid4()

    content = GroundedDeliverableContent(
        title="Bad Chunk Test",
        blocks=[
            GroundedBlock(
                block_index=0,
                sentences=[
                    GroundedSentence(
                        sentence_id="sent_0",
                        sentence_index=0,
                        text="Some claim text.",
                        citations=[
                            GroundedCitation(
                                chunk_id=foreign_chunk_id,
                                char_offset_start=0,
                                char_offset_end=10,
                                quote="Some quote",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(InvalidCitationChunkError) as exc_info:
        GroundingContractEnforcer.validate_deliverable(
            doc_id=doc_id,
            raw_text=SAMPLE_DOC_TEXT,
            valid_chunks={},  # No chunks available
            content=content,
        )
    assert "references non-existent chunk" in exc_info.value.message


def test_contract_enforcer_rejects_mismatched_quote():
    """Verify enforcer rejects citations where quote does not exist in chunk or text."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        chunk_index=0,
        text=CHUNK_0_TEXT,
        char_offset_start=0,
        char_offset_end=len(CHUNK_0_TEXT),
    )

    content = GroundedDeliverableContent(
        title="Quote Mismatch Test",
        blocks=[
            GroundedBlock(
                block_index=0,
                sentences=[
                    GroundedSentence(
                        sentence_id="sent_0",
                        sentence_index=0,
                        text="Fabricated claim.",
                        citations=[
                            GroundedCitation(
                                chunk_id=chunk_id,
                                char_offset_start=0,
                                char_offset_end=20,
                                quote="COMPLETELY FABRICATED QUOTE NOT IN SOURCE",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(GroundingQuoteMismatchError):
        GroundingContractEnforcer.validate_deliverable(
            doc_id=doc_id,
            raw_text=SAMPLE_DOC_TEXT,
            valid_chunks={chunk_id: chunk},
            content=content,
        )


# ==============================================================================
# Helper to Seed Test Document and Addressable Chunks
# ==============================================================================


async def seed_test_grounding_document(session: AsyncSession) -> tuple[SourceDocument, list[DocumentChunk]]:
    """Seed test source document and its 4 semantic chunks with exact character offsets."""
    doc_id = uuid.uuid4()
    raw_text = SAMPLE_DOC_TEXT

    # Find exact offsets for the 4 chunks
    s0 = raw_text.index(CHUNK_0_TEXT)
    e0 = s0 + len(CHUNK_0_TEXT)

    s1 = raw_text.index(CHUNK_1_TEXT)
    e1 = s1 + len(CHUNK_1_TEXT)

    s2 = raw_text.index(CHUNK_2_TEXT)
    e2 = s2 + len(CHUNK_2_TEXT)

    s3 = raw_text.index(CHUNK_3_TEXT)
    e3 = s3 + len(CHUNK_3_TEXT)

    doc = SourceDocument(
        doc_id=doc_id,
        original_filename="tactical_intel_briefing.txt",
        content_type="text/plain",
        raw_text=raw_text,
        structural_metadata={"format": "txt", "sections": 4},
        checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        encrypted_file_path="storage/encrypted/test_doc.bin",
        uploader_id="unit_tester",
    )
    session.add(doc)

    chunks = [
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            doc_id=doc_id,
            chunk_index=0,
            text=CHUNK_0_TEXT,
            char_offset_start=s0,
            char_offset_end=e0,
            heading="Air-Gapped Perimeter",
            page_number=1,
            metadata_payload={"section": 1},
        ),
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            doc_id=doc_id,
            chunk_index=1,
            text=CHUNK_1_TEXT,
            char_offset_start=s1,
            char_offset_end=e1,
            heading="Cryptographic Security",
            page_number=1,
            metadata_payload={"section": 2},
        ),
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            doc_id=doc_id,
            chunk_index=2,
            text=CHUNK_2_TEXT,
            char_offset_start=s2,
            char_offset_end=e2,
            heading="Semantic Chunking Layer",
            page_number=2,
            metadata_payload={"section": 3},
        ),
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            doc_id=doc_id,
            chunk_index=3,
            text=CHUNK_3_TEXT,
            char_offset_start=s3,
            char_offset_end=e3,
            heading="Knowledge Graph Architecture",
            page_number=2,
            metadata_payload={"section": 4},
        ),
    ]
    for c in chunks:
        session.add(c)

    await record_audit_event(
        session=session,
        actor="unit_tester",
        action="seed_test_document",
        doc_id=doc_id,
        source_hash=doc.checksum,
        details={"chunks": 4},
    )
    await session.commit()
    await session.refresh(doc)
    return doc, chunks


# ==============================================================================
# 2. Integration Tests: /retrieve Endpoint
# ==============================================================================


@pytest.mark.asyncio
async def test_retrieve_endpoint_success(prepare_database):
    """Test POST /api/v1/grounding/retrieve returns ranked chunks and graph context."""
    db_gen = app.dependency_overrides[get_db]()
    session = await anext(db_gen)

    doc, _ = await seed_test_grounding_document(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "query": "air-gapped security perimeter",
            "doc_id": str(doc.doc_id),
            "top_k": 3,
            "include_graph": True,
            "alpha": 0.7,
        }
        res = await client.post("/api/v1/grounding/retrieve", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["doc_id"] == str(doc.doc_id)
        assert data["total_chunks"] <= 3
        assert len(data["retrieved_chunks"]) > 0
        assert "merged_context_text" in data
        assert "=== CHUNK #" in data["merged_context_text"]
        assert "graph_context" in data

        # Check chunk structure
        first_chunk = data["retrieved_chunks"][0]
        assert "score" in first_chunk
        assert "vector_score" in first_chunk
        assert "graph_score" in first_chunk
        assert "char_offset_start" in first_chunk
        assert "char_offset_end" in first_chunk


@pytest.mark.asyncio
async def test_retrieve_endpoint_nonexistent_doc(prepare_database):
    """Test POST /api/v1/grounding/retrieve returns 404 for unknown document."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "query": "anything",
            "doc_id": str(uuid.uuid4()),
            "top_k": 3,
        }
        res = await client.post("/api/v1/grounding/retrieve", json=payload)
        assert res.status_code == 404


# ==============================================================================
# 3. Acceptance Criteria: 10 Sentences across 3 Output Types
# ==============================================================================


@pytest.mark.asyncio
async def test_acceptance_ten_sentences_across_three_output_types(prepare_database):
    """Acceptance criteria verification.

    Creates 3 distinct output types:
    1. executive_summary (4 sentences)
    2. advisory (3 sentences)
    3. linkedin_post (3 sentences)
    Total: exactly 10 sentences.

    Verifies:
    - Every sentence passes the hard claim-citation contract upon deliverable creation.
    - /trace resolves every sentence to a real, verified span in the original source document:
      raw_text[char_offset_start:char_offset_end] == quote / source slice.
    - Full deliverable trace confirms 100% coverage and all_verified == True.
    """
    db_gen = app.dependency_overrides[get_db]()
    session = await anext(db_gen)

    doc, chunks = await seed_test_grounding_document(session)
    c0, c1, c2, c3 = chunks[0], chunks[1], chunks[2], chunks[3]
    raw_text = doc.raw_text

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # ----------------------------------------------------------------------
        # Output 1: Executive Summary (4 sentences)
        # ----------------------------------------------------------------------
        exec_content = GroundedDeliverableContent(
            title="Strategic Defense Intelligence Overview",
            summary="High-level operational overview for defense commanders.",
            blocks=[
                GroundedBlock(
                    block_index=0,
                    title="System Architecture & Threat Isolation",
                    sentences=[
                        GroundedSentence(
                            sentence_id="exec_sent_0",
                            sentence_index=0,
                            text="The defense intelligence processing platform strictly enforces an air-gapped security perimeter with zero external network connectivity.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c0.chunk_id,
                                    char_offset_start=c0.char_offset_start,
                                    char_offset_end=c0.char_offset_end,
                                    quote=c0.text,
                                )
                            ],
                        ),
                        GroundedSentence(
                            sentence_id="exec_sent_1",
                            sentence_index=1,
                            text="All uploaded classified documents are secured using hardware-derived AES-256 cryptographic keys at rest.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c1.chunk_id,
                                    char_offset_start=c1.char_offset_start,
                                    char_offset_end=c1.char_offset_end,
                                    quote=c1.text,
                                )
                            ],
                        ),
                    ],
                ),
                GroundedBlock(
                    block_index=1,
                    title="Intelligence Structuring & Graph Synthesis",
                    sentences=[
                        GroundedSentence(
                            sentence_id="exec_sent_2",
                            sentence_index=2,
                            text="Raw textual intelligence is parsed into semantically coherent spans while preserving exact character offsets and metadata.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c2.chunk_id,
                                    char_offset_start=c2.char_offset_start,
                                    char_offset_end=c2.char_offset_end,
                                    quote=c2.text,
                                )
                            ],
                        ),
                        GroundedSentence(
                            sentence_id="exec_sent_3",
                            sentence_index=3,
                            text="A high-performance FalkorDB knowledge graph maps multi-hop entity relationships and cross-chunk contextual dependencies.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c3.chunk_id,
                                    char_offset_start=c3.char_offset_start,
                                    char_offset_end=c3.char_offset_end,
                                    quote=c3.text,
                                )
                            ],
                        ),
                    ],
                ),
            ],
        )

        res_exec = await client.post(
            "/api/v1/grounding/outputs",
            json={
                "doc_id": str(doc.doc_id),
                "deliverable_type": "executive_summary",
                "content": exec_content.model_dump(mode="json"),
                "format_metadata": {"persona": "Commanding Officer", "tone": "formal"},
            },
        )
        assert res_exec.status_code == 201, res_exec.text
        exec_data = res_exec.json()
        exec_output_id = exec_data["output_id"]
        assert exec_data["total_sentences"] == 4
        assert exec_data["total_citations"] == 4
        assert exec_data["contract_verified"] is True

        # ----------------------------------------------------------------------
        # Output 2: Tactical Advisory (3 sentences)
        # ----------------------------------------------------------------------
        advisory_content = GroundedDeliverableContent(
            title="Operational Cyber & Data Handling Advisory",
            summary="Mandatory security guidance for deployed operations.",
            blocks=[
                GroundedBlock(
                    block_index=0,
                    title="Mandatory Security Protocols",
                    sentences=[
                        GroundedSentence(
                            sentence_id="adv_sent_0",
                            sentence_index=0,
                            text="Air-gapped operation dictates that zero external network ingress or egress can be permitted under any operational scenario.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c0.chunk_id,
                                    char_offset_start=c0.char_offset_start,
                                    char_offset_end=c0.char_offset_end,
                                    quote=c0.text,
                                )
                            ],
                        ),
                        GroundedSentence(
                            sentence_id="adv_sent_1",
                            sentence_index=1,
                            text="Cryptographic integrity must be maintained using local AES-256 keys derived from secure hardware for all stored assets.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c1.chunk_id,
                                    char_offset_start=c1.char_offset_start,
                                    char_offset_end=c1.char_offset_end,
                                    quote=c1.text,
                                )
                            ],
                        ),
                        GroundedSentence(
                            sentence_id="adv_sent_2",
                            sentence_index=2,
                            text="Operators must strictly verify that semantic chunking retains exact character offsets for non-repudiation auditability.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c2.chunk_id,
                                    char_offset_start=c2.char_offset_start,
                                    char_offset_end=c2.char_offset_end,
                                    quote=c2.text,
                                )
                            ],
                        ),
                    ],
                )
            ],
        )

        res_adv = await client.post(
            "/api/v1/grounding/outputs",
            json={
                "doc_id": str(doc.doc_id),
                "deliverable_type": "advisory",
                "content": advisory_content.model_dump(mode="json"),
                "format_metadata": {"threat_level": "DEFCON_2", "urgency": "immediate"},
            },
        )
        assert res_adv.status_code == 201, res_adv.text
        adv_data = res_adv.json()
        adv_output_id = adv_data["output_id"]
        assert adv_data["total_sentences"] == 3
        assert adv_data["total_citations"] == 3

        # ----------------------------------------------------------------------
        # Output 3: LinkedIn Post (3 sentences)
        # ----------------------------------------------------------------------
        linkedin_content = GroundedDeliverableContent(
            title="Pioneering Air-Gapped Intelligence Architecture",
            summary="Public technological milestone announcement.",
            blocks=[
                GroundedBlock(
                    block_index=0,
                    title="Platform Launch Announcement",
                    sentences=[
                        GroundedSentence(
                            sentence_id="link_sent_0",
                            sentence_index=0,
                            text="We are thrilled to unveil our Defense Intelligence Content Processing Platform running completely air-gapped with zero external network connectivity!",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c0.chunk_id,
                                    char_offset_start=c0.char_offset_start,
                                    char_offset_end=c0.char_offset_end,
                                    quote=c0.text,
                                )
                            ],
                        ),
                        GroundedSentence(
                            sentence_id="link_sent_1",
                            sentence_index=1,
                            text="With robust AES-256 encryption at rest derived from secure hardware, enterprise data sovereignty is unconditionally guaranteed.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c1.chunk_id,
                                    char_offset_start=c1.char_offset_start,
                                    char_offset_end=c1.char_offset_end,
                                    quote=c1.text,
                                )
                            ],
                        ),
                        GroundedSentence(
                            sentence_id="link_sent_2",
                            sentence_index=2,
                            text="Our integrated FalkorDB graph engine connects complex cross-document entities and relationships with real-time provenance tracking.",
                            citations=[
                                GroundedCitation(
                                    chunk_id=c3.chunk_id,
                                    char_offset_start=c3.char_offset_start,
                                    char_offset_end=c3.char_offset_end,
                                    quote=c3.text,
                                )
                            ],
                        ),
                    ],
                )
            ],
        )

        res_link = await client.post(
            "/api/v1/grounding/outputs",
            json={
                "doc_id": str(doc.doc_id),
                "deliverable_type": "linkedin_post",
                "content": linkedin_content.model_dump(mode="json"),
                "format_metadata": {"tags": ["AI", "AirGap", "DefenseTech"]},
            },
        )
        assert res_link.status_code == 201, res_link.text
        link_data = res_link.json()
        link_output_id = link_data["output_id"]
        assert link_data["total_sentences"] == 3
        assert link_data["total_citations"] == 3

        # ----------------------------------------------------------------------
        # TRACE VERIFICATION: Test all 10 sentences individually
        # ----------------------------------------------------------------------
        test_matrix = [
            # (output_id, sentence_idx, expected_chunk, expected_type)
            (exec_output_id, 0, c0, "executive_summary"),
            (exec_output_id, 1, c1, "executive_summary"),
            (exec_output_id, 2, c2, "executive_summary"),
            (exec_output_id, 3, c3, "executive_summary"),
            (adv_output_id, 0, c0, "advisory"),
            (adv_output_id, 1, c1, "advisory"),
            (adv_output_id, 2, c2, "advisory"),
            (link_output_id, 0, c0, "linkedin_post"),
            (link_output_id, 1, c1, "linkedin_post"),
            (link_output_id, 2, c3, "linkedin_post"),
        ]

        assert len(test_matrix) == 10, "Acceptance test must cover exactly 10 sentences!"

        verified_sentences_count = 0

        for out_id, sent_idx, expected_chunk, exp_type in test_matrix:
            trace_res = await client.get(
                f"/api/v1/grounding/trace?output_id={out_id}&sentence_index={sent_idx}"
            )
            assert trace_res.status_code == 200, trace_res.text
            trace_data = trace_res.json()

            # 1. Check sentence metadata
            assert trace_data["deliverable_type"] == exp_type
            assert trace_data["sentence_index"] == sent_idx
            assert trace_data["all_spans_verified"] is True

            # 2. Check source span verification
            sources = trace_data["grounding_sources"]
            assert len(sources) >= 1
            src = sources[0]
            assert src["trace_verified"] is True
            assert src["chunk_id"] == str(expected_chunk.chunk_id)
            assert src["heading"] == expected_chunk.heading
            assert src["page_number"] == expected_chunk.page_number

            # 3. CRITICAL GROUND-TRUTH TEST:
            # raw_text[char_offset_start:char_offset_end] MUST EXACTLY equal the source slice!
            start = src["char_offset_start"]
            end = src["char_offset_end"]
            actual_span_in_raw_text = raw_text[start:end]

            assert actual_span_in_raw_text == expected_chunk.text, (
                f"Offset slice mismatch for {exp_type} sentence #{sent_idx}:\n"
                f"Expected: '{expected_chunk.text}'\n"
                f"Actual:   '{actual_span_in_raw_text}'"
            )

            # 4. Check UI context preview availability
            assert "context_before" in src
            assert "context_after" in src

            verified_sentences_count += 1

        assert verified_sentences_count == 10, "All 10 sentences verified 100% against source text!"

        # ----------------------------------------------------------------------
        # Full Deliverable Trace Verification
        # ----------------------------------------------------------------------
        full_exec_res = await client.get(f"/api/v1/grounding/trace/{exec_output_id}/full")
        assert full_exec_res.status_code == 200
        full_exec_data = full_exec_res.json()
        assert full_exec_data["total_sentences"] == 4
        assert full_exec_data["total_citations"] == 4
        assert full_exec_data["coverage_pct"] == 100.0
        assert full_exec_data["all_verified"] is True
        assert len(full_exec_data["traces"]) == 4

        # ----------------------------------------------------------------------
        # List deliverables by document
        # ----------------------------------------------------------------------
        list_res = await client.get(f"/api/v1/grounding/outputs/document/{doc.doc_id}")
        assert list_res.status_code == 200
        doc_deliverables = list_res.json()
        assert len(doc_deliverables) == 3

        # ----------------------------------------------------------------------
        # Cryptographic Audit Chain Verification
        # ----------------------------------------------------------------------
        audit_res = await client.get("/api/v1/audit/verify-chain")
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        assert audit_data["valid"] is True
        assert audit_data["total_records"] >= 4  # seed + 3 deliverables


# ==============================================================================
# 4. Negative Test: Attempting to Post Deliverable with Uncited Sentence
# ==============================================================================


@pytest.mark.asyncio
async def test_api_rejects_uncited_deliverable(prepare_database):
    """Test POST /api/v1/grounding/outputs rejects deliverable lacking citation with HTTP 422."""
    db_gen = app.dependency_overrides[get_db]()
    session = await anext(db_gen)

    doc, chunks = await seed_test_grounding_document(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_payload = {
            "doc_id": str(doc.doc_id),
            "deliverable_type": "briefing",
            "content": {
                "title": "Uncited Claim Deliverable",
                "blocks": [
                    {
                        "block_index": 0,
                        "sentences": [
                            {
                                "sentence_id": "sent_uncited",
                                "sentence_index": 0,
                                "text": "This statement is completely unbacked by any source citation.",
                                "citations": [],
                            }
                        ],
                    }
                ],
            },
        }
        res = await client.post("/api/v1/grounding/outputs", json=bad_payload)
        assert res.status_code == 422
        err_detail = res.json()["detail"]
        # Can be pydantic min_length error or custom UncitedClaimViolationError
        assert (
            "citations" in str(err_detail).lower()
            or "UncitedClaimViolationError" in str(err_detail)
        )
