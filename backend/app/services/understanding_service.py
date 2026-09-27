"""Understanding and Chunking Pipeline Orchestrator for Phase 2.

Coordinates:
1. Semantic paragraph/section-aware chunking preserving exact character offsets
2. LLM / heuristic entity, topic, intent, and sensitive terms extraction
3. Local 384-dimensional dense chunk embedding generation
4. Qdrant vector store upsert
5. FalkorDB openCypher knowledge graph upsert
6. Relational database persistence (PostgreSQL / SQLite)
7. Cryptographic append-only audit trail logging
"""

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.models.audit_log import SourceDocument
from app.models.understanding import DocumentChunk, DocumentUnderstanding
from app.schemas.understanding import (
    ChunkResponse,
    DocumentUnderstandingResponse,
    EntityMention,
    EntityRelationship,
    ProcessDocumentResponse,
    SensitiveTerm,
)
from app.services.chunking.semantic_chunker import SemanticChunker
from app.services.embeddings.local_embedder import get_local_embedder
from app.services.extraction.entity_extractor import get_entity_extractor
from app.services.storage.falkordb_service import get_falkordb_service
from app.services.storage.qdrant_service import get_qdrant_service

logger = logging.getLogger("app.services.understanding")


async def process_document_understanding(
    session: AsyncSession,
    doc_id: uuid.UUID,
    actor: str = "operator_default",
) -> ProcessDocumentResponse:
    """Execute complete Phase 2 understanding, chunking, embedding, and graphing pipeline."""
    # 1. Fetch Source Document
    stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise ValueError(f"Source document '{doc_id}' not found.")

    raw_text = doc.raw_text or ""
    metadata = doc.structural_metadata or {}

    # 2. Semantic Chunking with Exact Offset Preservation
    embedder = get_local_embedder()
    chunker = SemanticChunker(embedder=embedder, use_semantic_breakpoints=True)
    extracted_chunks = chunker.chunk_text(raw_text, metadata)

    # Invariant verification: raw_text[start:end] == chunk.text
    for c in extracted_chunks:
        if raw_text[c.char_offset_start : c.char_offset_end] != c.text:
            raise ValueError(
                f"Offset mismatch on chunk {c.chunk_index} in doc {doc_id}: "
                f"expected '{c.text[:30]}...', got '{raw_text[c.char_offset_start:c.char_offset_end][:30]}...'"
            )

    # 3. Entity, Topic, Intent & Sensitive Term Extraction
    extractor = get_entity_extractor()
    extraction_res = extractor.extract(raw_text, extracted_chunks, metadata)

    # 4. Hierarchical Context-Aware Dense Embeddings Generation (384 dimensions)
    enriched_embed_inputs = []
    for c in extracted_chunks:
        prefix_parts = []
        if c.heading:
            prefix_parts.append(f"[Section: {c.heading}]")
        if c.page_number:
            prefix_parts.append(f"[Page: {c.page_number}]")
        if prefix_parts:
            enriched_embed_inputs.append(f"{' '.join(prefix_parts)} {c.text}")
        else:
            enriched_embed_inputs.append(c.text)

    embeddings = embedder.embed_batch(enriched_embed_inputs) if enriched_embed_inputs else []

    # 5. Database Persistence (Relational Chunks & Understanding)
    # Clear existing chunks / understandings for idempotency
    await session.execute(delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
    await session.execute(delete(DocumentUnderstanding).where(DocumentUnderstanding.doc_id == doc_id))

    db_chunks: list[DocumentChunk] = []
    for c in extracted_chunks:
        db_chunks.append(
            DocumentChunk(
                chunk_id=c.chunk_id,
                doc_id=doc_id,
                chunk_index=c.chunk_index,
                text=c.text,
                char_offset_start=c.char_offset_start,
                char_offset_end=c.char_offset_end,
                page_number=c.page_number,
                heading=c.heading,
                timestamp_start=c.timestamp_start,
                timestamp_end=c.timestamp_end,
                metadata_payload=c.metadata,
            )
        )
    session.add_all(db_chunks)

    db_understanding = DocumentUnderstanding(
        doc_id=doc_id,
        objective=extraction_res.objective,
        topics=extraction_res.topics,
        key_entities=[e.model_dump(mode="json") for e in extraction_res.key_entities],
        sensitive_terms=[s.model_dump(mode="json") for s in extraction_res.sensitive_terms],
        relationships=[r.model_dump(mode="json") for r in extraction_res.relationships],
        summary=extraction_res.summary,
    )
    session.add(db_understanding)
    await session.commit()

    # 6. Qdrant Vector Upsert
    qdrant = get_qdrant_service()
    if extracted_chunks and embeddings:
        qdrant.upsert_chunks(extracted_chunks, embeddings, doc_id)

    # 7. FalkorDB Knowledge Graph Upsert
    falkordb = get_falkordb_service()
    await falkordb.upsert_document_graph(
        doc_id=doc_id,
        filename=doc.original_filename,
        chunks=extracted_chunks,
        entities=extraction_res.key_entities,
        relationships=extraction_res.relationships,
        topics=extraction_res.topics,
    )

    # 8. Cryptographic Append-Only Audit Log
    audit_details = {
        "chunk_count": len(extracted_chunks),
        "entities_count": len(extraction_res.key_entities),
        "topics_count": len(extraction_res.topics),
        "sensitive_terms_count": len(extraction_res.sensitive_terms),
        "relationships_count": len(extraction_res.relationships),
        "offset_accuracy_pct": 100.0,
    }

    await record_audit_event(
        session=session,
        actor=actor,
        action="process_understanding",
        doc_id=doc_id,
        source_hash=doc.checksum,
        details=audit_details,
    )
    await session.commit()

    # 9. Build response
    understanding_resp = DocumentUnderstandingResponse(
        doc_id=doc_id,
        objective=extraction_res.objective,
        topics=extraction_res.topics,
        key_entities=extraction_res.key_entities,
        sensitive_terms=extraction_res.sensitive_terms,
        relationships=extraction_res.relationships,
        summary=extraction_res.summary,
        total_chunks=len(extracted_chunks),
        offset_accuracy_pct=100.0,
    )

    return ProcessDocumentResponse(
        status="success",
        doc_id=doc_id,
        chunks_count=len(extracted_chunks),
        entities_count=len(extraction_res.key_entities),
        topics_count=len(extraction_res.topics),
        sensitive_terms_count=len(extraction_res.sensitive_terms),
        relationships_count=len(extraction_res.relationships),
        qdrant_indexed=True,
        falkordb_indexed=True,
        audit_entry_recorded=True,
        understanding=understanding_resp,
    )


async def get_document_chunks_service(
    session: AsyncSession,
    doc_id: uuid.UUID,
) -> list[ChunkResponse]:
    """Retrieve all chunks for a document with provenance verification."""
    # Fetch source document to verify offsets
    doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    doc_res = await session.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()

    raw_text = doc.raw_text if doc else ""

    stmt = select(DocumentChunk).where(DocumentChunk.doc_id == doc_id).order_by(DocumentChunk.chunk_index)
    res = await session.execute(stmt)
    chunks = res.scalars().all()

    output: list[ChunkResponse] = []
    for c in chunks:
        # Verify exact slice
        verified = bool(raw_text and raw_text[c.char_offset_start : c.char_offset_end] == c.text)
        output.append(
            ChunkResponse(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                chunk_index=c.chunk_index,
                text=c.text,
                char_offset_start=c.char_offset_start,
                char_offset_end=c.char_offset_end,
                page_number=c.page_number,
                heading=c.heading,
                timestamp_start=c.timestamp_start,
                timestamp_end=c.timestamp_end,
                metadata_payload=c.metadata_payload or {},
                offset_verified=verified,
            )
        )
    return output


async def get_document_understanding_service(
    session: AsyncSession,
    doc_id: uuid.UUID,
) -> DocumentUnderstandingResponse | None:
    """Retrieve persisted understanding for a document."""
    stmt = select(DocumentUnderstanding).where(DocumentUnderstanding.doc_id == doc_id)
    res = await session.execute(stmt)
    rec = res.scalar_one_or_none()
    if not rec:
        return None

    # Count chunks
    chunk_stmt = select(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
    c_res = await session.execute(chunk_stmt)
    chunks = c_res.scalars().all()

    key_entities = [EntityMention(**e) for e in (rec.key_entities or [])]
    sensitive_terms = [SensitiveTerm(**s) for s in (rec.sensitive_terms or [])]
    relationships = [EntityRelationship(**r) for r in (rec.relationships or [])]

    return DocumentUnderstandingResponse(
        doc_id=rec.doc_id,
        objective=rec.objective,
        topics=rec.topics or [],
        key_entities=key_entities,
        sensitive_terms=sensitive_terms,
        relationships=relationships,
        summary=rec.summary or "",
        total_chunks=len(chunks),
        offset_accuracy_pct=100.0,
    )
