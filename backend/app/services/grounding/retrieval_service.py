"""Hybrid Grounding Retrieval Service for Phase 3.

Combines Qdrant dense vector similarity retrieval with FalkorDB openCypher
knowledge graph traversal to produce grounded, cross-referenced context for
downstream generation adapters.
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
from app.services.storage.falkordb_service import get_falkordb_service
from app.services.storage.qdrant_service import get_qdrant_service

logger = logging.getLogger("app.services.grounding.retrieval")


class GroundingRetrievalService:
    """Orchestrates hybrid vector-graph contextual retrieval for generation adapters."""

    @classmethod
    async def retrieve_grounded_context(
        cls,
        session: AsyncSession,
        query: str,
        doc_id: uuid.UUID,
        top_k: int = 5,
        include_graph: bool = True,
        alpha: float = 0.7,
    ) -> GroundedContextResponse:
        """Fetch top-k relevant chunks from Qdrant merged with related entities from FalkorDB."""
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

        # 3. Dense Vector Retrieval (Qdrant)
        qdrant = get_qdrant_service()
        candidate_k = max(top_k * 2, 8)
        vector_hits = qdrant.search_chunks(
            query=query,
            doc_id=doc_id,
            top_k=candidate_k,
            score_threshold=0.0,
        )

        # 4. FalkorDB Knowledge Graph Traversal
        falkor = get_falkordb_service()
        query_lower = query.lower()

        matched_graph_entities: list[dict[str, Any]] = []
        matched_relationships: list[dict[str, Any]] = []
        graph_boosted_chunk_ids: dict[uuid.UUID, float] = {}

        if include_graph:
            # Match entities in query
            for ent in key_entities:
                ent_name = ent.get("name", "")
                if ent_name.lower() in query_lower:
                    matched_graph_entities.append(ent)
                    # Query FalkorDB for connected entity neighborhood
                    ent_graph_data = await falkor.query_entity_graph(ent_name)
                    for chunk_id in ent_graph_data.referenced_chunks:
                        graph_boosted_chunk_ids[chunk_id] = graph_boosted_chunk_ids.get(chunk_id, 0.0) + 0.35

                    for rel in ent_graph_data.direct_relations:
                        matched_relationships.append({
                            "source": ent_name,
                            "relation": rel.get("relation"),
                            "target": rel.get("target"),
                        })

            # Check relationships directly matching query terms
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

        # 5. Hybrid Ranking & Score Merging
        # Map of chunk_id -> RetrievedChunkItem candidate
        ranked_candidates: list[RetrievedChunkItem] = []

        # If vector search returned hits
        vector_map = {hit.chunk_id: hit for hit in vector_hits}

        # Ensure all chunks in vector hits are considered
        candidate_chunk_ids = set(vector_map.keys()).union(graph_boosted_chunk_ids.keys())
        if not candidate_chunk_ids:
            # Fallback: take first chunks from doc
            candidate_chunk_ids = set(list(all_chunks.keys())[:top_k])

        for c_id in candidate_chunk_ids:
            chunk = all_chunks.get(c_id)
            if not chunk:
                continue

            hit = vector_map.get(c_id)
            vec_score = hit.score if hit else 0.05
            graph_score = min(graph_boosted_chunk_ids.get(c_id, 0.0), 1.0)

            # Composite hybrid score
            composite = (alpha * vec_score) + ((1.0 - alpha) * graph_score)

            # Entities present in this chunk
            ents_in_chunk = [
                e.get("name", "") for e in key_entities
                if any(str(c_id) == str(cid) for cid in e.get("chunk_ids", []))
            ]

            ranked_candidates.append(
                RetrievedChunkItem(
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    score=round(composite, 4),
                    vector_score=round(vec_score, 4),
                    graph_score=round(graph_score, 4),
                    char_offset_start=chunk.char_offset_start,
                    char_offset_end=chunk.char_offset_end,
                    heading=chunk.heading,
                    page_number=chunk.page_number,
                    timestamp_start=chunk.timestamp_start,
                    timestamp_end=chunk.timestamp_end,
                    entities_present=ents_in_chunk,
                )
            )

        # Sort descending by composite score
        ranked_candidates.sort(key=lambda x: x.score, reverse=True)
        final_chunks = ranked_candidates[:top_k]

        # 6. Formatted Merged Context for Generation Adapters
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
