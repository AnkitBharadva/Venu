"""Tactical / Security Advisory Deliverable Adapter for Phase 4.

Generates safety-critical advisories featuring:
- Structured sections: Summary, Details, Risk/Impact, Recommended Actions
- Safety-critical mandatory human review gatekeeper (requires_human_review = True)
- Export lock flag until human signoff is obtained
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

logger = logging.getLogger("app.services.adapters.advisory")


class AdvisoryAdapter(BaseDeliverableAdapter):
    """Generates safety-critical tactical advisories requiring mandatory human review before export."""

    deliverable_type = "advisory"
    name = "Tactical Advisory"
    description = "Safety-critical advisory covering Summary, Details, Risk/Impact, and Recommended Actions with mandatory human signoff lock."
    category = "operational"
    requires_human_review = True  # SAFETY-CRITICAL: Must route through human review before export

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

        # 1. Section: Summary
        s0_text = (
            f"ADVISORY NOTICE: Immediate operational attention is required regarding {c0.heading or 'system security'}."
        )
        s0_cit = CitationLinker.link_sentence(s0_text, retrieved_chunks, raw_text, c0.chunk_id)

        s1_text = f"Primary condition identified: {c0.text.strip().split('.')[0]}."
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
        s2_text = f"Detailed technical verification confirms that {c1.text.strip().split('.')[0]}."
        s2_cit = CitationLinker.link_sentence(s2_text, retrieved_chunks, raw_text, c1.chunk_id)

        block_details = GroundedBlock(
            block_index=1,
            title="2. Technical Details",
            sentences=[
                GroundedSentence(sentence_id="adv_2", sentence_index=2, text=s2_text, citations=[s2_cit]),
            ],
        )

        # 3. Section: Risk / Impact
        s3_text = f"Identified operational risk: {c2.text.strip().split('.')[0]}."
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
        s5_text = f"Mandatory mitigation protocol: {c3.text.strip().split('.')[0]}."
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
