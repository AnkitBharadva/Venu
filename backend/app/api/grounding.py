"""Grounding and Provenance API Router for Phase 3.

Exposes:
- POST /api/v1/grounding/retrieve: Hybrid Qdrant vector + FalkorDB graph retrieval for generation adapters
- GET  /api/v1/grounding/trace: Provenance trace mapping generated sentences back to source chunks & offsets
- GET  /api/v1/grounding/trace/{output_id}/full: Complete deliverable sentence-by-sentence trace
- POST /api/v1/grounding/outputs: Register & persist deliverable with hard claim-citation contract enforcement
- GET  /api/v1/grounding/outputs/{output_id}: Retrieve single deliverable with citation verification status
- GET  /api/v1/grounding/outputs/document/{doc_id}: List all deliverables generated for a document
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.grounding import (
    CreateDeliverableRequest,
    DeliverableResponse,
    FullDeliverableTraceResponse,
    GroundedContextResponse,
    SentenceTraceResponse,
)
from app.services.grounding.contract_enforcer import GroundingContractError
from app.services.grounding.output_service import GroundingOutputService
from app.services.grounding.retrieval_service import GroundingRetrievalService
from app.services.grounding.trace_service import GroundingTraceService

logger = logging.getLogger("app.api.grounding")

router = APIRouter(prefix="/api/v1/grounding", tags=["Grounding & Provenance"])


class RetrieveContextRequest(BaseModel):
    """Request payload for hybrid grounded context retrieval."""

    query: str = Field(..., min_length=1, description="Topic, prompt, or search phrase for adapter grounding")
    doc_id: uuid.UUID = Field(..., description="Target document ID to retrieve from")
    top_k: int = Field(default=5, ge=1, le=25, description="Number of top chunks to return")
    include_graph: bool = Field(default=True, description="Whether to include FalkorDB knowledge graph traversal")
    alpha: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight given to dense vector score vs graph connectivity score (1.0 = purely vector)",
    )


@router.post(
    "/retrieve",
    response_model=GroundedContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve hybrid vector-graph grounded context for generation adapters",
)
async def retrieve_grounded_context(
    request: RetrieveContextRequest,
    session: AsyncSession = Depends(get_db),
) -> GroundedContextResponse:
    """Fetch top-k relevant chunks from Qdrant merged and ranked with FalkorDB entities.

    Used by generation adapters before creating any deliverable to ensure all claims
    are grounded in real document spans.
    """
    try:
        response = await GroundingRetrievalService.retrieve_grounded_context(
            session=session,
            query=request.query,
            doc_id=request.doc_id,
            top_k=request.top_k,
            include_graph=request.include_graph,
            alpha=request.alpha,
        )
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        logger.error("Retrieve context failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid grounding retrieval failed: {exc}",
        ) from exc


@router.get(
    "/trace",
    response_model=SentenceTraceResponse | FullDeliverableTraceResponse,
    summary="Trace generated sentence(s) to original source chunk spans and offsets",
)
async def trace_sentence(
    output_id: uuid.UUID = Query(..., description="ID of generated deliverable"),
    sentence_index: int | None = Query(default=None, description="Optional zero-based sentence index"),
    sentence_id: str | None = Query(default=None, description="Optional sentence ID (e.g. sent_0_1)"),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Resolve claim provenance back to exact document offsets.

    - When `sentence_index` or `sentence_id` is supplied: returns detailed trace for that single sentence.
    - When omitted: returns full sentence-by-sentence trace for the entire deliverable.
    """
    try:
        if sentence_index is not None or sentence_id is not None:
            return await GroundingTraceService.trace_sentence(
                session=session,
                output_id=output_id,
                sentence_index=sentence_index,
                sentence_id=sentence_id,
            )
        return await GroundingTraceService.trace_full_deliverable(
            session=session,
            output_id=output_id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        logger.error("Trace failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provenance trace failed: {exc}",
        ) from exc


@router.get(
    "/trace/{output_id}/full",
    response_model=FullDeliverableTraceResponse,
    summary="Complete deliverable sentence-by-sentence trace and verification report",
)
async def trace_full_deliverable(
    output_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> FullDeliverableTraceResponse:
    """Trace and verify every single sentence across all blocks of a deliverable."""
    try:
        return await GroundingTraceService.trace_full_deliverable(
            session=session,
            output_id=output_id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        logger.error("Full trace failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full provenance trace failed: {exc}",
        ) from exc


@router.post(
    "/outputs",
    response_model=DeliverableResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and persist grounded deliverable (enforces hard claim-citation contract)",
)
async def create_deliverable(
    request: CreateDeliverableRequest,
    actor: str = Query(default="operator_default", description="Identifier of operator/adapter"),
    session: AsyncSession = Depends(get_db),
) -> DeliverableResponse:
    """Validate deliverable against the hard claim-citation contract and persist if valid.

    Rejects any deliverable where even a single sentence lacks a verified citation
    referencing authentic source chunks and matching offsets.
    """
    try:
        deliverable = await GroundingOutputService.create_grounded_deliverable(
            session=session,
            request=request,
            actor=actor,
        )
        return deliverable
    except GroundingContractError as contract_err:
        logger.warning("Grounding contract rejection: %s", contract_err.message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": contract_err.__class__.__name__,
                "message": contract_err.message,
                "details": contract_err.details,
            },
        ) from contract_err
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        logger.error("Create deliverable failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create grounded deliverable: {exc}",
        ) from exc


@router.get(
    "/outputs/{output_id}",
    response_model=DeliverableResponse,
    summary="Get single deliverable by output ID",
)
async def get_deliverable(
    output_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DeliverableResponse:
    """Retrieve deliverable metadata, structured content, and citations."""
    try:
        return await GroundingOutputService.get_deliverable(session=session, output_id=output_id)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve deliverable: {exc}",
        ) from exc


@router.get(
    "/outputs/document/{doc_id}",
    response_model=list[DeliverableResponse],
    summary="List all deliverables generated for a document",
)
async def get_deliverables_by_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DeliverableResponse]:
    """Retrieve all deliverables associated with a given source document."""
    return await GroundingOutputService.get_deliverables_by_doc(session=session, doc_id=doc_id)
