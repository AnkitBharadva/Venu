"""SIH26155 GenAI Content Transformation Platform - Main FastAPI Application.

Operates in an offline, air-gapped environment with zero external telemetry or egress.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.adapters import router as adapters_router
from app.api.audit import router as audit_router
from app.api.grounding import router as grounding_router
from app.api.health import router as health_router
from app.api.ingestion import router as ingestion_router
from app.api.review import router as review_router
from app.api.understanding import router as understanding_router
from app.core.config import get_settings

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("app.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events for air-gapped operations."""
    logger.info("================================================================")
    logger.info("Initializing %s (Env: %s)", settings.PROJECT_NAME, settings.ENVIRONMENT)
    logger.info("AIRGAP STRICT MODE: %s", settings.AIRGAP_STRICT_MODE)
    logger.info("Target DB: %s:%s / %s", settings.POSTGRES_SERVER, settings.POSTGRES_PORT, settings.POSTGRES_DB)
    logger.info("Target Qdrant: %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT)
    logger.info("Target FalkorDB: %s:%s", settings.FALKORDB_HOST, settings.FALKORDB_PORT)
    logger.info("================================================================")
    yield
    logger.info("Shutting down %s cleanly.", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Air-gapped AI content transformation platform with tamper-evident audit logging and chunk grounding.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Health & Monitoring Endpoints
app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(audit_router)
app.include_router(understanding_router)
app.include_router(grounding_router)
app.include_router(adapters_router)
app.include_router(review_router)


@app.get("/")
async def root():
    """Root metadata endpoint."""
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "airgap_mode": settings.AIRGAP_STRICT_MODE,
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "liveness": "/health/live",
            "readiness": "/health/ready",
            "airgap_check": "/health/airgap",
            "docs": "/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else "disabled",
        },
    }
