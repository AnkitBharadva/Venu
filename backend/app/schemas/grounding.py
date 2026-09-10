"""Pydantic schemas for Phase 3: Grounding & Retrieval Service.

Includes:
- /retrieve request & response schemas (hybrid Qdrant vector + FalkorDB graph)
- /trace request & response schemas (claim-to-chunk provenance)
- Grounded sentence & citation models enforcing hard claim-citation contracts
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GroundedCitation(BaseModel):
    """Citation linking an emitted sentence to a specific source chunk and offset span."""

    chunk_id: uuid.UUID = Field(..., description="Referenced source DocumentChunk UUID")
    char_offset_start: int = Field(..., description="Character start index within the document raw_text")
    char_offset_end: int = Field(..., description="Character end index within the document raw_text")
    quote: str = Field(..., description="Verbatim quote or excerpt extracted from the source chunk")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Citation grounding confidence")


class GroundedSentence(BaseModel):
    """A claim or sentence within a deliverable, bound to one or more chunk citations."""

    sentence_id: str = Field(..., description="Unique sentence identifier (e.g. sent_0_1)")
    sentence_index: int = Field(..., description="Zero-based sequence index in deliverable")
    text: str = Field(..., description="The actual generated sentence/claim")
    citations: list[GroundedCitation] = Field(
        ...,
        min_length=1,
        description="Mandatory list of chunk citations (hard contract: cannot emit claim without citation)",
    )


class GroundedBlock(BaseModel):
    """A logical block or paragraph containing grounded sentences."""

    block_index: int = Field(..., description="Block index")
    title: str | None = Field(default=None, description="Optional block subtitle or section name")
    sentences: list[GroundedSentence] = Field(..., description="List of grounded sentences in this block")


class GroundedDeliverableContent(BaseModel):
    """Structured content payload for a generated deliverable."""

    title: str = Field(..., description="Title of deliverable")
    summary: str | None = Field(default=None, description="High-level overview")
    blocks: list[GroundedBlock] = Field(..., description="List of content blocks")


class CreateDeliverableRequest(BaseModel):
    """Request to create and register a grounded output deliverable."""

    doc_id: uuid.UUID = Field(..., description="Source document ID")
    deliverable_type: str = Field(
        ...,
        description="Deliverable format: executive_summary, advisory, linkedin_post, twitter_thread, etc.",
    )
    content: GroundedDeliverableContent = Field(..., description="Structured deliverable content")
    format_metadata: dict[str, Any] = Field(default_factory=dict, description="Style, target persona, layout metadata")
    reviewer_id: str | None = Field(default=None, description="Optional operator reviewer identifier")


class RetrievedChunkItem(BaseModel):
    """A retrieved semantic chunk enriched with vector score, graph score, and entity metadata."""

    chunk_id: uuid.UUID
    chunk_index: int
    text: str
    score: float = Field(..., description="Composite hybrid relevance score")
    vector_score: float = Field(..., description="Cosine similarity score from Qdrant")
    graph_score: float = Field(..., description="Knowledge graph connectivity score from FalkorDB")
    char_offset_start: int
    char_offset_end: int
    heading: str | None = None
    page_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    entities_present: list[str] = Field(default_factory=list, description="Entities found in this chunk")


class RetrievedGraphContext(BaseModel):
    """Knowledge graph context extracted from FalkorDB during hybrid retrieval."""

    matched_entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    active_topics: list[str] = Field(default_factory=list)


class GroundedContextResponse(BaseModel):
    """Response returned by /retrieve endpoint for output-generation adapters."""

    query: str
    doc_id: uuid.UUID
    total_chunks: int
    retrieved_chunks: list[RetrievedChunkItem]
    graph_context: RetrievedGraphContext
    merged_context_text: str = Field(
        ...,
        description="Aggregated, formatted context spans with chunk headers ready for LLM adapter ingestion",
    )


class GroundingSourceSpan(BaseModel):
    """Detailed ground-truth source slice returned by /trace endpoint."""

    chunk_id: uuid.UUID
    chunk_index: int
    heading: str | None = None
    page_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    char_offset_start: int
    char_offset_end: int
    quote: str
    chunk_text: str
    context_before: str = Field(default="", description="Text immediately preceding the quote in raw_text")
    context_after: str = Field(default="", description="Text immediately following the quote in raw_text")
    trace_verified: bool = Field(
        default=True,
        description="True if raw_text[char_offset_start:char_offset_end] exactly matches source slice",
    )


class SentenceTraceResponse(BaseModel):
    """Response returned by /trace for a single sentence."""

    output_id: uuid.UUID
    doc_id: uuid.UUID
    deliverable_type: str
    sentence_id: str
    sentence_index: int
    sentence_text: str
    grounding_sources: list[GroundingSourceSpan]
    all_spans_verified: bool = Field(default=True, description="True if all citations resolve to valid source spans")


class FullDeliverableTraceResponse(BaseModel):
    """Response returned by /trace when inspecting an entire deliverable."""

    output_id: uuid.UUID
    doc_id: uuid.UUID
    deliverable_type: str
    title: str
    total_sentences: int
    total_citations: int
    coverage_pct: float = Field(default=100.0, description="Percentage of sentences backed by citations (must be 100%)")
    traces: list[SentenceTraceResponse]
    all_verified: bool = Field(default=True)


class DeliverableResponse(BaseModel):
    """Public representation of a generated deliverable."""

    model_config = ConfigDict(from_attributes=True)

    output_id: uuid.UUID
    doc_id: uuid.UUID
    deliverable_type: str
    status: str
    content: dict[str, Any]
    citations: list[dict[str, Any]]
    format_metadata: dict[str, Any]
    encrypted_file_path: str | None = None
    reviewer_id: str | None = None
    reviewer_notes: str | None = None
    approved_at: datetime | None = None
    total_sentences: int = 0
    total_citations: int = 0
    contract_verified: bool = True
