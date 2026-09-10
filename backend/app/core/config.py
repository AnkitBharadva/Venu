"""Application configuration using Pydantic Settings.

Reads environment variables and enforces air-gapped / offline constraints.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application
    PROJECT_NAME: str = "GenAI Content Transformation Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "default-development-secret-key-replace-in-prod-32-bytes"
    ALLOWED_ORIGINS: str | list[str] = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:80"
    LOG_LEVEL: str = "INFO"

    # Air-Gap & Security Constraints
    AIRGAP_STRICT_MODE: bool = True
    STORAGE_ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    UPLOAD_STORAGE_PATH: str = "/data/encrypted_uploads"
    OUTPUT_STORAGE_PATH: str = "/data/encrypted_outputs"

    # PostgreSQL
    POSTGRES_SERVER: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "genai_platform"
    POSTGRES_USER: str = "genai_user"
    POSTGRES_PASSWORD: str = "genai_secure_pass"
    DATABASE_URL: str | None = None

    # Qdrant
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_COLLECTION_DEFAULT: str = "source_chunks"
    QDRANT_API_KEY: str | None = None

    # FalkorDB
    FALKORDB_HOST: str = "falkordb"
    FALKORDB_PORT: int = 6379
    FALKORDB_GRAPH_DEFAULT: str = "genai_knowledge_graph"

    # AI Models
    MODELS_DIR: str = "/models"
    REASONING_MODEL_NAME: str = "Qwen3-8B"
    VISION_MODEL_NAME: str = "Qwen3-VL-4B"
    ASR_MODEL_NAME: str = "Whisper-medium.en"
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384

    # Frontend / Network
    FRONTEND_PORT: int = 3000
    BACKEND_PORT: int = 8000
    REACT_APP_API_BASE_URL: str = "http://localhost:8000"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            # ensure asyncpg scheme
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
