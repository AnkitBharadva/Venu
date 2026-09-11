"""Qdrant Vector Store Service for Phase 2.

Manages 384-dimensional dense vector indexing, payload metadata storage,
and high-precision cosine semantic chunk retrieval.
Includes resilient offline fallback for local tests and bootstrap.
"""

import logging
import uuid
from typing import Any

import numpy as np
from qdrant_client.http import models

from app.core.config import get_settings
from app.core.qdrant_client import get_qdrant_client
from app.schemas.understanding import SemanticSearchResultItem
from app.services.chunking.semantic_chunker import ExtractedChunk
from app.services.embeddings.local_embedder import get_local_embedder

logger = logging.getLogger("app.services.storage.qdrant")
settings = get_settings()


class QdrantService:
    """Service wrapper for Qdrant vector index operations with in-memory fallback."""

    def __init__(self, collection_name: str | None = None) -> None:
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_DEFAULT
        self.dimension = settings.EMBEDDING_DIMENSION
        self._in_memory_store: dict[str, dict[str, Any]] = {}
        self._live_available: bool | None = None

    def _is_live(self) -> bool:
        """Check if live Qdrant container is reachable via fast non-blocking probe."""
        from app.core.qdrant_client import is_qdrant_live
        if self._live_available is not None:
            return self._live_available
        self._live_available = is_qdrant_live(timeout=0.15)
        return self._live_available

    def ensure_collection(self) -> bool:
        """Create Qdrant collection if it does not already exist."""
        if not self._is_live():
            # In-memory store is always ready
            return True

        try:
            client = get_qdrant_client()
            collections = client.get_collections().collections
            existing = {c.name for c in collections}

            if self.collection_name not in existing:
                logger.info("Creating Qdrant collection '%s' (dim: %d, Cosine)", self.collection_name, self.dimension)
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.dimension,
                        distance=models.Distance.COSINE,
                    ),
                )
            return True
        except Exception as exc:
            logger.warning("Failed to initialize Qdrant collection '%s': %s", self.collection_name, exc)
            return False

    def upsert_chunks(
        self,
        chunks: list[ExtractedChunk],
        embeddings: list[list[float]],
        doc_id: uuid.UUID,
    ) -> int:
        """Upsert chunk points with dense vector and rich metadata payload."""
        if not chunks or not embeddings:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatched chunks ({len(chunks)}) and embeddings ({len(embeddings)})")

        points: list[models.PointStruct] = []
        for chunk, emb in zip(chunks, embeddings, strict=True):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_{chunk.chunk_index}"))
            payload = {
                "doc_id": str(doc_id),
                "chunk_id": str(chunk.chunk_id),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "char_offset_start": chunk.char_offset_start,
                "char_offset_end": chunk.char_offset_end,
                "page_number": chunk.page_number,
                "heading": chunk.heading,
                "timestamp_start": chunk.timestamp_start,
                "timestamp_end": chunk.timestamp_end,
                "metadata": chunk.metadata,
            }

            # Always populate in-memory store for fallback retrieval
            self._in_memory_store[point_id] = {
                "id": point_id,
                "vector": emb,
                "payload": payload,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=payload,
                )
            )

        if self._is_live():
            try:
                self.ensure_collection()
                client = get_qdrant_client()
                client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True,
                )
                logger.info("Successfully upserted %d chunk vectors to Qdrant", len(points))
            except Exception as exc:
                logger.warning("Live Qdrant upsert failed (%s). Kept in fallback memory store.", exc)

        return len(points)

    def search_chunks(
        self,
        query: str,
        doc_id: uuid.UUID | None = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[SemanticSearchResultItem]:
        """Perform semantic similarity retrieval against chunk vectors."""
        embedder = get_local_embedder()
        query_vector = embedder.embed_text(query)

        results: list[SemanticSearchResultItem] = []

        if self._is_live():
            try:
                client = get_qdrant_client()
                q_filter = None
                if doc_id:
                    q_filter = models.Filter(
                        must=[
                            models.FieldCondition(
                                key="doc_id",
                                match=models.MatchValue(value=str(doc_id)),
                            )
                        ]
                    )

                if hasattr(client, "query_points"):
                    query_response = client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=q_filter,
                        limit=top_k,
                        score_threshold=score_threshold,
                    )
                    search_res = query_response.points
                else:
                    search_res = client.search(
                        collection_name=self.collection_name,
                        query_vector=query_vector,
                        query_filter=q_filter,
                        limit=top_k,
                        score_threshold=score_threshold,
                    )

                for hit in search_res:
                    payload = hit.payload or {}
                    results.append(
                        SemanticSearchResultItem(
                            chunk_id=uuid.UUID(str(payload.get("chunk_id"))),
                            doc_id=uuid.UUID(str(payload.get("doc_id"))),
                            chunk_index=int(payload.get("chunk_index", 0)),
                            text=str(payload.get("text", "")),
                            score=round(float(hit.score), 4),
                            char_offset_start=int(payload.get("char_offset_start", 0)),
                            char_offset_end=int(payload.get("char_offset_end", 0)),
                            heading=payload.get("heading"),
                            page_number=payload.get("page_number"),
                            timestamp_start=payload.get("timestamp_start"),
                            timestamp_end=payload.get("timestamp_end"),
                        )
                    )
                if results:
                    return results
            except Exception as exc:
                logger.warning("Live Qdrant search failed (%s). Falling back to in-memory index.", exc)

        # Fallback to In-Memory Exact Cosine Search
        scored_items: list[tuple[float, dict[str, Any]]] = []
        q_norm = np.array(query_vector, dtype=np.float32)

        for item in self._in_memory_store.values():
            payload = item["payload"]
            if doc_id and payload.get("doc_id") != str(doc_id):
                continue

            v = np.array(item["vector"], dtype=np.float32)
            cosine_score = float(np.dot(q_norm, v))

            if cosine_score >= score_threshold:
                scored_items.append((cosine_score, payload))

        # Sort descending by score
        scored_items.sort(key=lambda x: x[0], reverse=True)

        for score, p in scored_items[:top_k]:
            results.append(
                SemanticSearchResultItem(
                    chunk_id=uuid.UUID(str(p["chunk_id"])),
                    doc_id=uuid.UUID(str(p["doc_id"])),
                    chunk_index=int(p.get("chunk_index", 0)),
                    text=str(p.get("text", "")),
                    score=round(score, 4),
                    char_offset_start=int(p.get("char_offset_start", 0)),
                    char_offset_end=int(p.get("char_offset_end", 0)),
                    heading=p.get("heading"),
                    page_number=p.get("page_number"),
                    timestamp_start=p.get("timestamp_start"),
                    timestamp_end=p.get("timestamp_end"),
                )
            )

        return results

    def delete_document_chunks(self, doc_id: uuid.UUID) -> bool:
        """Delete all vectors and payload for a given doc_id."""
        # Clean from memory
        keys_to_del = [k for k, v in self._in_memory_store.items() if v["payload"].get("doc_id") == str(doc_id)]
        for k in keys_to_del:
            self._in_memory_store.pop(k, None)

        if self._is_live():
            try:
                client = get_qdrant_client()
                client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=str(doc_id)))]
                        )
                    ),
                )
                return True
            except Exception as exc:
                logger.warning("Failed to delete Qdrant points for doc %s: %s", doc_id, exc)
                return False

        return True

    def clear_all(self) -> bool:
        """Clear all vectors from Qdrant and reset in-memory store."""
        self._in_memory_store.clear()
        if self._is_live():
            try:
                client = get_qdrant_client()
                collections = client.get_collections().collections
                existing = {c.name for c in collections}
                if self.collection_name in existing:
                    client.delete_collection(collection_name=self.collection_name)
                self.ensure_collection()
                logger.info("Qdrant collection '%s' reset successfully.", self.collection_name)
                return True
            except Exception as exc:
                logger.warning("Failed to reset Qdrant collection: %s", exc)
                return False
        return True


_qdrant_service_instance: QdrantService | None = None


def get_qdrant_service() -> QdrantService:
    global _qdrant_service_instance
    if _qdrant_service_instance is None:
        _qdrant_service_instance = QdrantService()
    return _qdrant_service_instance
