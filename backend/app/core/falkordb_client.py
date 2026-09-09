"""FalkorDB / Graph database client provider and health check."""

import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger("app.core.falkordb_client")
settings = get_settings()


def get_redis_client() -> aioredis.Redis:
    """Return an async redis connection for FalkorDB."""
    return aioredis.Redis(
        host=settings.FALKORDB_HOST,
        port=settings.FALKORDB_PORT,
        socket_connect_timeout=3.0,
        socket_timeout=3.0,
        decode_responses=True,
    )


async def check_falkordb_health(timeout_seconds: float = 3.0) -> dict[str, Any]:
    """Verify FalkorDB connectivity via Redis PING protocol."""
    start_time = time.perf_counter()
    client = get_redis_client()
    try:
        pong = await client.ping()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if pong:
            # Check for GRAPH command support if available
            info = {}
            try:
                raw_info = await client.info()
                info = {
                    "redis_version": raw_info.get("redis_version"),
                    "used_memory_human": raw_info.get("used_memory_human"),
                }
            except Exception:
                pass

            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "host": f"{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}",
                "server_info": info,
                "error": None,
            }
        return {
            "status": "degraded",
            "latency_ms": latency_ms,
            "host": f"{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}",
            "error": "PING did not return True",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("FalkorDB health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "host": f"{settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}",
            "error": str(exc),
        }
    finally:
        await client.aclose()
