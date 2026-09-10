"""Deliverable Adapter Registry for Phase 4.

Maintains the catalog of generation adapters, supports dynamic registration via
configuration, and provides adapter discovery for operators.
"""

import logging

from app.schemas.adapters import AdapterMetadataResponse, DynamicAdapterConfig
from app.services.adapters.advisory_adapter import AdvisoryAdapter
from app.services.adapters.base import BaseDeliverableAdapter
from app.services.adapters.dynamic_adapter import ConfigDrivenAdapter
from app.services.adapters.executive_summary_adapter import ExecutiveSummaryAdapter
from app.services.adapters.infographic_adapter import InfographicAdapter
from app.services.adapters.linkedin_adapter import LinkedInPostAdapter
from app.services.adapters.presentation_adapter import PresentationAdapter
from app.services.adapters.twitter_adapter import TwitterThreadAdapter
from app.services.adapters.video_package_adapter import VideoPackageAdapter

logger = logging.getLogger("app.services.adapters.registry")


class AdapterRegistry:
    """Central registry and factory for all output deliverable generation adapters."""

    _instance: "AdapterRegistry | None" = None

    def __init__(self) -> None:
        self._adapters: dict[str, BaseDeliverableAdapter] = {}
        self._register_builtins()

    @classmethod
    def get_instance(cls) -> "AdapterRegistry":
        """Get or initialize singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_builtins(self) -> None:
        """Register the 7 core built-in adapters."""
        builtins = [
            LinkedInPostAdapter(),
            TwitterThreadAdapter(),
            ExecutiveSummaryAdapter(),
            AdvisoryAdapter(),
            PresentationAdapter(),
            VideoPackageAdapter(),
            InfographicAdapter(),
        ]
        for adapter in builtins:
            self.register(adapter)
        logger.info("Registered %d built-in generation adapters: %s", len(builtins), list(self._adapters.keys()))

    def register(self, adapter: BaseDeliverableAdapter) -> None:
        """Register a custom adapter instance."""
        self._adapters[adapter.deliverable_type] = adapter
        logger.debug("Registered adapter: %s (%s)", adapter.name, adapter.deliverable_type)

    def register_from_config(self, config: DynamicAdapterConfig) -> BaseDeliverableAdapter:
        """Register a new deliverable format dynamically from configuration (zero new code)."""
        adapter = ConfigDrivenAdapter(config)
        self.register(adapter)
        logger.info("Dynamically registered config-driven adapter: %s (%s)", adapter.name, adapter.deliverable_type)
        return adapter

    def get_adapter(self, deliverable_type: str) -> BaseDeliverableAdapter:
        """Retrieve adapter by deliverable type key."""
        adapter = self._adapters.get(deliverable_type)
        if not adapter:
            available = list(self._adapters.keys())
            raise KeyError(
                f"Unknown deliverable type '{deliverable_type}'. Available adapters: {available}"
            )
        return adapter

    def list_adapters(self) -> list[AdapterMetadataResponse]:
        """List metadata for all currently registered adapters."""
        results: list[AdapterMetadataResponse] = []
        for a in self._adapters.values():
            results.append(
                AdapterMetadataResponse(
                    deliverable_type=a.deliverable_type,
                    name=a.name,
                    description=a.description,
                    category=a.category,
                    requires_human_review=a.requires_human_review,
                    supported_tones=["objective", "authoritative", "technical", "engaging"],
                    output_schema_preview={"type": "GroundedDeliverableContent", "requires_citations": True},
                )
            )
        return results


def get_adapter_registry() -> AdapterRegistry:
    """Dependency helper to get global adapter registry."""
    return AdapterRegistry.get_instance()
