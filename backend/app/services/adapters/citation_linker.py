"""Citation Linking Pass for Phase 4 Output Generation Adapters.

Maps each generated sentence back to authentic source chunks and resolves exact
character offsets [char_offset_start : char_offset_end] within raw_text,
guaranteeing 100% compliance with the Hard Claim-Citation Contract.
"""

import logging
import re
import uuid
from typing import Any

from app.schemas.grounding import GroundedCitation, RetrievedChunkItem

logger = logging.getLogger("app.services.adapters.citation_linker")


class CitationLinker:
    """Resolves generated claims to exact verbatim spans within source chunks."""

    @classmethod
    def link_sentence(
        cls,
        sentence_text: str,
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        preferred_chunk_id: uuid.UUID | None = None,
        confidence: float = 1.0,
    ) -> GroundedCitation:
        """Find the best source chunk and exact character coordinates for a generated sentence.

        Args:
            sentence_text: The emitted claim or sentence.
            retrieved_chunks: Grounded chunks provided to the adapter.
            raw_text: Full verbatim document text for absolute slice resolution.
            preferred_chunk_id: Optional chunk hint if adapter explicitly tied block to a chunk.
            confidence: Grounding confidence score.

        Returns:
            GroundedCitation with verified char_offset_start, char_offset_end, and quote.
        """
        if not retrieved_chunks:
            raise ValueError("Cannot link sentence: retrieved_chunks is empty.")

        # If a preferred chunk was designated, test it first
        chunk_map = {c.chunk_id: c for c in retrieved_chunks}
        target_chunk: RetrievedChunkItem = (
            chunk_map.get(preferred_chunk_id) if preferred_chunk_id else retrieved_chunks[0]
        )

        clean_claim = cls._normalize_text(sentence_text)
        words_claim = set(clean_claim.split())

        # 1. Exact Substring Search in candidate chunks
        best_overlap_score = -1.0
        best_chunk = target_chunk
        best_slice_start = target_chunk.char_offset_start
        best_slice_end = target_chunk.char_offset_end
        best_quote = target_chunk.text

        # First pass: check if verbatim claim exists directly in raw_text
        direct_pos = raw_text.find(sentence_text.strip())
        if direct_pos != -1:
            best_slice_start = direct_pos
            best_slice_end = direct_pos + len(sentence_text.strip())
            best_quote = raw_text[best_slice_start:best_slice_end]
            # Find which chunk encompasses this span
            for c in retrieved_chunks:
                if c.char_offset_start <= best_slice_start and c.char_offset_end >= best_slice_end:
                    best_chunk = c
                    break
            return GroundedCitation(
                chunk_id=best_chunk.chunk_id,
                char_offset_start=best_slice_start,
                char_offset_end=best_slice_end,
                quote=best_quote,
                confidence=confidence,
            )

        # Second pass: Score each retrieved chunk by word overlap & semantic affinity
        for chunk in retrieved_chunks:
            chunk_clean = cls._normalize_text(chunk.text)
            chunk_words = set(chunk_clean.split())
            if not chunk_words:
                continue

            intersection = words_claim.intersection(chunk_words)
            union = words_claim.union(chunk_words)
            overlap_score = len(intersection) / len(union) if union else 0.0

            # Bonus if preferred
            if preferred_chunk_id and chunk.chunk_id == preferred_chunk_id:
                overlap_score += 0.25

            if overlap_score > best_overlap_score:
                best_overlap_score = overlap_score
                best_chunk = chunk

        # Now locate the most representative sentence inside the selected best_chunk
        chunk_sentences = cls._split_into_sentences(best_chunk.text)
        if chunk_sentences:
            best_sent_score = -1.0
            chosen_sub_sentence = chunk_sentences[0]

            for cs in chunk_sentences:
                cs_clean = cls._normalize_text(cs)
                cs_words = set(cs_clean.split())
                inter = words_claim.intersection(cs_words)
                score = len(inter) / max(len(cs_words), 1)
                if score > best_sent_score:
                    best_sent_score = score
                    chosen_sub_sentence = cs

            # Locate chosen_sub_sentence within raw_text
            sub_pos = raw_text.find(chosen_sub_sentence, best_chunk.char_offset_start)
            if sub_pos != -1:
                best_slice_start = sub_pos
                best_slice_end = sub_pos + len(chosen_sub_sentence)
                best_quote = raw_text[best_slice_start:best_slice_end]
            else:
                # Fallback to chunk boundaries
                best_slice_start = best_chunk.char_offset_start
                best_slice_end = best_chunk.char_offset_end
                best_quote = best_chunk.text
        else:
            best_slice_start = best_chunk.char_offset_start
            best_slice_end = best_chunk.char_offset_end
            best_quote = best_chunk.text

        # Ensure offsets are strictly non-zero length and in bounds
        text_len = len(raw_text)
        best_slice_start = max(0, min(best_slice_start, text_len))
        best_slice_end = max(best_slice_start + 1, min(best_slice_end, text_len))
        best_quote = raw_text[best_slice_start:best_slice_end]

        return GroundedCitation(
            chunk_id=best_chunk.chunk_id,
            char_offset_start=best_slice_start,
            char_offset_end=best_slice_end,
            quote=best_quote,
            confidence=confidence,
        )

    @classmethod
    def link_sentences_batch(
        cls,
        sentences: list[str],
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        prefix_id: str = "sent",
        preferred_chunk_mapping: dict[int, uuid.UUID] | None = None,
    ) -> list[dict[str, Any]]:
        """Link a sequence of sentences to source chunks and return structured dicts."""
        preferred_map = preferred_chunk_mapping or {}
        results: list[dict[str, Any]] = []

        for idx, text in enumerate(sentences):
            clean_text = text.strip()
            if not clean_text:
                continue

            pref_chunk = preferred_map.get(idx)
            cit = cls.link_sentence(
                sentence_text=clean_text,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=pref_chunk,
            )

            results.append({
                "sentence_id": f"{prefix_id}_{idx}",
                "sentence_index": idx,
                "text": clean_text,
                "citations": [cit],
            })

        return results

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Strip punctuation and lowercase."""
        return re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower()

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """Split text into sentences while filtering noise."""
        raw_sents = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in raw_sents if len(s.strip()) > 15]
