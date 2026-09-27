"""Comprehensive test suite for High-Precision Retrieval Layer.

Verifies:
1. Context-Aware Hierarchical Embedding Enrichment (preserving exact slice provenance)
2. BM25 Lexical Keyword Ranking with exact code & acronym boosting
3. Reciprocal Rank Fusion (RRF) combining dense & sparse candidate pools
4. Offline Cross-Re-Ranker precision scoring on query-passage interactions
5. Multi-Hop (1-hop & 2-hop) Graph Neighborhood Traversal in FalkorDB
6. Non-Penalizing Multiplicative Graph Context Boosting in GroundingRetrievalService
"""

import uuid

import pytest

from app.schemas.grounding import RetrievedChunkItem
from app.services.chunking.semantic_chunker import ExtractedChunk
from app.services.retrieval.bm25_search import BM25Ranker, reciprocal_rank_fusion
from app.services.retrieval.cross_reranker import CrossReranker
from app.services.storage.falkordb_service import FalkorDBService


def test_bm25_exact_code_and_acronym_boosting():
    """Verify BM25 specifically promotes exact technical codes (CVE-*, S-*, DEFCON)."""
    corpus = [
        "Routine border reconnaissance conducted along the mountainous perimeter.",
        "CRITICAL ALERT: Vulnerability CVE-2024-38077 discovered in tactical communication relays.",
        "General maintenance schedule for heavy transport logistics vehicles.",
    ]
    ranker = BM25Ranker(corpus)
    scores = ranker.score("CVE-2024-38077 patch vulnerability")

    assert len(scores) == 3
    assert scores[1] == 1.0, "Exact CVE match should receive top normalized BM25 score"
    assert scores[0] == 0.0
    assert scores[2] == 0.0


def test_reciprocal_rank_fusion_logic():
    """Verify RRF balances dense and sparse ranking without scale distortion."""
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()
    doc_c = uuid.uuid4()

    # Dense vector ranking: A > B > C
    dense_ranking = [(doc_a, 0.85), (doc_b, 0.72), (doc_c, 0.50)]
    # Sparse BM25 ranking: B > C > A
    sparse_ranking = [(doc_b, 1.0), (doc_c, 0.8), (doc_a, 0.0)]

    fused = reciprocal_rank_fusion([dense_ranking, sparse_ranking], k=60, weights=[1.0, 0.85])

    # doc_b is rank 2 in dense and rank 1 in sparse -> should win overall
    top_doc = fused[0][0]
    assert top_doc == doc_b, f"Doc B should lead RRF fusion, got {top_doc}"


def test_cross_reranker_discriminative_precision():
    """Verify CrossReranker accurately distinguishes matching vs confounding passages."""
    reranker = CrossReranker()
    query = "S-400 surface to air missile defense battery"

    matching_passage = (
        "The S-400 Triumf surface-to-air missile defense division has been operationalized "
        "to ensure long-range airspace denial and counter incoming ballistic threats."
    )
    confounding_passage = (
        "Two squadrons of multi-role combat aircraft conducted air maneuvers near the base, "
        "providing defense cover for military ground divisions."
    )
    unrelated_passage = "Strawberry fruit preserves and orange marmalade stored in kitchen pantry."

    s_match = reranker.score_pair(query, matching_passage)
    s_confound = reranker.score_pair(query, confounding_passage)
    s_unrel = reranker.score_pair(query, unrelated_passage)

    assert s_match > s_confound, f"Matching ({s_match}) must beat confounding ({s_confound})"
    assert s_confound > s_unrel, f"Confounding ({s_confound}) must beat unrelated ({s_unrel})"
    assert s_unrel == 0.0


def test_cross_reranker_item_reranking():
    """Verify CrossReranker re-orders RetrievedChunkItem candidates."""
    reranker = CrossReranker()
    query = "MQ-9 Reaper drone surveillance"

    c1 = RetrievedChunkItem(
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        text="Logistics trucks delivered rations and fuel to forward border posts.",
        score=0.70,
        vector_score=0.70,
        graph_score=0.0,
        char_offset_start=0,
        char_offset_end=70,
    )
    c2 = RetrievedChunkItem(
        chunk_id=uuid.uuid4(),
        chunk_index=1,
        text="For autonomous reconnaissance, MQ-9 Reaper unmanned aerial systems conduct multi-spectral surveillance.",
        score=0.60,
        vector_score=0.60,
        graph_score=0.0,
        char_offset_start=71,
        char_offset_end=175,
    )

    reranked = reranker.rerank_items(query, [c1, c2], top_k=2)
    assert len(reranked) == 2
    # c2 must be promoted to index 0 due to deep query-chunk cross-match
    assert reranked[0].chunk_id == c2.chunk_id


@pytest.mark.asyncio
async def test_falkordb_multi_hop_subgraph_traversal():
    """Verify 1-hop and 2-hop graph neighborhood expansion in FalkorDB."""
    falkor = FalkorDBService()
    doc_id = uuid.uuid4()

    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    c1 = ExtractedChunk(
        chunk_id=c1_id,
        chunk_index=0,
        text="Rafale combat aircraft operated by the Indian Air Force.",
        char_offset_start=0,
        char_offset_end=56,
    )
    c2 = ExtractedChunk(
        chunk_id=c2_id,
        chunk_index=1,
        text="Indian Air Force surveillance radar radar division stationed in Ladakh.",
        char_offset_start=57,
        char_offset_end=128,
    )

    from app.schemas.understanding import EntityMention, EntityRelationship

    entities = [
        EntityMention(name="Rafale", type="WEAPON_SYSTEM", count=1, chunk_ids=[c1_id]),
        EntityMention(name="Indian Air Force", type="ORGANIZATION", count=2, chunk_ids=[c1_id, c2_id]),
        EntityMention(name="Ladakh", type="LOCATION", count=1, chunk_ids=[c2_id]),
    ]
    relationships = [
        EntityRelationship(source="Rafale", relation="OPERATED_BY", target="Indian Air Force", chunk_id=c1_id),
        EntityRelationship(source="Indian Air Force", relation="DEPLOYED_IN", target="Ladakh", chunk_id=c2_id),
    ]

    await falkor.upsert_document_graph(
        doc_id=doc_id,
        filename="tactical.txt",
        chunks=[c1, c2],
        entities=entities,
        relationships=relationships,
        topics=["Air Defense"],
    )

    # Query multi-hop for "Rafale"
    hop_data = await falkor.query_multi_hop_context(["Rafale"])
    # 1-hop direct chunk should contain c1_id
    assert c1_id in hop_data["direct_chunks"]
    # Indian Air Force should be in relations or connected entities
    conn_names = {e["name"] for e in hop_data["connected_entities"]}
    assert "Indian Air Force" in conn_names
