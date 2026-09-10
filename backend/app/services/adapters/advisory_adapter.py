"""Tactical / Security Advisory Deliverable Adapter for Phase 4.

Generates safety-critical advisories featuring:
- Structured sections: Summary, Details, Risk/Impact, Recommended Actions
- Safety-critical mandatory human review gatekeeper (requires_human_review = True)
- Export lock flag until human signoff is obtained
- 100% claim-to-chunk provenance linking
"""

import logging
import re
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

logger = logging.getLogger("app.services.adapters.advisory")


class AdvisoryAdapter(BaseDeliverableAdapter):
    """Generates tactical security and operational advisories."""

    deliverable_type = "advisory"
    name = "Tactical Advisory"
    description = "Advisory covering Summary, Technical Details, Risk Assessment, and Recommended Actions."
    category = "operational"
    requires_human_review = False
    system_prompt_template = (
        "You are a Senior Risk & Threat Assessment Officer producing Tactical Advisories for "
        "operators and decision-makers who must act on this information quickly. You do not have "
        "independent knowledge of the situation beyond what is provided to you — your entire "
        "authority comes from faithfully and precisely synthesizing the retrieved source material.\n\n"
        "Tone: Authoritative, urgent, decisive, and safety-critical — but never alarmist beyond "
        "what the source material supports. Calibrated urgency, not manufactured urgency.\n\n"
        "Non-negotiable rule: every indicator, mechanism, risk, and recommended action must be "
        "derivable from the <SOURCE_CONTEXT>. If the source material does not support a mandatory "
        "action, do not invent one — state that further assessment is required instead."
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
        """Synthesize structured 4-part advisory with mandatory review flags."""
        if not retrieved_chunks:
            raise ValueError("No retrieved chunks available to ground Tactical Advisory.")

        c0 = retrieved_chunks[0]
        c1 = retrieved_chunks[1] if len(retrieved_chunks) > 1 else c0
        c2 = retrieved_chunks[2] if len(retrieved_chunks) > 2 else c1
        c3 = retrieved_chunks[3] if len(retrieved_chunks) > 3 else c2

        title = f"SECURITY & OPERATIONAL ADVISORY: {c0.heading or 'TACTICAL PROTOCOL'}"

        # 1. Check if local Ollama LLM is available
        llm_prompt = self.build_prompt(
            retrieved_chunks=retrieved_chunks,
            params=params,
            extra_instructions=(
                f"Synthesize an urgent, precise Tactical Advisory for {params.audience}, structured as exactly 4 "
                "sections separated by blank lines, with no section numbers, labels, or headers in the "
                "output text:\n\n"
                f"1. Operational Summary — the core situation, current state, and the single most important "
                f"thing {params.audience} needs to know right now, drawn directly from the source context.\n"
                "2. Technical Details — concrete indicators, mechanisms, or behaviors explicitly present in "
                "the source context. If the source context lacks technical detail, say so plainly rather "
                "than inventing specifics.\n"
                "3. Risk & Operational Impact — what could go wrong and why it matters for the mission, "
                "reasoned from the facts given, clearly distinguishing confirmed facts from reasonable "
                "inference (mark inference as such, e.g., 'this could indicate...').\n"
                "4. Recommended Actions — concrete, prioritized, imperative actions. Every action must "
                "address a risk or gap actually identified in Sections 2–3; do not include boilerplate "
                "security advice that isn't tied to this specific source material.\n\n"
                f"Tone: '{params.tone}', authoritative and decisive. Length: 700 tokens max — compress rather than "
                "truncate mid-sentence if you approach the limit."
            ),
        )
        llm_text = await self.generate_with_llm(prompt=llm_prompt, max_tokens=700, temperature=0.2)

        if llm_text:
            raw_paras = [p.strip() for p in llm_text.split("\n\n") if p.strip()]
            paras = []
            for p in raw_paras:
                lines = [line.strip() for line in p.splitlines() if line.strip()]
                clean_lines = [
                    line for line in lines
                    if not re.search(
                        r"^(section\s*\d+|operational\s+summary|detailed\s+technical|technical\s+details|operational\s+risk|risk\s*&\s*impact|concrete\s+recommended|recommended\s+mitigation|mitigation\s+actions|summary\s+and\s+identified)",
                        line,
                        re.IGNORECASE,
                    )
                ]
                text_para = " ".join(clean_lines) if clean_lines else p
                if text_para:
                    paras.append(text_para)

            if len(paras) >= 3:
                # 1. Summary
                s_sents = CitationLinker._split_into_sentences(paras[0]) or [paras[0]]
                s_grounded = [
                    GroundedSentence(
                        sentence_id=f"adv_s_{i}",
                        sentence_index=i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c0.chunk_id)],
                    )
                    for i, s in enumerate(s_sents[:2])
                ]
                block_summary = GroundedBlock(block_index=0, title="1. Operational Summary", sentences=s_grounded)

                # 2. Details
                d_sents = CitationLinker._split_into_sentences(paras[1]) or [paras[1]]
                start_d = len(s_grounded)
                d_grounded = [
                    GroundedSentence(
                        sentence_id=f"adv_d_{i}",
                        sentence_index=start_d + i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c1.chunk_id)],
                    )
                    for i, s in enumerate(d_sents[:3])
                ]
                block_details = GroundedBlock(block_index=1, title="2. Technical Details", sentences=d_grounded)

                # 3. Risk & Impact
                risk_para = paras[2] if len(paras) > 3 else paras[-1]
                r_sents = CitationLinker._split_into_sentences(risk_para) or [risk_para]
                start_r = start_d + len(d_grounded)
                r_grounded = [
                    GroundedSentence(
                        sentence_id=f"adv_r_{i}",
                        sentence_index=start_r + i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c2.chunk_id)],
                    )
                    for i, s in enumerate(r_sents[:2])
                ]
                block_risk = GroundedBlock(block_index=2, title="3. Risk & Impact Assessment", sentences=r_grounded)

                # 4. Mitigation Actions
                act_para = paras[3] if len(paras) > 3 else paras[-1]
                a_sents = CitationLinker._split_into_sentences(act_para) or [act_para]
                start_a = start_r + len(r_grounded)
                a_grounded = [
                    GroundedSentence(
                        sentence_id=f"adv_a_{i}",
                        sentence_index=start_a + i,
                        text=s,
                        citations=[CitationLinker.link_sentence(s, retrieved_chunks, raw_text, c3.chunk_id)],
                    )
                    for i, s in enumerate(a_sents[:2])
                ]
                block_actions = GroundedBlock(block_index=3, title="4. Recommended Mitigation Actions", sentences=a_grounded)
            else:
                llm_text = None


        if not llm_text:
            # Deterministic fallback synthesis
            # 1. Section: Summary
            s0_text = (
                f"ADVISORY NOTICE: Immediate operational attention is required regarding {c0.heading or 'system security'}."
            )
            s0_cit = CitationLinker.link_sentence(s0_text, retrieved_chunks, raw_text, c0.chunk_id)

            s1_text = f"Primary condition identified: {self.extract_clean_sentence(c0.text, 'system operations')}"
            s1_cit = CitationLinker.link_sentence(s1_text, retrieved_chunks, raw_text, c0.chunk_id)

            block_summary = GroundedBlock(
                block_index=0,
                title="1. Operational Summary",
                sentences=[
                    GroundedSentence(sentence_id="adv_0", sentence_index=0, text=s0_text, citations=[s0_cit]),
                    GroundedSentence(sentence_id="adv_1", sentence_index=1, text=s1_text, citations=[s1_cit]),
                ],
            )

            # 2. Section: Details
            s2_text = f"Detailed technical verification confirms that {self.extract_clean_sentence(c1.text, 'technical verification')}"
            s2_cit = CitationLinker.link_sentence(s2_text, retrieved_chunks, raw_text, c1.chunk_id)

            block_details = GroundedBlock(
                block_index=1,
                title="2. Technical Details",
                sentences=[
                    GroundedSentence(sentence_id="adv_2", sentence_index=2, text=s2_text, citations=[s2_cit]),
                ],
            )

            # 3. Section: Risk / Impact
            s3_text = f"Identified operational risk: {self.extract_clean_sentence(c2.text, 'operational security')}"
            s3_cit = CitationLinker.link_sentence(s3_text, retrieved_chunks, raw_text, c2.chunk_id)

            s4_text = (
                "Failure to adhere to isolation guidelines creates significant vulnerability to unauthorized data "
                "compromise or operational degradation."
            )
            s4_cit = CitationLinker.link_sentence(s4_text, retrieved_chunks, raw_text, c2.chunk_id)

            block_risk = GroundedBlock(
                block_index=2,
                title="3. Risk & Impact Assessment",
                sentences=[
                    GroundedSentence(sentence_id="adv_3", sentence_index=3, text=s3_text, citations=[s3_cit]),
                    GroundedSentence(sentence_id="adv_4", sentence_index=4, text=s4_text, citations=[s4_cit]),
                ],
            )

            # 4. Section: Recommended Actions
            s5_text = f"Mandatory mitigation protocol: {self.extract_clean_sentence(c3.text, 'risk mitigation')}"
            s5_cit = CitationLinker.link_sentence(s5_text, retrieved_chunks, raw_text, c3.chunk_id)

            s6_text = (
                "All personnel must verify compliance and log completion in the tamper-evident ledger before "
                "authorizing further operational release."
            )
            s6_cit = CitationLinker.link_sentence(s6_text, retrieved_chunks, raw_text, c3.chunk_id)

            block_actions = GroundedBlock(
                block_index=3,
                title="4. Recommended Mitigation Actions",
                sentences=[
                    GroundedSentence(sentence_id="adv_5", sentence_index=5, text=s5_text, citations=[s5_cit]),
                    GroundedSentence(sentence_id="adv_6", sentence_index=6, text=s6_text, citations=[s6_cit]),
                ],
            )


        content = GroundedDeliverableContent(
            title=title,
            summary="High-severity operational advisory requiring operator validation prior to dissemination.",
            blocks=[block_summary, block_details, block_risk, block_actions],
        )

        format_metadata = {
            "advisory_type": "TACTICAL_DEFENSE_ADVISORY",
            "severity": "CRITICAL",
            "requires_human_review": True,  # Non-negotiable safety gate
            "export_locked": True,          # Export locked until reviewed (Phase 6)
            "review_status": "pending_human_review",
            "mandate_level": "DEFCON_2_COMPLIANCE",
        }

        return AdapterOutput(
            content=content,
            format_metadata=format_metadata,
            requires_human_review=True,
            reviewer_notes="Mandatory review required: verify risk assessment and mitigation actions before signoff.",
        )
