"""Qdrant client provider and vector store health check."""

import logging
import socket
import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import get_settings

logger = logging.getLogger("app.core.qdrant_client")
settings = get_settings()


def is_qdrant_live(timeout: float = 0.2) -> bool:
    """Fast non-blocking probe to verify if Qdrant socket is actively listening."""
    for host in (settings.QDRANT_HOST, "127.0.0.1"):
        try:
            with socket.create_connection((host, settings.QDRANT_PORT), timeout=timeout):
                return True
        except (TimeoutError, socket.gaierror, ConnectionRefusedError, OSError):
            continue
    return False


def get_qdrant_client() -> QdrantClient:
    """Instantiate and return an air-gapped Qdrant client."""
    # Determine accessible host
    target_host = settings.QDRANT_HOST
    if target_host in ("localhost", "127.0.0.1"):
        target_host = "127.0.0.1"
    else:
        try:
            with socket.create_connection((settings.QDRANT_HOST, settings.QDRANT_PORT), timeout=0.1):
                target_host = settings.QDRANT_HOST
        except Exception:
            target_host = "127.0.0.1"

    return QdrantClient(
        host=target_host,
        port=settings.QDRANT_PORT,
        grpc_port=settings.QDRANT_GRPC_PORT,
        prefer_grpc=False,
        https=False,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=1.0,
        check_compatibility=False,
    )


async def check_qdrant_health(timeout_seconds: float = 3.0) -> dict[str, Any]:
    """Check Qdrant connectivity and collection readiness."""
    start_time = time.perf_counter()
    try:
        client = get_qdrant_client()
        # Ping readiness/cluster status via collections list
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "host": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
            "collections_count": len(collection_names),
            "collections": collection_names,
            "error": None,
        }
    except UnexpectedResponse as ur:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("Qdrant responded with error: %s", ur)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "host": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
            "error": f"HTTP {ur.status_code}: {ur.content.decode('utf-8', errors='ignore')}",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("Qdrant health check connection failed: %s", exc)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "host": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
            "error": str(exc),
        }
