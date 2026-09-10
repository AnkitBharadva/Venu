"""Output Deliverable Service for Phase 3.

Manages the registration, contract validation, and persistence of grounded
deliverables (executive summaries, advisories, LinkedIn posts, etc.).
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.models.audit_log import GeneratedOutput, SourceDocument
from app.models.understanding import DocumentChunk
from app.schemas.grounding import CreateDeliverableRequest, DeliverableResponse
from app.services.grounding.contract_enforcer import GroundingContractEnforcer
from app.services.security.output_encryption import save_encrypted_output

logger = logging.getLogger("app.services.grounding.output")


class GroundingOutputService:
    """Orchestrates deliverable persistence with hard claim-citation enforcement."""

    @classmethod
    async def create_grounded_deliverable(
        cls,
        session: AsyncSession,
        request: CreateDeliverableRequest,
        actor: str = "operator",
    ) -> DeliverableResponse:
        """Validate deliverable citations, persist to generated_outputs, and log audit event."""
        # 1. Fetch source document
        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == request.doc_id)
        doc_res = await session.execute(doc_stmt)
        source_doc = doc_res.scalar_one_or_none()
        if not source_doc:
            raise ValueError(f"Source document '{request.doc_id}' not found.")

        # 2. Fetch all valid document chunks for this doc
        chunk_stmt = select(DocumentChunk).where(DocumentChunk.doc_id == request.doc_id)
        chunk_res = await session.execute(chunk_stmt)
        valid_chunks = {c.chunk_id: c for c in chunk_res.scalars().all()}
        if not valid_chunks:
            raise ValueError(
                f"No processed chunks found for document '{request.doc_id}'. "
                f"Document must be ingested and chunked before creating deliverables."
            )

        # 3. Hard Contract Enforcement
        # Throws UncitedClaimViolationError, InvalidCitationChunkError, or GroundingQuoteMismatchError
        raw_text = source_doc.raw_text or ""
        flat_citations = GroundingContractEnforcer.validate_deliverable(
            doc_id=request.doc_id,
            raw_text=raw_text,
            valid_chunks=valid_chunks,
            content=request.content,
        )

        # Count total sentences across blocks
        total_sentences = sum(len(b.sentences) for b in request.content.blocks)

        # 4. Encrypt deliverable payload at rest (AES-256-GCM)
        output_id = uuid.uuid4()
        format_meta = dict(request.format_metadata)
        format_meta["review_status"] = "pending"
        format_meta["export_locked"] = True
        content_dict = request.content.model_dump(mode="json")
        encrypted_path = save_encrypted_output(
            output_id=output_id,
            doc_id=request.doc_id,
            deliverable_type=request.deliverable_type,
            status="draft",
            content=content_dict,
            citations=flat_citations,
            format_metadata=format_meta,
            reviewer_id=request.reviewer_id,
        )
        format_meta["encrypted_file_path"] = encrypted_path

        # 5. Persist GeneratedOutput entity (starts in status 'draft' per Phase 6 mandate)
        new_output = GeneratedOutput(
            output_id=output_id,
            doc_id=request.doc_id,
            deliverable_type=request.deliverable_type,
            status="draft",
            content=content_dict,
            citations=flat_citations,
            format_metadata=format_meta,
            encrypted_file_path=encrypted_path,
            reviewer_id=request.reviewer_id,
        )
        session.add(new_output)

        # 6. Cryptographic Append-Only Audit Entry
        audit_details = {
            "deliverable_type": request.deliverable_type,
            "title": request.content.title,
            "total_sentences": total_sentences,
            "total_citations": len(flat_citations),
            "contract_verified": True,
        }
        await record_audit_event(
            session=session,
            actor=actor,
            action="create_grounded_deliverable",
            doc_id=request.doc_id,
            output_id=output_id,
            source_hash=source_doc.checksum,
            details=audit_details,
        )
        await session.commit()
        await session.refresh(new_output)

        logger.info(
            "Created verified grounded deliverable %s (%s) for doc %s with %d sentences and %d citations",
            output_id,
            request.deliverable_type,
            request.doc_id,
            total_sentences,
            len(flat_citations),
        )

        return cls._to_response(new_output, total_sentences, len(flat_citations))

    @classmethod
    async def get_deliverable(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
    ) -> DeliverableResponse:
        """Fetch a generated deliverable by output_id."""
        stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == output_id)
        res = await session.execute(stmt)
        output = res.scalar_one_or_none()
        if not output:
            raise ValueError(f"Generated deliverable '{output_id}' not found.")

        content = output.content or {}
        blocks = content.get("blocks", [])
        total_sentences = sum(len(b.get("sentences", [])) for b in blocks)
        citations_list = output.citations or []

        return cls._to_response(output, total_sentences, len(citations_list))

    @classmethod
    async def get_deliverables_by_doc(
        cls,
        session: AsyncSession,
        doc_id: uuid.UUID,
    ) -> list[DeliverableResponse]:
        """Fetch all deliverables associated with a given doc_id."""
        stmt = (
            select(GeneratedOutput)
            .where(GeneratedOutput.doc_id == doc_id)
            .order_by(GeneratedOutput.created_at.desc())
        )
        res = await session.execute(stmt)
        outputs = res.scalars().all()

        results: list[DeliverableResponse] = []
        for o in outputs:
            content = o.content or {}
            blocks = content.get("blocks", [])
            total_sentences = sum(len(b.get("sentences", [])) for b in blocks)
            citations_list = o.citations or []
            results.append(cls._to_response(o, total_sentences, len(citations_list)))
        return results

    @staticmethod
    def _to_response(
        output: GeneratedOutput, total_sentences: int, total_citations: int
    ) -> DeliverableResponse:
        """Format a GeneratedOutput model into DeliverableResponse schema."""
        return DeliverableResponse(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata or {},
            encrypted_file_path=getattr(output, "encrypted_file_path", None),
            reviewer_id=output.reviewer_id,
            reviewer_notes=output.reviewer_notes,
            approved_at=output.approved_at,
            total_sentences=total_sentences,
            total_citations=total_citations,
            contract_verified=True,
        )
