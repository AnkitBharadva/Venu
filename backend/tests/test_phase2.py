"""Comprehensive test suite for Phase 2: Understanding & Chunking Layer.

Verifies:
1. Semantic paragraph/section-aware chunking preserving exact character offsets:
   raw_text[char_offset_start:char_offset_end] == chunk.text
2. Structural metadata propagation: page numbers, headings, audio/video timestamps
3. Entity, topic, intent, and sensitive advisory terms extraction
4. 384-dimensional dense embeddings with unit normalization and semantic ranking
5. Qdrant vector store upsert and semantic similarity retrieval by topic
6. FalkorDB openCypher knowledge graph upsert, entity relationship query, and chunk references
7. End-to-end API workflows via FastAPI TestClient
8. Tamper-evident cryptographic audit chain integrity across all operations
"""

import io
import uuid

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.chunking.semantic_chunker import ExtractedChunk, SemanticChunker
from app.services.embeddings.local_embedder import LocalEmbedder, get_local_embedder
from app.services.extraction.entity_extractor import EntityExtractor
from app.services.storage.falkordb_service import FalkorDBService
from app.services.storage.qdrant_service import QdrantService

# Fixtures provided by conftest.py


# Sample Complex Ground-Truth Document
SAMPLE_DOCUMENT_TEXT = """# OPERATION SENTINEL SHIELD: TACTICAL BRIEFING

## SECTION 1: MISSION OBJECTIVE & SCOPE
The primary goal of this operation is to establish an integrated border surveillance and air defense network across the northern sector.
In response to escalating drone incursions and electronic jamming along the Line of Actual Control in Ladakh, the Indian Air Force and Indian Army are conducting joint reconnaissance.

## SECTION 2: DEPLOYED WEAPON SYSTEMS & DEFENSE ASSETS
Key weapon systems assigned to the theater include two squadrons of Rafale multi-role combat aircraft stationed at Ambala and deployed along forward operating bases.
Additionally, the S-400 Triumf surface-to-air missile division has been operationalized to provide long-range airspace denial.
For autonomous reconnaissance, MQ-9 Reaper unmanned aerial systems have been tasked with continuous multi-spectral surveillance.

## SECTION 3: CYBER ADVISORY & SENSITIVE THREAT VECTORS
WARNING: TOP SECRET // NOFORN
A critical vulnerability designated CVE-2024-38077 has been reported in tactical relay nodes, allowing remote code execution if exploited.
Immediate patching is mandated under DEFCON 2 defense readiness protocols.
Any indications of CBRN materials or covert adversary SIGINT interception must be reported directly to CERT-In and DARPA liaison teams.
"""


# ==============================================================================
# Unit Tests: Semantic Chunker & Provenance
# ==============================================================================


def test_semantic_chunker_exact_provenance():
    """Verify that every chunk character span maps back 100% identically to raw_text."""
    chunker = SemanticChunker(min_chunk_chars=80, target_chunk_chars=300, max_chunk_chars=600)
    chunks = chunker.chunk_text(SAMPLE_DOCUMENT_TEXT)

    assert len(chunks) >= 3, "Should produce at least 3 distinct semantic chunks"

    for idx, chunk in enumerate(chunks):
        # Strict claim-to-chunk provenance invariant
        extracted_slice = SAMPLE_DOCUMENT_TEXT[chunk.char_offset_start : chunk.char_offset_end]
        assert extracted_slice == chunk.text, f"Chunk {idx} offset mismatch!"
        assert chunk.verify_provenance(SAMPLE_DOCUMENT_TEXT) is True
        assert len(chunk.text.strip()) > 0
        assert chunk.chunk_index == idx


