"""Generation Adapters API Router for Phase 4.

Exposes:
- POST /api/v1/generate: Multi-select deliverable generation against shared grounded context
- GET  /api/v1/generate/adapters: List all available generation adapters and metadata
- POST /api/v1/generate/adapters/register: Dynamically register a new deliverable format from config
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rbac import Permission, UserContext, require_permission
from app.schemas.adapters import (
    AdapterMetadataResponse,
    DynamicAdapterConfig,
    GenerateDeliverablesRequest,
    MultiDeliverableResponse,
)
from app.schemas.review import ExportDeliverableRequest, ExportDeliverableResponse
from app.services.adapters.orchestrator import AdapterOrchestrationService
from app.services.adapters.registry import get_adapter_registry
from app.services.grounding.contract_enforcer import GroundingContractError
from app.services.review_service import HumanReviewRequiredError, ReviewService

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


adapters_alias_router = APIRouter(prefix="/api/v1/adapters", tags=["Adapters Alias"])


async def _handle_adapter_export(
    output_id: uuid.UUID,
    format: str | None,
    body: ExportDeliverableRequest | None,
    session: AsyncSession,
    user: UserContext,
) -> ExportDeliverableResponse:
    target_format = (body.export_format if body and body.export_format else format) or "markdown"
    try:
        return await ReviewService.export_deliverable(
            session=session,
            output_id=output_id,
            actor=user.user_id,
            export_format=target_format,
        )
    except HumanReviewRequiredError as hr_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "HumanReviewRequired",
                "message": str(hr_err),
                "output_id": str(output_id),
            },
        ) from hr_err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@adapters_alias_router.post(
    "/export/{output_id}",
    response_model=ExportDeliverableResponse,
    summary="Export deliverable (adapters alias)",
)
async def export_via_adapters_alias(
    output_id: uuid.UUID,
    format: str = Query(default="markdown"),
    body: ExportDeliverableRequest = ExportDeliverableRequest(),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.EXPORT)),
) -> ExportDeliverableResponse:
    return await _handle_adapter_export(output_id, format, body, session, user)


@router.post(
    "/export/{output_id}",
    response_model=ExportDeliverableResponse,
    summary="Export deliverable (generate alias)",
)
async def export_via_generate_alias(
    output_id: uuid.UUID,
    format: str = Query(default="markdown"),
    body: ExportDeliverableRequest = ExportDeliverableRequest(),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.EXPORT)),
) -> ExportDeliverableResponse:
    return await _handle_adapter_export(output_id, format, body, session, user)

