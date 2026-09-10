"""Grounding & Provenance Service package.

Provides hybrid retrieval (Qdrant + FalkorDB), sentence-level source tracing,
and hard claim-citation contract enforcement for all output formats.
"""

from app.services.grounding.contract_enforcer import (
    GroundingContractEnforcer,
    GroundingContractError,
    GroundingQuoteMismatchError,
    InvalidCitationChunkError,
    UncitedClaimViolationError,
)
from app.services.grounding.output_service import GroundingOutputService
from app.services.grounding.retrieval_service import GroundingRetrievalService
from app.services.grounding.trace_service import GroundingTraceService

__all__ = [
    "GroundingContractEnforcer",
    "GroundingContractError",
    "GroundingQuoteMismatchError",
    "InvalidCitationChunkError",
    "UncitedClaimViolationError",
    "GroundingOutputService",
    "GroundingRetrievalService",
    "GroundingTraceService",
]
