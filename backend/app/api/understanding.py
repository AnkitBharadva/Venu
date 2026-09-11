"""Understanding and Chunking API Router for Phase 2.

Exposes:
- POST /api/v1/understand/process/{doc_id}
- GET  /api/v1/understand/documents/{doc_id}/chunks
- GET  /api/v1/understand/documents/{doc_id}/understanding
- GET  /api/v1/understand/documents/{doc_id}/graph
- POST /api/v1/understand/search/semantic
- GET  /api/v1/understand/graph/entity/{name}
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.understanding import (
    ChunkResponse,
    DocumentUnderstandingResponse,
    EntityGraphQueryResponse,
    GraphVisualizationResponse,
    ProcessDocumentResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.storage.falkordb_service import get_falkordb_service
from app.services.storage.qdrant_service import get_qdrant_service
from app.services.understanding_service import (
    get_document_chunks_service,
    get_document_understanding_service,
    process_document_understanding,
)

router = APIRouter(prefix="/api/v1/understand", tags=["Understanding & Chunking"])


@router.post(
    "/process/{doc_id}",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process document through semantic chunking, entity extraction, embeddings, and graph indexing",
)
async def process_document(
    doc_id: uuid.UUID,
    actor: str = Query(default="operator_default", description="Identifier of operator triggering processing"),
    session: AsyncSession = Depends(get_db),
) -> ProcessDocumentResponse:
    """Run full Phase 2 pipeline for a source document.

    Generates semantically coherent chunks, extracts entities/intent/topics/sensitive terms,
    computes 384-dimensional dense vectors, upserts into Qdrant, builds FalkorDB knowledge graph,
    and commits a cryptographically chained audit log entry.
    """
    try:
        response = await process_document_understanding(session=session, doc_id=doc_id, actor=actor)
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document understanding: {exc}",
        ) from exc


@router.get(
    "/documents/{doc_id}/chunks",
    response_model=list[ChunkResponse],
    summary="Retrieve all semantic chunks for a document with exact character offsets",
)
async def get_document_chunks(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ChunkResponse]:
    """Retrieve addressable chunks for document with exact offset verification."""
    chunks = await get_document_chunks_service(session=session, doc_id=doc_id)
    if not chunks:
        # Check if doc exists
        from sqlalchemy import select

        from app.models.audit_log import SourceDocument
        stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source document '{doc_id}' not found.",
            )
    return chunks


@router.get(
    "/documents/{doc_id}/understanding",
    response_model=DocumentUnderstandingResponse,
    summary="Retrieve extracted intent, topics, entities, and sensitive terms",
)
async def get_document_understanding(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DocumentUnderstandingResponse:
    """Retrieve understanding analysis for a document."""
    res = await get_document_understanding_service(session=session, doc_id=doc_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Understanding not found for document '{doc_id}'. Please run /process/{doc_id} first.",
        )
    return res


@router.get(
    "/documents/{doc_id}/graph",
    response_model=GraphVisualizationResponse,
    summary="Retrieve knowledge graph topology for document visualization",
)
async def get_document_graph(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> GraphVisualizationResponse:
    """Retrieve graph nodes and edges for visualization in frontend."""
    falkor = get_falkordb_service()
    res = falkor.get_document_graph(doc_id=doc_id)
    if not res.nodes or len(res.nodes) <= 1:
        from sqlalchemy import select
        from app.models.understanding import DocumentUnderstanding, DocumentChunk
        from app.models.audit_log import SourceDocument
        from app.schemas.understanding import ExtractedChunk, EntityMention, EntityRelationship

        und_stmt = select(DocumentUnderstanding).where(DocumentUnderstanding.doc_id == doc_id)
        und_row = (await session.execute(und_stmt)).scalar_one_or_none()

        chunk_stmt = select(DocumentChunk).where(DocumentChunk.doc_id == doc_id).order_by(DocumentChunk.chunk_index)
        chunk_rows = (await session.execute(chunk_stmt)).scalars().all()

        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
        doc_row = (await session.execute(doc_stmt)).scalar_one_or_none()

        if und_row and chunk_rows:
            extracted_chunks = [
                ExtractedChunk(
                    chunk_id=c.chunk_id,
                    chunk_index=c.chunk_index,
                    text=c.text,
                    char_offset_start=c.char_offset_start,
                    char_offset_end=c.char_offset_end,
                    page_number=c.page_number,
                    heading=c.heading,
                )
                for c in chunk_rows
            ]
            key_entities = [EntityMention(**e) for e in (und_row.key_entities or [])]
            relationships = [EntityRelationship(**r) for r in (und_row.relationships or [])]
            topics = und_row.topics or []
            filename = doc_row.original_filename if doc_row else "Document"

            await falkor.upsert_document_graph(
                doc_id=doc_id,
                filename=filename,
                chunks=extracted_chunks,
                entities=key_entities,
                relationships=relationships,
                topics=topics,
            )
            res = falkor.get_document_graph(doc_id=doc_id)
    return res


@router.post(
    "/search/semantic",
    response_model=SemanticSearchResponse,
    summary="Vector semantic search against Qdrant collection",
)
async def semantic_search(
    request: SemanticSearchRequest,
) -> SemanticSearchResponse:
    """Query Qdrant collection with topic or natural language phrase.

    Returns ranked chunks with cosine similarity score, character offsets, and structural metadata.
    """
    qdrant = get_qdrant_service()
    hits = qdrant.search_chunks(
        query=request.query,
        doc_id=request.doc_id,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
    )
    return SemanticSearchResponse(
        query=request.query,
        total_results=len(hits),
        results=hits,
    )


@router.get(
    "/graph/entity/{name}",
    response_model=EntityGraphQueryResponse,
    summary="Query FalkorDB knowledge graph for an entity and its relations",
)
async def query_entity(
    name: str,
) -> EntityGraphQueryResponse:
    """Query knowledge graph for an entity, its connected nodes, relations, and referencing chunks."""
    falkor = get_falkordb_service()
    return await falkor.query_entity_graph(entity_name=name)
