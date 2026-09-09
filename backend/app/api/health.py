"""Comprehensive health-check router for backend and all storage dependencies.

Checks:
- PostgreSQL (metadata & append-only audit log)
- Qdrant (vector embeddings store)
- FalkorDB (entity-relationship graph store)
- Air-gap / Zero-egress network isolation verification
"""

import asyncio
import socket
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.database import check_postgres_health
from app.core.falkordb_client import check_falkordb_health
from app.core.qdrant_client import check_qdrant_health

router = APIRouter(prefix="", tags=["Health"])
settings = get_settings()


@router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/api/v1/health", status_code=status.HTTP_200_OK)
async def get_overall_health(response: Response) -> dict[str, Any]:
    """Aggregate health check for all core platform services.

    Returns HTTP 200 when dependencies are responsive.
    If dependencies are degraded, reports status code 200 (with degraded flag)
    or 503 if strict readiness is required.
    """
    # Execute checks concurrently for minimum latency
    pg_task = asyncio.create_task(check_postgres_health())
    qdrant_task = asyncio.create_task(check_qdrant_health())
    falkordb_task = asyncio.create_task(check_falkordb_health())

    results = await asyncio.gather(
        pg_task, qdrant_task, falkordb_task, return_exceptions=True
    )
    postgres_res: Any = results[0]
    qdrant_res: Any = results[1]
    falkordb_res: Any = results[2]

    # Normalize responses in case of unhandled task exception
    def normalize_result(res: Any, service_name: str) -> dict[str, Any]:
        if isinstance(res, Exception):
            return {
                "status": "unhealthy",
                "error": str(res),
                "latency_ms": 0.0,
            }
        return res

    pg_norm = normalize_result(postgres_res, "postgres")
    qd_norm = normalize_result(qdrant_res, "qdrant")
    fk_norm = normalize_result(falkordb_res, "falkordb")

    all_healthy = (
        pg_norm.get("status") == "healthy"
        and qd_norm.get("status") == "healthy"
        and fk_norm.get("status") == "healthy"
    )

    if not all_healthy and settings.ENVIRONMENT == "production":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": settings.ENVIRONMENT,
        "airgap_strict_mode": settings.AIRGAP_STRICT_MODE,
        "dependencies": {
            "postgres": pg_norm,
            "qdrant": qd_norm,
            "falkordb": fk_norm,
        },
    }


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, Any]:
    """Fast liveness probe for container orchestrators."""
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(response: Response) -> dict[str, Any]:
    """Readiness probe indicating if service is ready to accept ingestion requests."""
    res = await get_overall_health(response)
    is_ready = res["status"] == "healthy"
    if not is_ready and settings.ENVIRONMENT == "production":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": is_ready,
        "details": res,
    }


@router.get("/health/postgres")
async def postgres_health(response: Response) -> dict[str, Any]:
    """Individual health check for PostgreSQL."""
    res = await check_postgres_health()
    if res["status"] != "healthy" and settings.ENVIRONMENT == "production":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return res


@router.get("/health/qdrant")
async def qdrant_health(response: Response) -> dict[str, Any]:
    """Individual health check for Qdrant vector store."""
    res = await check_qdrant_health()
    if res["status"] != "healthy" and settings.ENVIRONMENT == "production":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return res


@router.get("/health/falkordb")
async def falkordb_health(response: Response) -> dict[str, Any]:
    """Individual health check for FalkorDB graph store."""
    res = await check_falkordb_health()
    if res["status"] != "healthy" and settings.ENVIRONMENT == "production":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return res


@router.get("/health/airgap", status_code=status.HTTP_200_OK)
async def verify_airgap_isolation() -> dict[str, Any]:
    """Verifies that the container / process has ZERO outbound network egress.

    Attempts a non-blocking TCP socket connection to a public internet address (e.g. 1.1.1.1:53).
    In an air-gapped / isolated container, this MUST fail or be blocked.
    """
    test_target_ip = "1.1.1.1"
    test_target_port = 53
    egress_blocked = False
    details = ""

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect((test_target_ip, test_target_port))
        egress_blocked = False
        details = "WARNING: Outbound connection succeeded. Network is NOT air-gapped."
    except (TimeoutError, OSError) as err:
        egress_blocked = True
        details = f"Outbound connection blocked as expected: {err}"
    finally:
        sock.close()

    return {
        "airgap_verified": egress_blocked,
        "details": details,
        "target_tested": f"{test_target_ip}:{test_target_port}",
        "timestamp": datetime.now(UTC).isoformat(),
    }
