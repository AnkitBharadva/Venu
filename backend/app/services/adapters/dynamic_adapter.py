"""Config-Driven Dynamic Deliverable Adapter for Phase 4.

Enables adding new deliverable formats purely through JSON/YAML configuration
without writing any new code.
"""

import logging
import uuid

from app.schemas.adapters import DynamicAdapterConfig, GenerationParameters
from app.schemas.grounding import (
    GroundedBlock,
    GroundedDeliverableContent,
    GroundedSentence,
    RetrievedChunkItem,
)
from app.services.adapters.base import AdapterOutput, BaseDeliverableAdapter
from app.services.adapters.citation_linker import CitationLinker

logger = logging.getLogger("app.services.adapters.dynamic")


class ConfigDrivenAdapter(BaseDeliverableAdapter):
    """Deliverable adapter configured dynamically via DynamicAdapterConfig."""

    def __init__(self, config: DynamicAdapterConfig) -> None:
        self.config = config
        self.deliverable_type = config.deliverable_type
        self.name = config.name
        self.description = config.description
        self.category = config.category
        self.requires_human_review = config.requires_human_review
        self.system_prompt_template = config.system_prompt_template

    async def generate(
        self,
        source_doc_id: uuid.UUID,
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        params: GenerationParameters,
        doc_summary: str | None = None,
        key_entities: list[str] | None = None,
    ) -> AdapterOutput:
        """Execute dynamic deliverable generation based on configured block structure."""
        if not retrieved_chunks:
            raise ValueError(f"No retrieved chunks available to ground format '{self.deliverable_type}'.")

        blocks_config = self.config.block_structure
        if not blocks_config:
            # Default to one block per chunk
            blocks_config = [
                {"index": i, "title": f"Section {i+1}: {c.heading or 'Analysis'}"}
                for i, c in enumerate(retrieved_chunks[:4])
            ]

        blocks: list[GroundedBlock] = []
        sent_counter = 0

        for b_cfg in blocks_config:
            b_idx = b_cfg.get("index", len(blocks))
            b_title = b_cfg.get("title", f"Block #{b_idx}")

            target_chunk = retrieved_chunks[b_idx % len(retrieved_chunks)]
            clause = target_chunk.text.strip().split(".")[0].strip() + "."

            cit = CitationLinker.link_sentence(
                sentence_text=clause,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=target_chunk.chunk_id,
            )

            sent = GroundedSentence(
                sentence_id=f"{self.deliverable_type}_{sent_counter}",
                sentence_index=sent_counter,
                text=clause,
                citations=[cit],
            )
            sent_counter += 1

            blocks.append(
                GroundedBlock(
                    block_index=b_idx,
                    title=b_title,
                    sentences=[sent],
                )
            )

        title = f"{self.name}: {retrieved_chunks[0].heading or 'Grounded Analysis'}"
        content = GroundedDeliverableContent(
            title=title,
            summary=f"Dynamically configured deliverable format '{self.deliverable_type}' generated via config.",
            blocks=blocks,
        )

        format_metadata = {
            **self.config.format_metadata_defaults,
            "format_type": self.deliverable_type,
            "config_driven": True,
            "total_blocks": len(blocks),
        }

        return AdapterOutput(
            content=content,
            format_metadata=format_metadata,
            requires_human_review=self.requires_human_review,
        )
