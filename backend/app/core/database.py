"""Database session management and PostgreSQL health check."""

import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

logger = logging.getLogger("app.core.database")
settings = get_settings()

db_url = settings.async_database_url
engine_kwargs: dict[str, Any] = {"echo": settings.DEBUG}
if not db_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 5,
        "pool_pre_ping": True,
    })

engine = create_async_engine(
    db_url,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_postgres_health(timeout_seconds: float = 3.0) -> dict[str, Any]:
    """Verify PostgreSQL connectivity and query execution latency."""
    start_time = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1 AS alive;"))
            row = result.scalar_one_or_none()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if row == 1:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "database": settings.POSTGRES_DB,
                    "error": None,
                }
            return {
                "status": "degraded",
                "latency_ms": latency_ms,
                "database": settings.POSTGRES_DB,
                "error": f"Unexpected scalar query response: {row}",
            }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("Postgres health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "database": settings.POSTGRES_DB,
            "error": str(exc),
        }
