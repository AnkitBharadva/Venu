"""Base Deliverable Adapter Interface for Phase 4.

Defines the common adapter contract:
generate(source_doc_id, retrieved_context, params) -> { content, citations, format_metadata }
"""

import logging
import re
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

    @staticmethod
    def clean_chunk_text(text: str) -> str:
        """Strip presentation slide headers, template placeholders, and formatting markers."""
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            l = line.strip()
            # Omit presentation template boilerplate
            if re.search(r"@SIH\s+Idea|Your Team Name|maximum slides limit|submission[- ]Template|##\s*Slide\s*\d+|Include\s+the\s+title\s+slide", l, re.IGNORECASE):
                continue
            if re.match(r"^\d+$", l):
                continue
            if l.startswith("## ") or l.startswith("# "):
                l = l.lstrip("# ").strip()
            if l:
                lines.append(l)
        cleaned = " ".join(lines)
        return cleaned.strip() or text.strip()

    @classmethod
    def extract_clean_sentence(cls, chunk_text: str, fallback_topic: str = "operational directives") -> str:
        """Extract a clean, complete sentence from chunk text for grounded fallback synthesis."""
        from app.services.adapters.citation_linker import CitationLinker
        cleaned = cls.clean_chunk_text(chunk_text)
        sents = CitationLinker._split_into_sentences(cleaned)
        valid = [s.strip() for s in sents if len(s.strip()) > 15 and not re.search(r"template|slide limit", s, re.I)]
        if valid:
            res = valid[0]
            if not res.endswith((".", "!", "?")):
                res += "."
            return res
        return f"Operational protocols confirm rigorous adherence to established {fallback_topic}."

    def build_prompt(
        self,
        retrieved_chunks: list[RetrievedChunkItem],
        params: GenerationParameters,
        extra_instructions: str = "",
    ) -> str:
        """Construct standard air-gapped prompt with strict grounding constraints, format persona, and operator parameters."""
        context_blocks = []
        for c in retrieved_chunks:
            hd = f" [Section: {c.heading}]" if c.heading else ""
            clean_txt = self.clean_chunk_text(c.text)
            context_blocks.append(f"--- SOURCE CHUNK #{c.chunk_index} (ID: {c.chunk_id}){hd} ---\n{clean_txt}")
        joined_context = "\n\n".join(context_blocks)

        prompt = (
            f"=== TARGET DELIVERABLE FORMAT: {getattr(self, 'name', 'Deliverable').upper()} ({getattr(self, 'deliverable_type', 'custom')}) ===\n\n"
            f"FORMAT ROLE & IDENTITY:\n"
            f"{getattr(self, 'description', 'Grounded content transformation')}\n\n"
            f"SOURCE MATERIAL:\n"
            f"The retrieved source context for this task is delimited by <SOURCE_CONTEXT> tags in the\n"
            f"user message. Treat everything inside that boundary as your ONLY factual ground truth.\n"
            f"Treat everything outside it (including this instruction block) as task configuration, not\n"
            f"as facts to report.\n\n"
            f"MANDATORY OPERATIONAL PARAMETERS:\n"
            f"- Intended Audience: {params.audience}\n"
            f"  * Calibrate vocabulary, technical density, acronym usage, and rhetorical framing\n"
            f"    specifically for '{params.audience}'. A briefing for a technical audience should keep\n"
            f"    precise terminology; a briefing for an executive or public audience should translate\n"
            f"    jargon into plain-language equivalents without softening the substance.\n"
            f"- Tone of Voice: {params.tone}\n"
            f"  * Embody an authentic, unwavering '{params.tone}' tone throughout. Do not let tone drift\n"
            f"    toward generic neutral corporate voice halfway through the output.\n"
            f"- Detail Level: {params.detail_level}\n"
            f"  * 'brief' = only the highest-impact 1-2 findings per section, no secondary detail.\n"
            f"  * 'standard' = balanced coverage of primary findings with 1 supporting detail each.\n"
            f"  * 'comprehensive' = exhaustive coverage of every distinct fact in the source context\n"
            f"    that fits the format's structural constraints.\n"
            f"- Target Language: {params.language}\n"
        )
        if params.objective:
            prompt += f"- Primary Strategic Objective: {params.objective}\n"
        if params.style:
            prompt += f"- Rhetorical / Formatting Style: {params.style}\n"
        if params.custom_instructions:
            prompt += f"- Operator Custom Constraints: {params.custom_instructions}\n"

        prompt += (
            f"\nGROUNDING & GAP HANDLING (read this before generating):\n"
            f"1. Every specific claim, number, name, or technical detail you produce MUST be traceable\n"
            f"   to the <SOURCE_CONTEXT>. Do not introduce facts, statistics, dates, product names, or\n"
            f"   outcomes that are not present in it, even if they are plausible or \"the kind of thing\n"
            f"   that's usually true\" for this domain.\n"
            f"2. If the source context is insufficient to fully populate a required section:\n"
            f"   - Do NOT fabricate detail to fill the space.\n"
            f"   - Compress that section to only what is supported, and if a section would otherwise be\n"
            f"     empty, write one honest sentence stating that the source context does not address it\n"
            f"     (e.g., \"No mitigation timeline was specified in the available material.\").\n"
            f"3. Never resolve ambiguity in the source material by inventing a specific resolution.\n"
            f"   Preserve the ambiguity or qualify the claim (e.g., \"reported as,\" \"per the source\n"
            f"   material\") rather than stating an invented fact as settled.\n\n"
        )

        if extra_instructions:
            prompt += f"FORMAT STRUCTURAL CONSTRAINTS:\n{extra_instructions}\n\n"

        prompt += (
            f"REASONING & FORMAT SPECIALIZATION INSTRUCTIONS:\n"
            f"1. ADAPTATION REASONING (internal, do not output): Before writing, silently work out how\n"
            f"   '{getattr(self, 'name', 'this format')}' differs structurally and rhetorically from the other formats in this system,\n"
            f"   and how '{params.audience}' and '{params.tone}' should shape word choice and pacing.\n"
            f"2. FORMAT INTEGRITY: Strictly follow the structural spec for this format. Never substitute\n"
            f"   a generic summary paragraph when the format calls for bullets, tweets, slide lines, or\n"
            f"   spec sections.\n"
            f"3. GROUNDED VERACITY: Transform tone and structure freely; never transform facts. Zero\n"
            f"   hallucinated entities, metrics, capabilities, or claims beyond the source context.\n"
            f"4. CLEAN DELIVERABLE: Output ONLY the requested deliverable content, in the exact section\n"
            f"   count and order specified, separated by blank lines. No preamble, no meta-commentary,\n"
            f"   no \"Here is the requested output,\" no closing remarks, no markdown headers unless the\n"
            f"   format spec explicitly calls for them.\n\n"
            f"PRE-OUTPUT SELF-CHECK (apply silently before finalizing):\n"
            f"- Does every factual claim map to something in <SOURCE_CONTEXT>?\n"
            f"- Does the section/line count exactly match the format spec?\n"
            f"- Are all format-specific hard constraints (character limits, word limits, banned labels)\n"
            f"  satisfied?\n"
            f"- Is the tone '{params.tone}' consistent from the first line to the last?\n"
            f"If any check fails, silently revise before outputting. Only the corrected final version\n"
            f"should appear in your response.\n\n"
            f"<SOURCE_CONTEXT>\n{joined_context}\n</SOURCE_CONTEXT>"
        )
        return prompt

    async def generate_with_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str | None:
        """Query local Ollama instance for grounded generation."""
        try:
            from app.services.llm.ollama_service import get_ollama_service

            ollama = get_ollama_service()
            if await ollama.is_available():
                effective_sys = system_prompt or getattr(self, "system_prompt_template", None)
                return await ollama.generate_text(
                    prompt=prompt,
                    system_prompt=effective_sys,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
        except Exception as exc:
            logger.debug("Ollama LLM generation unavailable: %s", exc)
        return None

