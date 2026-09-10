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

        if not self.system_prompt_template:
            self.system_prompt_template = (
                "You are a Dynamic Content Synthesis Engine. You will be given a custom block schema "
                "describing the sections, order, and per-section constraints of a deliverable that does not "
                "match any of the system's fixed formats. Your job is to populate that schema faithfully "
                "from the source context, following its structural rules exactly as if it were a fixed "
                "format defined by an engineer.\n\n"
                f"Tone: Match whatever '{params.tone}' and '{params.style or 'standard'}' parameters are supplied; if the schema itself "
                "implies a register (e.g. field names like 'tweet_text' vs 'spec_paragraph'), let the field "
                "name's implied format override a mismatched general tone instruction, and note that you "
                "did so is not necessary — just apply the more specific rule."
            )

        # 1. Attempt LLM generation for dynamic deliverable
        block_titles = [b.get("title", f"Section {i+1}") for i, b in enumerate(blocks_config)]
        extra_instructions = (
            f"Synthesize the deliverable '{self.name}' tailored specifically for {params.audience}.\n"
            "1. Parse the provided block schema into its ordered list of fields, each with its own "
            "type (short text, bullet list, paragraph, numeric) and constraint (length, count):\n"
            + "\n".join(f"- {t}" for t in block_titles) + "\n"
            "2. Populate each field using only the <SOURCE_CONTEXT>, respecting that field's individual "
            "constraint exactly.\n"
            "3. If the schema requests a field type the source context cannot support (e.g., a numeric "
            "statistic field with no matching number in the source), return an explicit null/empty "
            "marker for that field rather than fabricating a plausible-looking value — the calling "
            "code should decide how to handle missing fields, not the model.\n"
            f"Provide exactly {len(blocks_config)} distinct sections separated by blank lines.\n"
            f"Tone: '{params.tone}'. Do NOT include section numbers or headers in your output."
        )
        llm_prompt = self.build_prompt(
            retrieved_chunks=retrieved_chunks,
            params=params,
            extra_instructions=extra_instructions,
        )
        llm_text = await self.generate_with_llm(prompt=llm_prompt, max_tokens=600, temperature=0.3)

        llm_paras: list[str] = []
        if llm_text:
            llm_paras = [p.strip() for p in llm_text.split("\n\n") if len(p.strip()) > 15]

        blocks: list[GroundedBlock] = []
        sent_counter = 0

        for i, b_cfg in enumerate(blocks_config):
            b_idx = b_cfg.get("index", i)
            b_title = b_cfg.get("title", f"Block #{b_idx}")
            target_chunk = retrieved_chunks[b_idx % len(retrieved_chunks)]

            if i < len(llm_paras):
                clause = llm_paras[i]
            else:
                chunk_sents = CitationLinker._split_into_sentences(target_chunk.text)
                clause = chunk_sents[0] if chunk_sents else self.extract_clean_sentence(target_chunk.text)

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
