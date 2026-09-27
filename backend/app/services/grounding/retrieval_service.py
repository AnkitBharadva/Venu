"""High-Precision Hybrid Grounding Retrieval Service for Phase 3.

Combines:
1. Qdrant dense vector similarity retrieval with asymmetric BGE query prefix
2. BM25 lexical ranking for exact technical codes, acronyms, and keywords
3. Reciprocal Rank Fusion (RRF) for scale-invariant dense-sparse merge
4. FalkorDB multi-hop (1-hop & 2-hop) openCypher knowledge graph neighborhood expansion
5. Cross-Encoder precision re-ranking for joint query-passage attention
6. Non-penalizing multiplicative graph boost ensuring relevant passages are never diluted
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.understanding import DocumentChunk, DocumentUnderstanding
from app.schemas.grounding import (
    GroundedContextResponse,
    RetrievedChunkItem,
    RetrievedGraphContext,
)
from app.services.retrieval.bm25_search import BM25Ranker, reciprocal_rank_fusion
from app.services.retrieval.cross_reranker import CrossReranker
from app.services.storage.falkordb_service import get_falkordb_service
from app.services.storage.qdrant_service import get_qdrant_service

logger = logging.getLogger("app.services.grounding.retrieval")


class GroundingRetrievalService:
    """Orchestrates hybrid vector-lexical-graph contextual retrieval for generation adapters."""

    @classmethod
    async def retrieve_grounded_context(
        cls,
        session: AsyncSession,
        query: str,
        doc_id: uuid.UUID,
        top_k: int = 5,
        include_graph: bool = True,
        alpha: float = 0.7,
        enable_rerank: bool = True,
    ) -> GroundedContextResponse:
        """Fetch top-k relevant chunks using Hybrid Dense-Sparse RRF + Multi-Hop Graph + Cross-Reranker."""
        # 1. Fetch all chunks for this doc to map metadata and verify existence
        stmt = select(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
        res = await session.execute(stmt)
        all_chunks = {c.chunk_id: c for c in res.scalars().all()}

        if not all_chunks:
            raise ValueError(f"No processed chunks found for document '{doc_id}'. Please run /process/{doc_id} first.")

        # 2. Fetch DocumentUnderstanding for entity mappings
        und_stmt = select(DocumentUnderstanding).where(DocumentUnderstanding.doc_id == doc_id)
        und_res = await session.execute(und_stmt)
        understanding = und_res.scalar_one_or_none()

        key_entities: list[dict[str, Any]] = understanding.key_entities if understanding else []
        relationships: list[dict[str, Any]] = understanding.relationships if understanding else []
        topics: list[str] = understanding.topics if understanding else []

        candidate_k = max(top_k * 3, 12)

        # 3. Dense Vector Retrieval (Qdrant)
        qdrant = get_qdrant_service()
        vector_hits = qdrant.search_chunks(
            query=query,
            doc_id=doc_id,
            top_k=candidate_k,
            score_threshold=0.0,
        )
        vector_map = {hit.chunk_id: hit for hit in vector_hits}
        dense_ranked = [(hit.chunk_id, hit.score) for hit in vector_hits]

        # 4. Sparse Lexical BM25 Retrieval
        chunk_list = list(all_chunks.values())
        bm25_ranker = BM25Ranker([c.text for c in chunk_list])
        bm25_scores = bm25_ranker.score(query)
        bm25_map: dict[uuid.UUID, float] = {}
        bm25_ranked: list[tuple[uuid.UUID, float]] = []

        for c, s in zip(chunk_list, bm25_scores, strict=True):
            bm25_map[c.chunk_id] = s
            if s > 0.0:
                bm25_ranked.append((c.chunk_id, s))

        bm25_ranked.sort(key=lambda x: x[1], reverse=True)

        # 5. Reciprocal Rank Fusion (Dense + Sparse)
        rrf_fused = reciprocal_rank_fusion(
            ranked_lists=[dense_ranked, bm25_ranked],
            k=60,
            weights=[alpha, 1.0 - alpha + 0.15],
        )

        # 6. FalkorDB Multi-Hop Knowledge Graph Traversal
        falkor = get_falkordb_service()
        query_lower = query.lower()

        matched_graph_entities: list[dict[str, Any]] = []
        matched_relationships: list[dict[str, Any]] = []
        graph_boosted_chunk_ids: dict[uuid.UUID, float] = {}

        if include_graph:
            # Fuzzy and substring entity matching
            matched_entity_names: list[str] = []
            for ent in key_entities:
                ent_name = ent.get("name", "")
                ent_name_lower = ent_name.lower()
                # Substring match or significant token match
                if ent_name_lower in query_lower or any(
                    len(tok) > 3 and tok in query_lower for tok in ent_name_lower.split()
                ):
                    matched_graph_entities.append(ent)
                    matched_entity_names.append(ent_name)

            if matched_entity_names:
                # Multi-hop graph expansion (1-hop direct + 2-hop neighbor chunks)
                multi_hop_data = await falkor.query_multi_hop_context(matched_entity_names)
                for cid in multi_hop_data["direct_chunks"]:
                    graph_boosted_chunk_ids[cid] = graph_boosted_chunk_ids.get(cid, 0.0) + 0.40

                for cid in multi_hop_data["hop2_chunks"]:
                    graph_boosted_chunk_ids[cid] = graph_boosted_chunk_ids.get(cid, 0.0) + 0.20

                for rel in multi_hop_data["relations"]:
                    if rel not in matched_relationships:
                        matched_relationships.append(rel)

            # Check explicit relationships matching query terms
            for rel in relationships:
                s = rel.get("source", "").lower()
                t = rel.get("target", "").lower()
                if s in query_lower or t in query_lower:
                    if rel not in matched_relationships:
                        matched_relationships.append(rel)
                    cid = rel.get("chunk_id")
                    if cid:
                        try:
                            uid = uuid.UUID(str(cid))
                            graph_boosted_chunk_ids[uid] = graph_boosted_chunk_ids.get(uid, 0.0) + 0.25
                        except ValueError:
                            pass

        # 7. Form Candidate Pool
        # Union of top RRF chunks + graph boosted chunks
        candidate_ids: list[uuid.UUID] = []
        seen_cids: set[uuid.UUID] = set()

        for cid, _ in rrf_fused[:candidate_k]:
            if cid not in seen_cids:
                seen_cids.add(cid)
                candidate_ids.append(cid)

        for cid in graph_boosted_chunk_ids.keys():
            if cid not in seen_cids and cid in all_chunks:
                seen_cids.add(cid)
                candidate_ids.append(cid)

        if not candidate_ids:
            candidate_ids = list(all_chunks.keys())[:candidate_k]

        # 8. Assemble RetrievedChunkItem candidates
        candidate_items: list[RetrievedChunkItem] = []
        for c_id in candidate_ids:
            chunk = all_chunks.get(c_id)
            if not chunk:
                continue

            hit = vector_map.get(c_id)
            vec_score = hit.score if hit else 0.0
            bm25_s = bm25_map.get(c_id, 0.0)
            g_boost = min(graph_boosted_chunk_ids.get(c_id, 0.0), 1.0)

            # Initial hybrid blend
            if vec_score > 0.0 and bm25_s > 0.0:
                base_score = (0.65 * vec_score) + (0.35 * bm25_s)
            elif vec_score > 0.0:
                base_score = vec_score
            else:
                base_score = 0.5 * bm25_s + 0.2

            ents_in_chunk = [
                e.get("name", "") for e in key_entities
                if any(str(c_id) == str(cid) for cid in e.get("chunk_ids", []))
            ]

            candidate_items.append(
                RetrievedChunkItem(
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    score=round(base_score, 4),
                    vector_score=round(vec_score, 4),
                    graph_score=round(g_boost, 4),
                    bm25_score=round(bm25_s, 4),
                    rerank_score=0.0,
                    char_offset_start=chunk.char_offset_start,
                    char_offset_end=chunk.char_offset_end,
                    heading=chunk.heading,
                    page_number=chunk.page_number,
                    timestamp_start=chunk.timestamp_start,
                    timestamp_end=chunk.timestamp_end,
                    entities_present=ents_in_chunk,
                )
            )

        # 9. Cross-Encoder Re-Ranking
        if enable_rerank and len(candidate_items) > 1:
            reranker = CrossReranker()
            candidate_items = reranker.rerank_items(query, candidate_items, top_k=candidate_k)
            for item in candidate_items:
                item.rerank_score = item.score

        # 10. Non-Penalizing Graph Context Boosting
        for item in candidate_items:
            if item.graph_score > 0.0:
                boosted = item.score * (1.0 + (0.35 * item.graph_score))
                item.score = round(min(boosted, 1.0), 4)

        # Sort descending by final score
        candidate_items.sort(key=lambda x: x.score, reverse=True)
        final_chunks = candidate_items[:top_k]

        # 11. Formatted Merged Context for Generation Adapters
        merged_blocks = []
        for c in final_chunks:
            hd = f" [Section: {c.heading}]" if c.heading else ""
            pg = f" [Page: {c.page_number}]" if c.page_number else ""
            ts = f" [Time: {c.timestamp_start:.1f}s-{c.timestamp_end:.1f}s]" if c.timestamp_start is not None else ""
            header = f"=== CHUNK #{c.chunk_index} (ID: {c.chunk_id}){hd}{pg}{ts} ==="
            merged_blocks.append(f"{header}\n{c.text}")

        merged_context = "\n\n".join(merged_blocks)

        graph_context = RetrievedGraphContext(
            matched_entities=matched_graph_entities,
            relationships=matched_relationships[:15],
            active_topics=topics,
        )

        return GroundedContextResponse(
            query=query,
            doc_id=doc_id,
            total_chunks=len(final_chunks),
            retrieved_chunks=final_chunks,
            graph_context=graph_context,
            merged_context_text=merged_context,
        )
