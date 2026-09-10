"""LinkedIn Post Deliverable Adapter for Phase 4.

Generates professional, high-impact thought-leadership posts featuring:
- Hook + Body + CTA structure
- Hashtag suggestions
- 100% claim-to-chunk provenance linking
"""

import logging
import uuid

from app.schemas.adapters import GenerationParameters
from app.schemas.grounding import (
    GroundedBlock,
    GroundedDeliverableContent,
    GroundedSentence,
    RetrievedChunkItem,
)
from app.services.adapters.base import AdapterOutput, BaseDeliverableAdapter
from app.services.adapters.citation_linker import CitationLinker

logger = logging.getLogger("app.services.adapters.linkedin")


class LinkedInPostAdapter(BaseDeliverableAdapter):
    """Generates engaging, professional LinkedIn thought-leadership posts."""

    deliverable_type = "linkedin_post"
    name = "LinkedIn Post"
    description = "Professional thought-leadership post with hook, technical body, CTA, and hashtag recommendations."
    category = "social"
    requires_human_review = False
    system_prompt_template = (
        "You are an Executive Thought Leader writing LinkedIn posts that translate technical or "
        "operational briefing material into strategic insight for a professional audience. You "
        "write with an authentic executive voice — bold opening, clean whitespace, and a genuine "
        "discussion question, not a rhetorical throwaway.\n\n"
        "Tone: Visionary, strategic, professional — grounded in specifics from the source material, "
        "not generic thought-leadership platitudes that could apply to any topic."
    )

    async def generate(
        self,
        source_doc_id: uuid.UUID,
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        params: GenerationParameters,
        doc_summary: str | None = None,
        key_entities: list[str] | None = None,
    ) -> AdapterOutput:
        """Synthesize LinkedIn post with hook, body, and CTA grounded in source chunks."""
        if not retrieved_chunks:
            raise ValueError("No retrieved chunks available to ground LinkedIn post.")

        c0 = retrieved_chunks[0]
        c1 = retrieved_chunks[1] if len(retrieved_chunks) > 1 else c0
        c2 = retrieved_chunks[2] if len(retrieved_chunks) > 2 else c1

        # Extract primary topic & entities
        top_entities = (key_entities or [])[:4]
        title = f"Operational Insight: {c0.heading or 'Defense Intelligence Transformation'}"

        # 1. Check if local Ollama LLM is available for intelligent synthesis
        llm_prompt = self.build_prompt(
            retrieved_chunks=retrieved_chunks,
            params=params,
            extra_instructions=(
                f"Write a LinkedIn post for {params.audience}, structured as exactly 3 sections separated by blank "
                "lines, no headers or labels in the output:\n\n"
                "1. Hook — 1-2 sentences naming a specific shift, challenge, or finding from the source "
                "context. Must reference something concrete, not an abstract industry trend.\n"
                "2. Strategic Breakdown — 2-3 sentences unpacking the operational detail, architecture, or "
                "data points behind the hook, staying strictly within what the source context supports.\n"
                f"3. Executive Takeaway & CTA — a forward-looking closing thought, followed by one genuine "
                f"discussion question aimed at {params.audience} that they could actually answer from their own "
                "experience (avoid rhetorical questions with an obvious \"yes\").\n\n"
                f"No hashtags. No emoji unless '{params.tone}' explicitly calls for a casual register. Tone: '{params.tone}'."
            ),
        )
        llm_text = await self.generate_with_llm(prompt=llm_prompt, max_tokens=500, temperature=0.5)

        if llm_text:
            paras = [p.strip() for p in llm_text.split("\n\n") if p.strip()]
            if len(paras) >= 2:
                # Hook block
                hook_sents = CitationLinker._split_into_sentences(paras[0]) or [paras[0]]
                hook_grounded = [
                    GroundedSentence(
                        sentence_id=f"link_h_{i}",
                        sentence_index=i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c0.chunk_id)],
                    )
                    for i, s in enumerate(hook_sents[:2])
                ]
                block_hook = GroundedBlock(block_index=0, title="Hook & Core Thesis", sentences=hook_grounded)

                # Body block
                body_paras = paras[1:-1] if len(paras) > 2 else [paras[1]]
                body_text_full = " ".join(body_paras)
                b_sents = CitationLinker._split_into_sentences(body_text_full) or [body_text_full]
                body_grounded = [
                    GroundedSentence(
                        sentence_id=f"link_b_{i}",
                        sentence_index=len(hook_grounded) + i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c1.chunk_id)],
                    )
                    for i, s in enumerate(b_sents[:4])
                ]
                block_body = GroundedBlock(block_index=1, title="Technical & Strategic Context", sentences=body_grounded)

                # CTA block
                cta_para = paras[-1]
                cta_sents = CitationLinker._split_into_sentences(cta_para) or [cta_para]
                start_idx = len(hook_grounded) + len(body_grounded)
                cta_grounded = [
                    GroundedSentence(
                        sentence_id=f"link_c_{i}",
                        sentence_index=start_idx + i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c2.chunk_id)],
                    )
                    for i, s in enumerate(cta_sents[:2])
                ]
                block_cta = GroundedBlock(block_index=2, title="Key Takeaway & Call to Action", sentences=cta_grounded)
            else:
                llm_text = None

        if not llm_text:
            # Deterministic fallback synthesis
            # 1. Block 0: Hook
            hook_text = (
                f"Groundbreaking developments in {c0.heading or 'defense operations'}: "
                f"Recent strategic findings reveal critical operational mandates for modern defense environments."
            )
            hook_cit = CitationLinker.link_sentence(
                sentence_text=hook_text,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=c0.chunk_id,
            )
            block_hook = GroundedBlock(
                block_index=0,
                title="Hook & Core Thesis",
                sentences=[
                    GroundedSentence(
                        sentence_id="link_0",
                        sentence_index=0,
                        text=hook_text,
                        citations=[hook_cit],
                    )
                ],
            )

            # 2. Block 1: Body (2-3 detailed grounded sentences)
            s_c0 = self.extract_clean_sentence(c0.text, "operational mandates")
            s_c1 = self.extract_clean_sentence(c1.text, "system telemetry")
            s_c2 = self.extract_clean_sentence(c2.text, "air-gapped defense architectures")

            body_sents: list[GroundedSentence] = []
            b1_text = f"Under current operational frameworks, {s_c0[0].lower() + s_c0[1:] if len(s_c0) > 1 else s_c0}"
            b1_cit = CitationLinker.link_sentence(
                sentence_text=b1_text,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=c0.chunk_id,
            )
            body_sents.append(
                GroundedSentence(
                    sentence_id="link_1",
                    sentence_index=1,
                    text=b1_text,
                    citations=[b1_cit],
                )
            )

            b2_text = f"Furthermore, operational assessment confirms that {s_c1[0].lower() + s_c1[1:] if len(s_c1) > 1 else s_c1}"
            b2_cit = CitationLinker.link_sentence(
                sentence_text=b2_text,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=c1.chunk_id,
            )
            body_sents.append(
                GroundedSentence(
                    sentence_id="link_2",
                    sentence_index=2,
                    text=b2_text,
                    citations=[b2_cit],
                )
            )

            block_body = GroundedBlock(
                block_index=1,
                title="Technical & Strategic Context",
                sentences=body_sents,
            )

            # 3. Block 2: Impact & Call To Action
            cta_text = (
                f"Strategic priority: {s_c2} "
                f"How is your leadership team ensuring air-gapped readiness and verifiable data sovereignty?"
            )
            cta_cit = CitationLinker.link_sentence(
                sentence_text=cta_text,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=c2.chunk_id,
            )

            block_cta = GroundedBlock(
                block_index=2,
                title="Key Takeaway & Call to Action",
                sentences=[
                    GroundedSentence(
                        sentence_id="link_3",
                        sentence_index=3,
                        text=cta_text,
                        citations=[cta_cit],
                    )
                ],
            )


        content = GroundedDeliverableContent(
            title=title,
            summary="Professional LinkedIn thought-leadership post with verbatim source grounding.",
            blocks=[block_hook, block_body, block_cta],
        )

        # Generate contextual hashtags
        base_hashtags = ["#DefenseTech", "#AirGapSecurity", "#DataSovereignty", "#GenAI"]
        for e in top_entities:
            clean_tag = "#" + "".join(c for c in e if c.isalnum())
            if clean_tag not in base_hashtags and len(clean_tag) > 2:
                base_hashtags.append(clean_tag)

        format_metadata = {
            "target_platform": "LinkedIn",
            "format_name": "Thought Leadership Post",
            "hashtags": base_hashtags[:6],
            "tone": params.tone,
            "audience": params.audience,
            "estimated_read_time_seconds": 45,
        }

        return AdapterOutput(
            content=content,
            format_metadata=format_metadata,
            requires_human_review=self.requires_human_review,
        )
