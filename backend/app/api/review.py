"""Review, Approval, and Export API Router for Phase 5.

Exposes:
- GET  /api/v1/review/pending: List deliverables awaiting review
- GET  /api/v1/review/outputs/{output_id}: Retrieve deliverable details
- POST /api/v1/review/outputs/{output_id}/request-approval: Operator submits for review
- POST /api/v1/review/outputs/{output_id}/approve: Reviewer approves deliverable (RBAC protected)
- POST /api/v1/review/outputs/{output_id}/reject: Reviewer rejects deliverable (RBAC protected)
- POST /api/v1/review/outputs/{output_id}/export: Export approved deliverable (RBAC & review gatekeeper)
- GET  /api/v1/review/outputs/{output_id}/verify-encryption: Verify AES-256-GCM encryption at rest
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rbac import Permission, UserContext, require_permission
from app.schemas.grounding import DeliverableResponse
from app.schemas.review import (
    ApprovalActionRequest,
    ExportDeliverableRequest,
    ExportDeliverableResponse,
    OutputEncryptionVerificationResponse,
    RequestApprovalRequest,
)
from app.services.grounding.output_service import GroundingOutputService
from app.services.review_service import HumanReviewRequiredError, ReviewService

logger = logging.getLogger("app.api.review")

router = APIRouter(prefix="/api/v1/review", tags=["Review & Approval Layer"])


@router.get(
    "/pending",
    response_model=list[DeliverableResponse],
    summary="List deliverables pending review or in draft status",
)
async def list_pending_reviews(
    doc_id: uuid.UUID | None = Query(default=None, description="Optional document filter"),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.VIEW)),
) -> list[DeliverableResponse]:
    """Retrieve all generated deliverables available for review or inspection."""
    return await ReviewService.list_pending_reviews(session=session, doc_id=doc_id)


@router.get(
    "/outputs/{output_id}",
    response_model=DeliverableResponse,
    summary="Retrieve deliverable by output ID with provenance and review status",
)
async def get_deliverable_by_id(
    output_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.VIEW)),
) -> DeliverableResponse:
    """Fetch deliverable details, review status, reviewer notes, and citations."""
    try:
        return await GroundingOutputService.get_deliverable(session=session, output_id=output_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post(
    "/outputs/{output_id}/request-approval",
    response_model=DeliverableResponse,
    summary="Operator submits deliverable for formal human reviewer evaluation",
)
async def request_approval(
    output_id: uuid.UUID,
    body: RequestApprovalRequest = RequestApprovalRequest(),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.REQUEST_APPROVAL)),
) -> DeliverableResponse:
    """Submits deliverable to the reviewer queue and transitions state to 'pending_review'."""
    try:
        return await ReviewService.request_approval(
            session=session,
            output_id=output_id,
            actor=user.user_id,
            notes=body.notes,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post(
    "/outputs/{output_id}/approve",
    response_model=DeliverableResponse,
    summary="Reviewer formally approves deliverable (RBAC: Reviewer / Approver / Admin only)",
)
async def approve_deliverable(
    output_id: uuid.UUID,
    body: ApprovalActionRequest = ApprovalActionRequest(),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.APPROVE)),
) -> DeliverableResponse:
    """Approve deliverable. Strictly forbidden for operator role (returns HTTP 403 Forbidden)."""
    try:
        return await ReviewService.approve_deliverable(
            session=session,
            output_id=output_id,
            reviewer_id=user.user_id,
            reviewer_notes=body.reviewer_notes,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post(
    "/outputs/{output_id}/reject",
    response_model=DeliverableResponse,
    summary="Reviewer formally rejects deliverable with feedback (RBAC: Reviewer / Approver / Admin only)",
)
async def reject_deliverable(
    output_id: uuid.UUID,
    body: ApprovalActionRequest = ApprovalActionRequest(),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.REJECT)),
) -> DeliverableResponse:
    """Reject deliverable. Strictly forbidden for operator role (returns HTTP 403 Forbidden)."""
    try:
        return await ReviewService.reject_deliverable(
            session=session,
            output_id=output_id,
            reviewer_id=user.user_id,
            reviewer_notes=body.reviewer_notes,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post(
    "/outputs/{output_id}/export",
    response_model=ExportDeliverableResponse,
    summary="Export deliverable (RBAC: Reviewer / Approver / Admin only; human review gatekeeper enforced)",
)
async def export_deliverable(
    output_id: uuid.UUID,
    body: ExportDeliverableRequest = ExportDeliverableRequest(),
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.EXPORT)),
) -> ExportDeliverableResponse:
    """Authorize and render deliverable export.

    Enforces two critical defences:
    1. RBAC: Operator is blocked (HTTP 403 Forbidden).
    2. Review Gatekeeper: Safety-critical deliverables (Advisories) cannot be exported unless status is 'approved'.
    """
    try:
        return await ReviewService.export_deliverable(
            session=session,
            output_id=output_id,
            actor=user.user_id,
            export_format=body.export_format,
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


@router.get(
    "/outputs/{output_id}/verify-encryption",
    response_model=OutputEncryptionVerificationResponse,
    summary="Cryptographically verify output deliverable encryption at rest (AES-256-GCM)",
)
async def verify_output_encryption(
    output_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_permission(Permission.VIEW)),
) -> OutputEncryptionVerificationResponse:
    """Proves that the deliverable on disk is encrypted with AES-256-GCM and decrypts cleanly with enclave key."""
    try:
        return await ReviewService.verify_output_encryption_at_rest(
            session=session,
            output_id=output_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
