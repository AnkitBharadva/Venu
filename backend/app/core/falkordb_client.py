"""FalkorDB / Graph database client provider and health check."""

import logging
import socket
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger("app.core.falkordb_client")
settings = get_settings()


def is_falkordb_live(timeout: float = 0.2) -> bool:
    """Fast non-blocking probe to verify if FalkorDB socket is actively listening."""
    for host in (settings.FALKORDB_HOST, "127.0.0.1"):
        try:
            with socket.create_connection((host, settings.FALKORDB_PORT), timeout=timeout):
                return True
        except (TimeoutError, socket.gaierror, ConnectionRefusedError, OSError):
            continue
    return False


def get_redis_client() -> aioredis.Redis:
    """Return an async redis connection for FalkorDB."""
    target_host = settings.FALKORDB_HOST
    if target_host in ("localhost", "127.0.0.1"):
        target_host = "127.0.0.1"
    else:
        try:
            with socket.create_connection((settings.FALKORDB_HOST, settings.FALKORDB_PORT), timeout=0.1):
                target_host = settings.FALKORDB_HOST
        except Exception:
            target_host = "127.0.0.1"

    return aioredis.Redis(
        host=target_host,
        port=settings.FALKORDB_PORT,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
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
