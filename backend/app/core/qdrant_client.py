"""Qdrant client provider and vector store health check."""

import logging
import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import get_settings

logger = logging.getLogger("app.core.qdrant_client")
settings = get_settings()


def get_qdrant_client() -> QdrantClient:
    """Instantiate and return an air-gapped Qdrant client."""
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        grpc_port=settings.QDRANT_GRPC_PORT,
        prefer_grpc=False,
        api_key=settings.QDRANT_API_KEY,
        timeout=3,
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
