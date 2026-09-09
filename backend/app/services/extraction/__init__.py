"""Entity and intent extraction package for Phase 2."""

from app.services.extraction.entity_extractor import (
    EntityExtractor,
    ExtractionResult,
    get_entity_extractor,
)

__all__ = ["EntityExtractor", "ExtractionResult", "get_entity_extractor"]
