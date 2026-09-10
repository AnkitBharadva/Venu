"""Base Deliverable Adapter Interface for Phase 4.

Defines the common adapter contract:
generate(source_doc_id, retrieved_context, params) -> { content, citations, format_metadata }
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.schemas.adapters import GenerationParameters
from app.schemas.grounding import (
    GroundedDeliverableContent,
    RetrievedChunkItem,
)

logger = logging.getLogger("app.services.adapters.base")


@dataclass
class AdapterOutput:
    """Standardized output produced by any deliverable generation adapter."""

    content: GroundedDeliverableContent
    format_metadata: dict[str, Any] = field(default_factory=dict)
    requires_human_review: bool = False
    reviewer_notes: str | None = None


class BaseDeliverableAdapter(ABC):
    """Abstract base class for all output deliverable generation adapters."""

    deliverable_type: str
    name: str
    description: str
    category: str = "general"
    requires_human_review: bool = False
    system_prompt_template: str = (
        "You are an air-gapped content transformation specialist. "
        "Strict Rule: Only state facts explicitly present in the provided context. "
        "Every single generated sentence must be grounded in an authentic source chunk."
    )

    @abstractmethod
    async def generate(
        self,
        source_doc_id: uuid.UUID,
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        params: GenerationParameters,
        doc_summary: str | None = None,
        key_entities: list[str] | None = None,
    ) -> AdapterOutput:
        """Execute generation and produce a fully grounded, citation-bound deliverable.

        Args:
            source_doc_id: UUID of source document.
            retrieved_chunks: Top-k grounded chunks from hybrid retrieval.
            raw_text: Full verbatim text of source document for offset slicing.
            params: Operator configurable parameters (audience, tone, language, detail, objective, style).
            doc_summary: Optional high-level summary from understanding layer.
            key_entities: Optional list of identified named entities.

        Returns:
            AdapterOutput with GroundedDeliverableContent and format-specific metadata.
        """
        pass

    def build_prompt(
        self,
        retrieved_chunks: list[RetrievedChunkItem],
        params: GenerationParameters,
        extra_instructions: str = "",
    ) -> str:
        """Construct standard air-gapped prompt with strict grounding constraints."""
        context_blocks = []
        for c in retrieved_chunks:
            hd = f" [Section: {c.heading}]" if c.heading else ""
            context_blocks.append(f"--- SOURCE CHUNK #{c.chunk_index} (ID: {c.chunk_id}){hd} ---\n{c.text}")
        joined_context = "\n\n".join(context_blocks)

        prompt = (
            f"{self.system_prompt_template}\n\n"
            f"TARGET PARAMETERS:\n"
            f"- Audience: {params.audience}\n"
            f"- Tone: {params.tone}\n"
            f"- Detail Level: {params.detail_level}\n"
            f"- Language: {params.language}\n"
        )
        if params.objective:
            prompt += f"- Objective: {params.objective}\n"
        if params.style:
            prompt += f"- Style: {params.style}\n"
        if params.custom_instructions:
            prompt += f"- Custom Constraints: {params.custom_instructions}\n"
        if extra_instructions:
            prompt += f"\nFORMAT CONSTRAINTS:\n{extra_instructions}\n"

        prompt += f"\nGROUNDED SOURCE CONTEXT:\n{joined_context}\n"
        return prompt
