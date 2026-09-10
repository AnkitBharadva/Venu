"""Shared pytest configuration and fixtures for backend test suites."""

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all models to ensure metadata includes chunks and understanding
import app.models.understanding  # noqa: F401
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.audit_log import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def prepare_database(tmp_path):
    """Set up fresh database tables and isolated encrypted uploads directory for each test."""
    test_upload_dir = tmp_path / "encrypted_uploads"
    test_upload_dir.mkdir(parents=True, exist_ok=True)
    test_output_dir = tmp_path / "encrypted_outputs"
    test_output_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch.object(get_settings(), "UPLOAD_STORAGE_PATH", str(test_upload_dir)),
        patch.object(get_settings(), "OUTPUT_STORAGE_PATH", str(test_output_dir)),
    ):
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
