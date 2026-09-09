"""Unit and integration tests for backend health check endpoints."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify root metadata returns service details."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "endpoints" in data
    assert data["airgap_mode"] is True


@pytest.mark.asyncio
async def test_liveness_probe():
    """Verify liveness probe returns HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_aggregate_health_all_healthy():
    """Verify /health returns 200 and healthy status when all dependencies are healthy."""
    mock_pg = {"status": "healthy", "latency_ms": 1.5, "database": "genai_platform", "error": None}
    mock_qd = {"status": "healthy", "latency_ms": 2.1, "host": "qdrant:6333", "collections_count": 0, "error": None}
    mock_fk = {"status": "healthy", "latency_ms": 0.9, "host": "falkordb:6379", "server_info": {}, "error": None}

    with (
        patch("app.api.health.check_postgres_health", return_value=mock_pg),
        patch("app.api.health.check_qdrant_health", return_value=mock_qd),
        patch("app.api.health.check_falkordb_health", return_value=mock_fk),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["dependencies"]["postgres"]["status"] == "healthy"
    assert data["dependencies"]["qdrant"]["status"] == "healthy"
    assert data["dependencies"]["falkordb"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_aggregate_health_degraded():
    """Verify /health returns degraded when a dependency is unreachable in dev mode."""
    mock_pg = {"status": "healthy", "latency_ms": 1.5, "database": "genai_platform", "error": None}
    mock_qd = {"status": "unhealthy", "latency_ms": 20.0, "host": "qdrant:6333", "error": "Connection refused"}
    mock_fk = {"status": "healthy", "latency_ms": 0.9, "host": "falkordb:6379", "server_info": {}, "error": None}

    with (
        patch("app.api.health.check_postgres_health", return_value=mock_pg),
        patch("app.api.health.check_qdrant_health", return_value=mock_qd),
        patch("app.api.health.check_falkordb_health", return_value=mock_fk),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["qdrant"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_airgap_endpoint():
    """Verify /health/airgap probe executes without error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/airgap")
    assert response.status_code == 200
    data = response.json()
    assert "airgap_verified" in data
    assert "target_tested" in data


def test_settings_load():
    """Verify settings defaults and types."""
    settings = get_settings()
    assert settings.PROJECT_NAME != ""
    assert settings.POSTGRES_PORT == 5432
    assert settings.QDRANT_PORT == 6333
    assert settings.FALKORDB_PORT == 6379
    assert isinstance(settings.ALLOWED_ORIGINS, list)