def test_semantic_chunker_headings_and_pages():
    """Verify heading hierarchy and page numbers are preserved across chunks."""
    doc_with_pages = (
        "--- [Page 1] ---\n"
        "# Executive Summary\n"
        "This is the opening summary describing defensive capabilities.\n\n"
        "--- [Page 2] ---\n"
        "# Technical Details\n"
        "This section details technical weapon specifications and radars."
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_text(doc_with_pages)

    assert len(chunks) >= 2
    # Verify exact slice
    for c in chunks:
        assert doc_with_pages[c.char_offset_start : c.char_offset_end] == c.text

    # First chunk should have Page 1
    assert chunks[0].page_number == 1
    # Last chunk should have Page 2
    assert chunks[-1].page_number == 2


def test_semantic_chunker_video_timestamps():
    """Verify audio/video segment timestamps propagate to chunks."""
    raw_text = "The surveillance drone detected abnormal activity near the ridge. Patrol units responded immediately."
    metadata = {
        "timestamps": [
            {"start": 10.5, "end": 18.2, "char_start": 0, "char_end": 66},
            {"start": 18.5, "end": 25.0, "char_start": 67, "char_end": 102},
        ]
    }

    chunker = SemanticChunker()
    chunks = chunker.chunk_text(raw_text, structural_metadata=metadata)

    assert len(chunks) >= 1
    assert chunks[0].timestamp_start is not None
    assert chunks[0].timestamp_start == 10.5
    assert chunks[0].timestamp_end == 25.0


# ==============================================================================
# Unit Tests: Entity, Intent & Sensitive Terms Extractor
# ==============================================================================


def test_entity_extractor_comprehensive():
    """Verify extraction of entities, topics, intent, sensitive terms, and relationships."""
    chunker = SemanticChunker()
    chunks = chunker.chunk_text(SAMPLE_DOCUMENT_TEXT)

    extractor = EntityExtractor()
    result = extractor.extract(SAMPLE_DOCUMENT_TEXT, chunks)

    # 1. Stated Objective
    assert "Objective:" in result.objective or "goal" in result.objective.lower()
    assert "surveillance" in result.objective.lower() or "air defense" in result.objective.lower()

    # 2. Topics
    topic_names = " ".join(result.topics).lower()
    assert "air defense" in topic_names or "surveillance" in topic_names or "cyber" in topic_names

    # 3. Entities
    entity_names = {e.name.upper(): e.type for e in result.key_entities}
    assert "RAFALE" in entity_names
    assert entity_names["RAFALE"] == "WEAPON_SYSTEM"
    assert "S-400" in entity_names
    assert "INDIAN AIR FORCE" in entity_names
    assert entity_names["INDIAN AIR FORCE"] == "ORGANIZATION"
    assert "LADAKH" in entity_names
    assert entity_names["LADAKH"] == "LOCATION"

    # Verify each entity has valid grounded chunk_ids
    for ent in result.key_entities:
        assert len(ent.chunk_ids) > 0
        for cid in ent.chunk_ids:
            assert any(c.chunk_id == cid for c in chunks)

    # 4. Sensitive Terms
    sens_terms = {s.term: s for s in result.sensitive_terms}
    assert "TOP SECRET" in sens_terms
    assert sens_terms["TOP SECRET"].category == "CLASSIFICATION"
    assert sens_terms["TOP SECRET"].severity == "CRITICAL"
    assert "CVE-2024-38077" in sens_terms
    assert sens_terms["CVE-2024-38077"].category == "CYBER_VULNERABILITY"
    assert "DEFCON 2" in sens_terms or "CBRN" in sens_terms

    # 5. Entity Relationships
    assert len(result.relationships) > 0
    rel_sources = {r.source for r in result.relationships}
    assert any("Rafale" in s or "Indian Air Force" in s or "S-400" in s for s in rel_sources)


# ==============================================================================
# Unit Tests: Local Embeddings & Vector Search
# ==============================================================================


def test_local_embedder_dimension_and_norm():
    """Verify local embedder outputs 384-dimensional unit vectors."""
    embedder = LocalEmbedder(dimension=384)
    texts = [
        "Rafale fighter jets equipped with Meteor beyond-visual-range missiles.",
        "Border surveillance radars deployed along the northern sector mountain ridges.",
        "Unrelated baking recipe with flour, yeast, butter, and sugar.",
    ]
    embeddings = embedder.embed_batch(texts)

    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 384
        norm = np.linalg.norm(np.array(emb))
        assert norm == pytest.approx(1.0, rel=1e-4)


def test_local_embedder_semantic_ranking():
    """Verify that semantic query has higher cosine similarity to relevant chunk."""
    embedder = LocalEmbedder(dimension=384)
    query = "air defense missiles and radar systems"
    relevant_doc = "S-400 surface to air missile defense system with phased array radar."
    irrelevant_doc = "Fresh organic tomatoes harvested during early spring season."

    q_vec = np.array(embedder.embed_text(query))
    rel_vec = np.array(embedder.embed_text(relevant_doc))
    irrel_vec = np.array(embedder.embed_text(irrelevant_doc))

    score_rel = float(np.dot(q_vec, rel_vec))
    score_irrel = float(np.dot(q_vec, irrel_vec))

    assert score_rel > score_irrel, f"Relevant score ({score_rel}) must exceed irrelevant score ({score_irrel})"


def test_qdrant_service_upsert_and_search():
    """Verify Qdrant service indexing and similarity retrieval."""
    qdrant = QdrantService()
    embedder = get_local_embedder()
    doc_id = uuid.uuid4()

    c1 = ExtractedChunk(
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        text="Rafale combat aircraft conducting aerial combat training patrols.",
        char_offset_start=0,
        char_offset_end=65,
        heading="Air Wings",
    )
    c2 = ExtractedChunk(
        chunk_id=uuid.uuid4(),
        chunk_index=1,
        text="Navy stealth frigates conducting anti-submarine drills in international waters.",
        char_offset_start=66,
        char_offset_end=145,
        heading="Maritime Fleet",
    )

    chunks = [c1, c2]
    embs = embedder.embed_batch([c.text for c in chunks])

    # Upsert
    count = qdrant.upsert_chunks(chunks=chunks, embeddings=embs, doc_id=doc_id)
    assert count == 2

    # Query for aircraft
    results = qdrant.search_chunks(query="fighter jets combat patrol", doc_id=doc_id, top_k=2)
    assert len(results) >= 1
    # Top result should be chunk 0 (Rafale)
    assert results[0].chunk_id == c1.chunk_id
    assert results[0].heading == "Air Wings"


# ==============================================================================
# Unit Tests: FalkorDB Graph Service
# ==============================================================================


@pytest.mark.asyncio
async def test_falkordb_service_graph_and_query():
    """Verify graph creation, entity relationships, and referencing chunks."""
    falkor = FalkorDBService()
    doc_id = uuid.uuid4()

    c1 = ExtractedChunk(
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        text="Rafale fighter aircraft operated by the Indian Air Force in Ladakh.",
        char_offset_start=0,
        char_offset_end=67,
    )

    from app.schemas.understanding import EntityMention, EntityRelationship

    entities = [
        EntityMention(name="Rafale", type="WEAPON_SYSTEM", count=1, chunk_ids=[c1.chunk_id]),
        EntityMention(name="Indian Air Force", type="ORGANIZATION", count=1, chunk_ids=[c1.chunk_id]),
        EntityMention(name="Ladakh", type="LOCATION", count=1, chunk_ids=[c1.chunk_id]),
    ]
    relationships = [
        EntityRelationship(source="Rafale", relation="OPERATED_BY", target="Indian Air Force", chunk_id=c1.chunk_id),
        EntityRelationship(source="Rafale", relation="STATIONED_AT", target="Ladakh", chunk_id=c1.chunk_id),
    ]
    topics = ["Air Defense & Aerospace"]

    # Upsert graph
    ok = await falkor.upsert_document_graph(
        doc_id=doc_id,
        filename="tactical_plan.txt",
        chunks=[c1],
        entities=entities,
        relationships=relationships,
        topics=topics,
    )
    assert ok is True

    # Query entity graph for Rafale
    res = await falkor.query_entity_graph("Rafale")
    assert res.entity_name == "Rafale"
    assert res.entity_type == "WEAPON_SYSTEM"
    assert c1.chunk_id in res.referenced_chunks

    conn_names = {ce["name"] for ce in res.connected_entities}
    assert "Indian Air Force" in conn_names or "Ladakh" in conn_names


# ==============================================================================
# Integration Tests: End-to-End API Workflows
# ==============================================================================


@pytest.mark.asyncio
async def test_end_to_end_understanding_pipeline():
    """Verify full workflow: Upload document -> Process understanding -> Query chunks & graph -> Verify audit chain."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Ingest sample document
        files = {
            "file": ("operation_sentinel.txt", io.BytesIO(SAMPLE_DOCUMENT_TEXT.encode("utf-8")), "text/plain")
        }
        data = {"uploader_id": "mission_planner_alpha"}

        upload_resp = await ac.post("/api/v1/ingest/upload", files=files, data=data)
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()["document"]
        doc_id = doc_data["doc_id"]

        # 2. Trigger Phase 2 Understanding & Chunking
        process_resp = await ac.post(f"/api/v1/understand/process/{doc_id}?actor=mission_planner_alpha")
        assert process_resp.status_code == 200
        proc_json = process_resp.json()

        assert proc_json["status"] == "success"
        assert proc_json["chunks_count"] >= 3
        assert proc_json["entities_count"] > 0
        assert proc_json["sensitive_terms_count"] >= 1
        assert proc_json["qdrant_indexed"] is True
        assert proc_json["falkordb_indexed"] is True
        assert proc_json["audit_entry_recorded"] is True

        understanding = proc_json["understanding"]
        assert "Objective:" in understanding["objective"] or "goal" in understanding["objective"].lower()
        assert understanding["offset_accuracy_pct"] == 100.0

        # 3. Retrieve chunks and verify 100% exact text offsets
        chunks_resp = await ac.get(f"/api/v1/understand/documents/{doc_id}/chunks")
        assert chunks_resp.status_code == 200
        chunks_list = chunks_resp.json()

        assert len(chunks_list) == proc_json["chunks_count"]
        for c in chunks_list:
            assert c["offset_verified"] is True
            # Verify slice directly against input
            expected_text = SAMPLE_DOCUMENT_TEXT[c["char_offset_start"] : c["char_offset_end"]]
            assert expected_text == c["text"]

        # 4. Retrieve document understanding
        und_resp = await ac.get(f"/api/v1/understand/documents/{doc_id}/understanding")
        assert und_resp.status_code == 200
        und_data = und_resp.json()
        assert len(und_data["key_entities"]) > 0

        # Check that Rafale and CVE-2024-38077 exist
        ent_names = [e["name"] for e in und_data["key_entities"]]
        assert any("Rafale" in n for n in ent_names)

        sens_terms = [s["term"] for s in und_data["sensitive_terms"]]
        assert "TOP SECRET" in sens_terms or "CVE-2024-38077" in sens_terms

        # 5. Semantic Vector Search against Qdrant
        search_payload = {
            "query": "Rafale combat fighter aircraft and S-400 missiles",
            "doc_id": doc_id,
            "top_k": 3,
        }
        search_resp = await ac.post("/api/v1/understand/search/semantic", json=search_payload)
        assert search_resp.status_code == 200
        search_data = search_resp.json()
        assert search_data["total_results"] > 0
        returned_texts = [r["text"] for r in search_data["results"]]
        assert any("Rafale" in t or "S-400" in t for t in returned_texts)
        assert search_data["results"][0]["score"] > 0.0

        # 6. FalkorDB Graph Visualization & Entity Query
        graph_resp = await ac.get(f"/api/v1/understand/documents/{doc_id}/graph")
        assert graph_resp.status_code == 200
        graph_data = graph_resp.json()
        assert len(graph_data["nodes"]) > 0
        assert len(graph_data["edges"]) > 0

        entity_query_resp = await ac.get("/api/v1/understand/graph/entity/Rafale")
        assert entity_query_resp.status_code == 200
        eq_data = entity_query_resp.json()
        assert eq_data["entity_name"] == "Rafale"
        assert len(eq_data["referenced_chunks"]) > 0

        # 7. Verify cryptographic audit chain integrity
        audit_verify_resp = await ac.get("/api/v1/audit/verify-chain")
        assert audit_verify_resp.status_code == 200
        audit_data = audit_verify_resp.json()
        assert audit_data["valid"] is True
        assert audit_data["total_records"] >= 2  # upload + process_understanding


def test_local_embedder_bge_query_prefix_and_neural_status():
    """Verify BGE asymmetric query prefixing and high-fidelity neural model loading."""
    embedder = get_local_embedder()
    assert embedder.is_neural is True, "FastEmbed ONNX weights must be active in air-gapped enclave"

    query = "integrated border surveillance and air defense network"
    passage_rel = "air defense missiles and radar systems deployed across the northern sector"
    passage_irrel = "fresh farm butter, flour, sugar and strawberries baked in oven"

    q_vec = embedder.embed_query(query)
    rel_vec = embedder.embed_text(passage_rel)
    irrel_vec = embedder.embed_text(passage_irrel)

    assert len(q_vec) == embedder.dimension
    assert len(rel_vec) == embedder.dimension
    assert len(irrel_vec) == embedder.dimension

    score_rel = float(np.dot(np.array(q_vec), np.array(rel_vec)))
    score_irrel = float(np.dot(np.array(q_vec), np.array(irrel_vec)))

    assert score_rel > 0.50, f"Relevant similarity should be high ({score_rel})"
    assert score_rel - score_irrel > 0.25, f"Discriminative margin ({score_rel - score_irrel}) must exceed 0.25"


def test_local_embedder_initialize_prewarm():
    """Verify FastEmbed initialize pre-warms RAM with zero errors."""
    embedder = get_local_embedder()
    assert embedder.initialize() is True


def test_semantic_chunker_overlap_provenance():
    """Verify that chunking with sentence overlap preserves 100% slice provenance."""
    chunker = SemanticChunker(min_chunk_chars=100, target_chunk_chars=200, max_chunk_chars=350, overlap_chars=80)
    chunks = chunker.chunk_text(SAMPLE_DOCUMENT_TEXT)

    assert len(chunks) >= 3
    for idx, c in enumerate(chunks):
        assert c.verify_provenance(SAMPLE_DOCUMENT_TEXT) is True, f"Chunk {idx} violated provenance"
        assert SAMPLE_DOCUMENT_TEXT[c.char_offset_start : c.char_offset_end] == c.text

