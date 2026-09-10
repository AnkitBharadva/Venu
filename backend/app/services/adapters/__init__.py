"""Output Generation Adapters package for Phase 4.

Provides modular adapters for deliverable transformation (LinkedIn, Twitter/X,
Executive Summary, Tactical Advisory, Presentation Deck, Video Package, Infographic),
dynamic config-driven extensibility, citation linking, and multi-select orchestration.
"""

from app.services.adapters.advisory_adapter import AdvisoryAdapter
from app.services.adapters.base import AdapterOutput, BaseDeliverableAdapter
from app.services.adapters.citation_linker import CitationLinker
from app.services.adapters.dynamic_adapter import ConfigDrivenAdapter
from app.services.adapters.executive_summary_adapter import ExecutiveSummaryAdapter
from app.services.adapters.infographic_adapter import InfographicAdapter
from app.services.adapters.linkedin_adapter import LinkedInPostAdapter
from app.services.adapters.orchestrator import AdapterOrchestrationService
from app.services.adapters.presentation_adapter import PresentationAdapter
from app.services.adapters.registry import AdapterRegistry, get_adapter_registry
from app.services.adapters.twitter_adapter import TwitterThreadAdapter
from app.services.adapters.video_package_adapter import VideoPackageAdapter

__all__ = [
    "BaseDeliverableAdapter",
    "AdapterOutput",
    "CitationLinker",
    "ConfigDrivenAdapter",
    "AdapterRegistry",
    "get_adapter_registry",
    "LinkedInPostAdapter",
    "TwitterThreadAdapter",
    "ExecutiveSummaryAdapter",
    "AdvisoryAdapter",
    "PresentationAdapter",
    "VideoPackageAdapter",
    "InfographicAdapter",
    "AdapterOrchestrationService",
]
