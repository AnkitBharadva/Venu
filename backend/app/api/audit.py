"""Audit Log API Router.

Exposes:
- GET /api/v1/audit/logs
- GET /api/v1/audit/verify-chain
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import verify_audit_integrity
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse, AuditVerificationResponse

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Log"])


@router.get(
    "/logs",
    response_model=list[AuditLogResponse],
    summary="List audit log entries with tamper-evident hash chaining",
)
async def list_audit_logs(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    """Retrieve immutable audit log records ordered chronologically."""
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    entries = result.scalars().all()
    return [AuditLogResponse.model_validate(e) for e in entries]


@router.get(
    "/verify-chain",
    response_model=AuditVerificationResponse,
    summary="Cryptographically verify the entire audit log hash chain",
)
async def verify_chain(
    session: AsyncSession = Depends(get_db),
) -> AuditVerificationResponse:
    """Verifies that no record in the audit_log table has been modified, deleted,

    or inserted out-of-order by re-computing the SHA-256 hash sequence.
    """
    res = await verify_audit_integrity(session)
    return AuditVerificationResponse(
        valid=res["valid"],
        total_records=res["total_records"],
        latest_hash=res.get("latest_hash"),
        status=res.get("status", "Unknown"),
        error=res.get("error"),
        record_id=res.get("record_id"),
    )
