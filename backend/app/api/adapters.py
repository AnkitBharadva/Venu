"""Generation Adapters API Router for Phase 4.

Exposes:
- POST /api/v1/generate: Multi-select deliverable generation against shared grounded context
- GET  /api/v1/generate/adapters: List all available generation adapters and metadata
- POST /api/v1/generate/adapters/register: Dynamically register a new deliverable format from config
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.adapters import (
    AdapterMetadataResponse,
    DynamicAdapterConfig,
    GenerateDeliverablesRequest,
    MultiDeliverableResponse,
)
from app.services.adapters.orchestrator import AdapterOrchestrationService
from app.services.adapters.registry import get_adapter_registry
from app.services.grounding.contract_enforcer import GroundingContractError

logger = logging.getLogger("app.api.adapters")

router = APIRouter(prefix="/api/v1/generate", tags=["Output Generation Adapters"])


@router.post(
    "",
    response_model=MultiDeliverableResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate one or multiple grounded deliverables from a source document",
)
async def generate_deliverables(
    request: GenerateDeliverablesRequest,
    session: AsyncSession = Depends(get_db),
) -> MultiDeliverableResponse:
    """Execute selected generation adapters against source document's grounded context.

    Supports multi-select: runs adapters concurrently against a shared hybrid
    vector-graph context and enforces the hard claim-citation contract on each sentence.
    """
    try:
        response = await AdapterOrchestrationService.generate_deliverables(
            session=session,
            request=request,
        )
        return response
    except KeyError as key_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(key_err),
        ) from key_err
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except GroundingContractError as contract_err:
        logger.warning("Generation contract violation: %s", contract_err.message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": contract_err.__class__.__name__,
                "message": contract_err.message,
                "details": contract_err.details,
            },
        ) from contract_err
    except Exception as exc:
        logger.error("Multi-deliverable generation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {exc}",
        ) from exc


@router.get(
    "/adapters",
    response_model=list[AdapterMetadataResponse],
    summary="List all available generation adapters and schemas",
)
async def list_adapters() -> list[AdapterMetadataResponse]:
    """Retrieve catalog of registered deliverable adapters (LinkedIn, Twitter, Executive Summary, Advisory, Presentation, Video, Infographic, etc.)."""
    registry = get_adapter_registry()
    return registry.list_adapters()


@router.post(
    "/adapters/register",
    response_model=AdapterMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dynamically register a new deliverable format purely from configuration",
)
async def register_dynamic_adapter(
    config: DynamicAdapterConfig,
) -> AdapterMetadataResponse:
    """Add a new deliverable format to the system dynamically via config without writing new code."""
    registry = get_adapter_registry()
    adapter = registry.register_from_config(config)
    return AdapterMetadataResponse(
        deliverable_type=adapter.deliverable_type,
        name=adapter.name,
        description=adapter.description,
        category=adapter.category,
        requires_human_review=adapter.requires_human_review,
        supported_tones=["objective", "authoritative", "technical"],
        output_schema_preview={"type": "GroundedDeliverableContent", "config_driven": True},
    )
