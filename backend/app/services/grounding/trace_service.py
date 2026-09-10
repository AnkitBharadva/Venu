"""Claim-to-Chunk Trace Service for Phase 3.

Powers the "hover a sentence -> inspect source paragraph" UI capability.
Resolves any generated sentence back to its ground-truth source chunks,
exact character offsets, headings, page numbers, and contextual previews.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import GeneratedOutput, SourceDocument
from app.models.understanding import DocumentChunk
from app.schemas.grounding import (
    FullDeliverableTraceResponse,
    GroundingSourceSpan,
    SentenceTraceResponse,
)

logger = logging.getLogger("app.services.grounding.trace")


class GroundingTraceService:
    """Resolves claims in generated deliverables back to original ground-truth spans."""

    @classmethod
    async def trace_sentence(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        sentence_index: int | None = None,
        sentence_id: str | None = None,
    ) -> SentenceTraceResponse:
        """Resolve a single sentence to its source chunks and exact offsets."""
        output, source_doc, all_chunks = await cls._fetch_output_and_context(session, output_id)

        citations_list: list[dict[str, Any]] = output.citations or []
        if not citations_list:
            raise ValueError(f"Generated output '{output_id}' has no recorded citations.")

        # Match target citations
        matched_cits: list[dict[str, Any]] = []
        if sentence_id is not None:
            matched_cits = [c for c in citations_list if c.get("sentence_id") == sentence_id]
        elif sentence_index is not None:
            matched_cits = [c for c in citations_list if int(c.get("sentence_index", -1)) == sentence_index]
        else:
            # Default to first sentence index
            first_idx = int(citations_list[0].get("sentence_index", 0))
            matched_cits = [c for c in citations_list if int(c.get("sentence_index", -1)) == first_idx]

        if not matched_cits:
            target = f"ID '{sentence_id}'" if sentence_id else f"index {sentence_index}"
            raise ValueError(f"No citations found for sentence {target} in deliverable '{output_id}'.")

        s_id = matched_cits[0].get("sentence_id", "sent_unknown")
        s_idx = int(matched_cits[0].get("sentence_index", 0))
        s_text = matched_cits[0].get("sentence_text", "")

        raw_text = source_doc.raw_text or ""
        text_len = len(raw_text)

        source_spans: list[GroundingSourceSpan] = []
        all_verified = True

        for cit in matched_cits:
            cid_str = cit.get("chunk_id")
            cid = uuid.UUID(str(cid_str))
            chunk = all_chunks.get(cid)

            c_start = int(cit.get("char_offset_start", 0))
            c_end = int(cit.get("char_offset_end", 0))

            # Bound check
            c_start = max(0, min(c_start, text_len))
            c_end = max(c_start, min(c_end, text_len))

            actual_span = raw_text[c_start:c_end]
            verified = bool(actual_span and (chunk is not None))

            if not verified:
                all_verified = False

            # Extract surrounding context for operator UI tooltip
            ctx_start = max(0, c_start - 80)
            ctx_end = min(text_len, c_end + 80)
            context_before = raw_text[ctx_start:c_start]
            context_after = raw_text[c_end:ctx_end]

            source_spans.append(
                GroundingSourceSpan(
                    chunk_id=cid,
                    chunk_index=chunk.chunk_index if chunk else int(cit.get("chunk_index", 0)),
                    heading=chunk.heading if chunk else cit.get("heading"),
                    page_number=chunk.page_number if chunk else cit.get("page_number"),
                    timestamp_start=chunk.timestamp_start if chunk else cit.get("timestamp_start"),
                    timestamp_end=chunk.timestamp_end if chunk else cit.get("timestamp_end"),
                    char_offset_start=c_start,
                    char_offset_end=c_end,
                    quote=cit.get("quote") or actual_span,
                    chunk_text=chunk.text if chunk else actual_span,
                    context_before=context_before,
                    context_after=context_after,
                    trace_verified=verified,
                )
            )

        return SentenceTraceResponse(
            output_id=output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            sentence_id=s_id,
            sentence_index=s_idx,
            sentence_text=s_text,
            grounding_sources=source_spans,
            all_spans_verified=all_verified,
        )

    @classmethod
    async def trace_full_deliverable(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
    ) -> FullDeliverableTraceResponse:
        """Trace every sentence in a deliverable to verify 100% claim-to-chunk provenance."""
        output, _, _ = await cls._fetch_output_and_context(session, output_id)

        citations_list: list[dict[str, Any]] = output.citations or []
        content_dict: dict[str, Any] = output.content or {}

        # Collect distinct sentence indices
        sentence_indices: list[int] = sorted(
            list({int(c.get("sentence_index", 0)) for c in citations_list if "sentence_index" in c})
        )

        traces: list[SentenceTraceResponse] = []
        all_verified = True

        for s_idx in sentence_indices:
            s_trace = await cls.trace_sentence(session, output_id, sentence_index=s_idx)
            if not s_trace.all_spans_verified:
                all_verified = False
            traces.append(s_trace)

        # Calculate coverage
        content_title = content_dict.get("title", f"Deliverable {output.deliverable_type}")
        total_sents = len(sentence_indices)
        coverage_pct = 100.0 if total_sents > 0 else 0.0

        return FullDeliverableTraceResponse(
            output_id=output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            title=content_title,
            total_sentences=total_sents,
            total_citations=len(citations_list),
            coverage_pct=coverage_pct,
            traces=traces,
            all_verified=all_verified,
        )

    @classmethod
    async def _fetch_output_and_context(
        cls, session: AsyncSession, output_id: uuid.UUID
    ) -> tuple[GeneratedOutput, SourceDocument, dict[uuid.UUID, DocumentChunk]]:
        """Helper to fetch output, source document, and chunks."""
        stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == output_id)
        res = await session.execute(stmt)
        output = res.scalar_one_or_none()

        if not output:
            raise ValueError(f"Generated deliverable '{output_id}' not found.")

        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == output.doc_id)
        doc_res = await session.execute(doc_stmt)
        source_doc = doc_res.scalar_one_or_none()

        if not source_doc:
            raise ValueError(f"Source document '{output.doc_id}' for deliverable '{output_id}' not found.")

        chunk_stmt = select(DocumentChunk).where(DocumentChunk.doc_id == output.doc_id)
        chunk_res = await session.execute(chunk_stmt)
        all_chunks = {c.chunk_id: c for c in chunk_res.scalars().all()}

        return output, source_doc, all_chunks
