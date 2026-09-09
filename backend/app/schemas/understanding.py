"""Pydantic schemas for Phase 2: Understanding, Chunking, Embeddings, and Graph."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkResponse(BaseModel):
    """Normalized chunk model preserving structural layout and grounding offsets."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID = Field(..., description="Unique chunk UUID")
    doc_id: uuid.UUID = Field(..., description="Source document identifier")
    chunk_index: int = Field(..., description="Zero-based sequence index in document")
    text: str = Field(..., description="Exact chunk text span")
    char_offset_start: int = Field(..., description="Exact character start index in raw_text")
    char_offset_end: int = Field(..., description="Exact character end index in raw_text")
    page_number: int | None = Field(default=None, description="PDF/PPTX page or slide number")
    heading: str | None = Field(default=None, description="Nearest section heading hierarchy")
    timestamp_start: float | None = Field(default=None, description="Audio/Video start timestamp in seconds")
    timestamp_end: float | None = Field(default=None, description="Audio/Video end timestamp in seconds")
    metadata_payload: dict[str, Any] = Field(default_factory=dict, description="Additional parser metadata")
    offset_verified: bool = Field(default=True, description="True if raw_text[start:end] strictly matches text")


class EntityMention(BaseModel):
    """Named entity mention with classification and chunk occurrences."""

    name: str = Field(..., description="Canonical entity name")
    type: str = Field(
        ...,
        description="Entity type: ORGANIZATION, PERSON, LOCATION, TACTIC_TECHNIQUE, WEAPON_SYSTEM, DEFENSE_PROGRAM, DATE_TIME",
    )
    count: int = Field(default=1, description="Number of mentions in document")
    chunk_ids: list[uuid.UUID] = Field(default_factory=list, description="IDs of chunks containing this entity")


class SensitiveTerm(BaseModel):
    """Advisory and defense-critical sensitive terms surfaced for human review."""

    term: str = Field(..., description="Detected sensitive term or code")
    category: str = Field(
        ...,
        description="Category: CLASSIFICATION, CYBER_VULNERABILITY, CBRN, EXPORT_CONTROL, OPERATIONAL_SECURITY",
    )
    severity: str = Field(..., description="Severity level: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL")
    chunk_ids: list[uuid.UUID] = Field(default_factory=list, description="IDs of chunks where term appears")
    reason: str = Field(..., description="Explanation of why this term requires advisory caution")


class EntityRelationship(BaseModel):
    """Semantic relationship tuple between entities grounded in source chunks."""

    source: str = Field(..., description="Source entity name")
    relation: str = Field(..., description="Predicate/relation type (e.g. OPERATED_BY, TARGETS, LOCATED_IN)")
    target: str = Field(..., description="Target entity name")
    chunk_id: uuid.UUID | None = Field(default=None, description="Grounding chunk ID where relation was observed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score")


class DocumentUnderstandingResponse(BaseModel):
    """Complete structured understanding result for a document."""

    model_config = ConfigDict(from_attributes=True)

    doc_id: uuid.UUID = Field(..., description="Source document identifier")
    objective: str = Field(..., description="Extracted stated intent / operational mandate of document")
    topics: list[str] = Field(default_factory=list, description="Thematic topic tags")
    key_entities: list[EntityMention] = Field(default_factory=list, description="Extracted entities with types")
    sensitive_terms: list[SensitiveTerm] = Field(default_factory=list, description="Detected sensitive markers")
    relationships: list[EntityRelationship] = Field(default_factory=list, description="Extracted relationship tuples")
    summary: str = Field(default="", description="High-level operational abstract")
    total_chunks: int = Field(default=0, description="Total number of chunks produced")
    offset_accuracy_pct: float = Field(default=100.0, description="Percentage of chunks with exact offset verification")


class ProcessDocumentResponse(BaseModel):
    """Response returned upon completing Phase 2 understanding & chunking."""

    status: str = Field(default="success")
    doc_id: uuid.UUID
    chunks_count: int
    entities_count: int
    topics_count: int
    sensitive_terms_count: int
    relationships_count: int
    qdrant_indexed: bool = Field(default=True, description="True if vectors upserted into Qdrant collection")
    falkordb_indexed: bool = Field(default=True, description="True if graph nodes & edges upserted to FalkorDB")
    audit_entry_recorded: bool = Field(default=True, description="True if tamper-evident audit record committed")
    understanding: DocumentUnderstandingResponse


class SemanticSearchRequest(BaseModel):
    """Request payload for vector search in Qdrant."""

    query: str = Field(..., min_length=1, description="Topic or natural language query string")
    doc_id: uuid.UUID | None = Field(default=None, description="Optional doc_id filter")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum chunks to return")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum cosine similarity score")


class SemanticSearchResultItem(BaseModel):
    """Ranked chunk result from Qdrant vector retrieval."""

    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    chunk_index: int
    text: str
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    char_offset_start: int
    char_offset_end: int
    heading: str | None = None
    page_number: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None


class SemanticSearchResponse(BaseModel):
    """Response containing ranked vector search results."""

    query: str
    total_results: int
    results: list[SemanticSearchResultItem]


class GraphNode(BaseModel):
    """Node representation for knowledge graph visualization."""

    id: str
    label: str
    type: str  # Document, Chunk, Entity, Topic
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Edge representation for knowledge graph visualization."""

    source: str
    target: str
    relation: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphVisualizationResponse(BaseModel):
    """Knowledge graph payload formatted for frontend visualizer."""

    doc_id: uuid.UUID | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class EntityGraphQueryResponse(BaseModel):
    """FalkorDB query result for an individual entity."""

    entity_name: str
    entity_type: str
    connected_entities: list[dict[str, Any]]
    referenced_chunks: list[uuid.UUID]
    direct_relations: list[dict[str, Any]]
