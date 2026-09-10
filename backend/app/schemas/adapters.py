"""Pydantic schemas for Phase 4: Output Generation Adapters.

Defines:
- Generation parameters (audience, tone, language, detail_level, objective, style)
- Multi-select generation request and response models
- Dynamic adapter configuration for config-driven extensibility
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.grounding import DeliverableResponse


class GenerationParameters(BaseModel):
    """Configurable parameters passed to output generation adapters."""

    model_config = ConfigDict(extra="ignore")

    audience: str = Field(default="general_professional", description="Target audience (e.g. executive, technical, public)")
    tone: str = Field(default="objective", description="Tone of voice (e.g. authoritative, formal, engaging, urgent)")
    language: str = Field(default="en", description="Target output language ISO code")
    detail_level: str = Field(default="standard", description="Depth of coverage: brief, standard, or comprehensive")
    objective: str | None = Field(default=None, description="Optional specific focus or transformation goal")
    style: str | None = Field(default=None, description="Optional style guide or format modifier")
    custom_instructions: str | None = Field(default=None, description="Operator-supplied prompt constraints")


class GenerateDeliverablesRequest(BaseModel):
    """Request to generate one or multiple deliverables from a source document."""

    doc_id: uuid.UUID = Field(..., description="Target source document UUID")
    deliverable_types: list[str] = Field(
        ...,
        min_length=1,
        description="List of adapter types to run (e.g. ['linkedin_post', 'executive_summary', 'advisory'])",
    )
    query: str | None = Field(
        default=None,
        description="Optional guiding query or topic for hybrid retrieval. Defaults to document title/topics.",
    )
    parameters: GenerationParameters = Field(
        default_factory=GenerationParameters,
        description="Audience, tone, detail level, and style parameters",
    )
    top_k_chunks: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Number of top grounded chunks to feed adapters",
    )
    actor: str = Field(
        default="operator_default",
        description="Identifier of operator triggering generation",
    )


class AdapterMetadataResponse(BaseModel):
    """Description of an available generation adapter."""

    deliverable_type: str
    name: str
    description: str
    category: str
    requires_human_review: bool = False
    supported_tones: list[str] = Field(default_factory=list)
    output_schema_preview: dict[str, Any] = Field(default_factory=dict)


class DynamicAdapterConfig(BaseModel):
    """Configuration payload to register a new deliverable format without writing new code."""

    deliverable_type: str = Field(..., pattern="^[a-z0-9_]+$", description="Unique lowercase identifier")
    name: str = Field(..., description="Human-readable deliverable name")
    description: str = Field(..., description="Description of format and use case")
    category: str = Field(default="general", description="Category: social, executive, operational, visual")
    system_prompt_template: str = Field(..., description="Prompt instructions for generating this format")
    block_structure: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Template of blocks/sections (e.g. [{'index': 0, 'title': 'Overview'}])",
    )
    requires_human_review: bool = Field(default=False, description="Whether human review is mandatory before export")
    format_metadata_defaults: dict[str, Any] = Field(default_factory=dict)


class MultiDeliverableResponse(BaseModel):
    """Response returned when generating one or multiple deliverables."""

    doc_id: uuid.UUID
    query_used: str
    retrieved_chunks_count: int
    total_deliverables: int
    deliverables: list[DeliverableResponse]
    all_citations_verified: bool = True
