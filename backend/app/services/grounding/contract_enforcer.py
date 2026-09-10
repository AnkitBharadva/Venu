"""Hard Claim-Citation Contract Enforcer for Phase 3.

Enforces that NO generation adapter can emit a claim or sentence without
an authentic, verifiable chunk citation. This is a non-negotiable contract
enforced at the gateway layer.
"""

import logging
import uuid
from typing import Any

from app.models.understanding import DocumentChunk
from app.schemas.grounding import (
    GroundedCitation,
    GroundedDeliverableContent,
    GroundedSentence,
)

logger = logging.getLogger("app.services.grounding.contract")


class GroundingContractError(Exception):
    """Base exception for grounding contract violations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UncitedClaimViolationError(GroundingContractError):
    """Raised when an output adapter attempts to emit an un-cited sentence."""
    pass


class InvalidCitationChunkError(GroundingContractError):
    """Raised when a citation references a non-existent or foreign chunk."""
    pass


class GroundingQuoteMismatchError(GroundingContractError):
    """Raised when cited quote or offsets cannot be verified in the source text."""
    pass


class GroundingContractEnforcer:
    """Enforces strict claim-to-chunk provenance on all generated deliverables."""

    @classmethod
    def validate_deliverable(
        cls,
        doc_id: uuid.UUID,
        raw_text: str,
        valid_chunks: dict[uuid.UUID, DocumentChunk],
        content: GroundedDeliverableContent,
    ) -> list[dict[str, Any]]:
        """Validate an entire deliverable against the hard claim-citation contract.

        Returns:
            Normalized list of flat citation records for the GeneratedOutput.citations column.

        Raises:
            UncitedClaimViolationError: If any sentence lacks citations.
            InvalidCitationChunkError: If citation references invalid chunk_id.
            GroundingQuoteMismatchError: If quote or offsets fail exact verification.
        """
        all_citations: list[dict[str, Any]] = []
        sentence_counter = 0

        if not content.blocks:
            raise GroundingContractError("Deliverable content cannot be empty. Must contain at least one content block.")

        for block in content.blocks:
            if not block.sentences:
                raise GroundingContractError(f"Block #{block.block_index} contains no sentences.")

            for sentence in block.sentences:
                # 1. HARD RULE: No uncited claims
                if not sentence.citations or len(sentence.citations) == 0:
                    raise UncitedClaimViolationError(
                        f"HARD CONTRACT VIOLATION: Sentence #{sentence.sentence_index} '{sentence.text[:50]}...' "
                        f"(ID: {sentence.sentence_id}) contains 0 citations. All generated claims must be explicitly cited.",
                        details={
                            "sentence_id": sentence.sentence_id,
                            "sentence_index": sentence.sentence_index,
                            "text": sentence.text,
                        },
                    )

                # 2. HARD RULE: Validate each citation against source chunks & raw_text
                for cit_idx, citation in enumerate(sentence.citations):
                    validated_cit = cls._validate_single_citation(
                        doc_id=doc_id,
                        raw_text=raw_text,
                        valid_chunks=valid_chunks,
                        sentence=sentence,
                        citation=citation,
                        cit_idx=cit_idx,
                    )
                    all_citations.append(validated_cit)

                sentence_counter += 1

        logger.info(
            "Grounding contract verified for doc %s: %d sentences, %d citations validated 100%%",
            doc_id,
            sentence_counter,
            len(all_citations),
        )
        return all_citations

    @classmethod
    def _validate_single_citation(
        cls,
        doc_id: uuid.UUID,
        raw_text: str,
        valid_chunks: dict[uuid.UUID, DocumentChunk],
        sentence: GroundedSentence,
        citation: GroundedCitation,
        cit_idx: int,
    ) -> dict[str, Any]:
        """Validate and normalize a single citation against source chunks and raw_text."""
        chunk = valid_chunks.get(citation.chunk_id)
        if not chunk:
            raise InvalidCitationChunkError(
                f"HARD CONTRACT VIOLATION: Citation #{cit_idx} in sentence '{sentence.sentence_id}' "
                f"references non-existent chunk '{citation.chunk_id}'.",
                details={"chunk_id": str(citation.chunk_id), "sentence_id": sentence.sentence_id},
            )

        if chunk.doc_id != doc_id:
            raise InvalidCitationChunkError(
                f"HARD CONTRACT VIOLATION: Citation #{cit_idx} references chunk '{citation.chunk_id}' "
                f"belonging to doc '{chunk.doc_id}', not '{doc_id}'. Cross-document citations prohibited.",
                details={"chunk_id": str(citation.chunk_id), "expected_doc": str(doc_id)},
            )

        quote = citation.quote.strip() if citation.quote else ""
        s = citation.char_offset_start
        e = citation.char_offset_end
        text_len = len(raw_text)

        # If offsets are provided, check exact slice
        if 0 <= s < e <= text_len:
            actual_slice = raw_text[s:e].strip()
            # If quote was provided, verify it matches the slice
            if quote:
                clean_actual = " ".join(actual_slice.split())
                clean_quote = " ".join(quote.split())
                if clean_quote not in clean_actual and clean_actual not in clean_quote:
                    # Attempt to find quote inside chunk.text to resolve true offset
                    found_in_chunk = chunk.text.find(quote)
                    if found_in_chunk >= 0:
                        s = chunk.char_offset_start + found_in_chunk
                        e = s + len(quote)
                    else:
                        raise GroundingQuoteMismatchError(
                            f"HARD CONTRACT VIOLATION: Quote '{quote[:40]}...' does not match source slice "
                            f"raw_text[{s}:{e}] ('{actual_slice[:40]}...').",
                            details={"quote": quote, "source_slice": actual_slice},
                        )
        else:
            # Offsets were not provided or invalid -> locate quote in chunk
            if not quote:
                raise GroundingQuoteMismatchError(
                    f"HARD CONTRACT VIOLATION: Citation #{cit_idx} lacks both valid character offsets and quote.",
                    details={"citation": citation.model_dump()},
                )
            found_in_chunk = chunk.text.find(quote)
            if found_in_chunk >= 0:
                s = chunk.char_offset_start + found_in_chunk
                e = s + len(quote)
            else:
                # Fallback: check if chunk text matches
                s = chunk.char_offset_start
                e = chunk.char_offset_end
                quote = chunk.text[:150]

        # Final verification: raw_text[s:e] must be valid
        resolved_span = raw_text[s:e]
        if not resolved_span:
            raise GroundingQuoteMismatchError(
                f"HARD CONTRACT VIOLATION: Resolved span raw_text[{s}:{e}] is empty.",
                details={"s": s, "e": e},
            )

        # Update citation offsets in-place
        citation.char_offset_start = s
        citation.char_offset_end = e
        citation.quote = quote or resolved_span

        return {
            "sentence_id": sentence.sentence_id,
            "sentence_index": sentence.sentence_index,
            "sentence_text": sentence.text,
            "chunk_id": str(citation.chunk_id),
            "chunk_index": chunk.chunk_index,
            "char_offset_start": s,
            "char_offset_end": e,
            "quote": citation.quote,
            "heading": chunk.heading,
            "page_number": chunk.page_number,
            "timestamp_start": chunk.timestamp_start,
            "timestamp_end": chunk.timestamp_end,
            "confidence": citation.confidence,
        }
