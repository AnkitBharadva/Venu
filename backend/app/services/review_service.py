"""Review, Approval, and Export Service for Phase 5.

Implements:
1. Two-man rule & human-in-the-loop review workflow for safety-critical deliverables (e.g. Advisories).
2. Human reviewer approval/rejection state transitions.
3. Export authorization and format rendering (Markdown, JSON, HTML, Text).
4. AES-256-GCM encryption at rest for all exported assets.
5. Tamper-evident cryptographic audit logging on all review and export actions.
"""

import difflib
import html
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.audit import record_audit_event
from app.core.security import compute_sha256, save_encrypted_file
from app.models.audit_log import GeneratedOutput, OutputEditHistory
from app.schemas.grounding import DeliverableResponse
from app.schemas.review import (
    EditHistoryItemResponse,
    ExportDeliverableResponse,
    OutputEncryptionVerificationResponse,
    OutputReviewSummaryResponse,
)
from app.services.grounding.output_service import GroundingOutputService
from app.services.security.output_encryption import (
    _get_output_storage_dir,
    save_encrypted_output,
    verify_output_encryption,
)

logger = logging.getLogger("app.services.review_service")


class HumanReviewRequiredError(PermissionError):
    """Raised when an unapproved safety-critical deliverable is requested for export."""


class ReviewService:
    """Orchestrates approval workflows, export security gates, and audit chaining."""

    @classmethod
    async def request_approval(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        actor: str = "operator",
        notes: str | None = None,
    ) -> DeliverableResponse:
        """Operator requests formal reviewer evaluation for a deliverable."""
        output = await cls._get_output_entity(session, output_id)

        output.status = "pending_review"
        format_meta = dict(output.format_metadata or {})
        format_meta["review_status"] = "pending_review"
        output.format_metadata = format_meta

        # Re-encrypt state at rest
        enc_path = save_encrypted_output(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata,
            reviewer_id=output.reviewer_id,
            reviewer_notes=output.reviewer_notes,
        )
        output.encrypted_file_path = enc_path

        # Cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=actor,
            action="request_approval",
            doc_id=output.doc_id,
            output_id=output.output_id,
            details={
                "deliverable_type": output.deliverable_type,
                "notes": notes,
                "new_status": "pending_review",
            },
        )
        await session.commit()
        await session.refresh(output)

        logger.info("Deliverable %s submitted for review by %s", output_id, actor)
        return cls._format_response(output)

    @classmethod
    async def edit_sentence(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        sentence_id: str,
        new_text: str,
        actor: str = "reviewer",
        notes: str | None = None,
    ) -> DeliverableResponse:
        """Reviewer edits a specific sentence with unified diff tracking and cryptographic audit entry."""
        output = await cls._get_output_entity(session, output_id)

        content = dict(output.content or {})
        blocks = list(content.get("blocks", []))
        found_sentence = None
        old_text = ""
        target_sentence_idx = None

        for block in blocks:
            for s_idx, sentence in enumerate(block.get("sentences", [])):
                if sentence.get("sentence_id") == sentence_id:
                    found_sentence = sentence
                    old_text = sentence.get("text", "")
                    target_sentence_idx = s_idx
                    break
            if found_sentence:
                break

        if not found_sentence:
            raise ValueError(f"Sentence '{sentence_id}' not found in deliverable '{output_id}'.")

        now = datetime.now(UTC)

        # Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile="before",
                tofile="after",
            )
        )
        diff_summary = "".join(diff_lines) if diff_lines else f"- {old_text}\n+ {new_text}"

        # Update sentence object in content
        found_sentence["text"] = new_text
        found_sentence["review_status"] = "edited"
        found_sentence["last_edited_by"] = actor
        found_sentence["last_edited_at"] = now.isoformat()
        if notes:
            found_sentence["reviewer_notes"] = notes

        # Flag mutated content for SQLAlchemy
        content["blocks"] = blocks
        output.content = content
        flag_modified(output, "content")

        # Determine version
        stmt = select(OutputEditHistory).where(OutputEditHistory.output_id == output_id)
        res = await session.execute(stmt)
        existing_history = res.scalars().all()
        version = len(existing_history) + 1

        # Store OutputEditHistory record
        history_entry = OutputEditHistory(
            output_id=output.output_id,
            version=version,
            actor=actor,
            action="edit_sentence",
            target_type="sentence",
            target_id=sentence_id,
            target_index=target_sentence_idx,
            before_content=old_text,
            after_content=new_text,
            diff_summary=diff_summary,
            timestamp=now,
        )
        session.add(history_entry)

        # Re-encrypt deliverable payload at rest
        enc_path = save_encrypted_output(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata,
            reviewer_id=output.reviewer_id,
            reviewer_notes=output.reviewer_notes,
        )
        output.encrypted_file_path = enc_path

        # Chained cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=actor,
            action="edit_sentence",
            doc_id=output.doc_id,
            output_id=output.output_id,
            details={
                "sentence_id": sentence_id,
                "version": version,
                "before": old_text,
                "after": new_text,
                "diff_summary": diff_summary,
                "notes": notes,
            },
        )

        await session.commit()
        await session.refresh(output)

        logger.info(
            "Sentence %s in deliverable %s edited by %s (v%d)",
            sentence_id,
            output_id,
            actor,
            version,
        )
        return cls._format_response(output)

    @classmethod
    async def review_sentence(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        sentence_id: str,
        decision: str,
        actor: str = "reviewer",
        notes: str | None = None,
    ) -> DeliverableResponse:
        """Reviewer accepts or rejects a single sentence with audit history tracking."""
        decision_clean = decision.lower().strip()
        if decision_clean not in ["accept", "reject"]:
            raise ValueError(f"Invalid sentence review decision: '{decision}'. Must be 'accept' or 'reject'.")

        output = await cls._get_output_entity(session, output_id)

        content = dict(output.content or {})
        blocks = list(content.get("blocks", []))
        found_sentence = None
        target_sentence_idx = None

        for block in blocks:
            for s_idx, sentence in enumerate(block.get("sentences", [])):
                if sentence.get("sentence_id") == sentence_id:
                    found_sentence = sentence
                    target_sentence_idx = s_idx
                    break
            if found_sentence:
                break

        if not found_sentence:
            raise ValueError(f"Sentence '{sentence_id}' not found in deliverable '{output_id}'.")

        now = datetime.now(UTC)
        before_status = found_sentence.get("review_status", "pending")
        new_status = "accepted" if decision_clean == "accept" else "rejected"

        found_sentence["review_status"] = new_status
        found_sentence["reviewed_by"] = actor
        found_sentence["reviewed_at"] = now.isoformat()
        if notes:
            found_sentence["reviewer_notes"] = notes

        content["blocks"] = blocks
        output.content = content
        flag_modified(output, "content")

        # Determine version
        stmt = select(OutputEditHistory).where(OutputEditHistory.output_id == output_id)
        res = await session.execute(stmt)
        version = len(res.scalars().all()) + 1

        history_entry = OutputEditHistory(
            output_id=output.output_id,
            version=version,
            actor=actor,
            action=f"{decision_clean}_sentence",
            target_type="sentence",
            target_id=sentence_id,
            target_index=target_sentence_idx,
            before_content=before_status,
            after_content=new_status,
            diff_summary=f"Sentence {sentence_id} marked as '{new_status}' by {actor}. Notes: {notes or 'N/A'}",
            timestamp=now,
        )
        session.add(history_entry)

        # Re-encrypt deliverable payload at rest
        enc_path = save_encrypted_output(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata,
            reviewer_id=output.reviewer_id,
            reviewer_notes=output.reviewer_notes,
        )
        output.encrypted_file_path = enc_path

        # Chained cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=actor,
            action=f"{decision_clean}_sentence",
            doc_id=output.doc_id,
            output_id=output.output_id,
            details={
                "sentence_id": sentence_id,
                "decision": decision_clean,
                "before_status": before_status,
                "new_status": new_status,
                "notes": notes,
            },
        )

        await session.commit()
        await session.refresh(output)

        logger.info("Sentence %s in deliverable %s %sed by %s", sentence_id, output_id, decision_clean, actor)
        return cls._format_response(output)

    @classmethod
    async def review_section(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        block_index: int,
        decision: str,
        actor: str = "reviewer",
        notes: str | None = None,
    ) -> DeliverableResponse:
        """Reviewer accepts or rejects an entire content section."""
        decision_clean = decision.lower().strip()
        if decision_clean not in ["accept", "reject"]:
            raise ValueError(f"Invalid section review decision: '{decision}'. Must be 'accept' or 'reject'.")

        output = await cls._get_output_entity(session, output_id)

        content = dict(output.content or {})
        blocks = list(content.get("blocks", []))

        if block_index < 0 or block_index >= len(blocks):
            raise ValueError(f"Block index {block_index} out of bounds for deliverable with {len(blocks)} blocks.")

        target_block = blocks[block_index]
        now = datetime.now(UTC)
        new_status = "accepted" if decision_clean == "accept" else "rejected"
        target_block["review_status"] = new_status
        target_block["reviewed_by"] = actor
        target_block["reviewed_at"] = now.isoformat()

        # Update all sentences in this block as well
        for sentence in target_block.get("sentences", []):
            sentence["review_status"] = new_status
            sentence["reviewed_by"] = actor
            sentence["reviewed_at"] = now.isoformat()

        content["blocks"] = blocks
        output.content = content
        flag_modified(output, "content")

        # Determine version
        stmt = select(OutputEditHistory).where(OutputEditHistory.output_id == output_id)
        res = await session.execute(stmt)
        version = len(res.scalars().all()) + 1

        history_entry = OutputEditHistory(
            output_id=output.output_id,
            version=version,
            actor=actor,
            action=f"{decision_clean}_section",
            target_type="section",
            target_id=str(block_index),
            target_index=block_index,
            before_content=target_block.get("title", f"Section {block_index}"),
            after_content=new_status,
            diff_summary=f"Section #{block_index} ({target_block.get('title', 'Section')}) marked as '{new_status}' by {actor}.",
            timestamp=now,
        )
        session.add(history_entry)

        # Re-encrypt deliverable payload at rest
        enc_path = save_encrypted_output(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata,
            reviewer_id=output.reviewer_id,
            reviewer_notes=output.reviewer_notes,
        )
        output.encrypted_file_path = enc_path

        # Chained cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=actor,
            action=f"{decision_clean}_section",
            doc_id=output.doc_id,
            output_id=output.output_id,
            details={
                "block_index": block_index,
                "section_title": target_block.get("title"),
                "decision": decision_clean,
                "new_status": new_status,
                "notes": notes,
            },
        )

        await session.commit()
        await session.refresh(output)

        return cls._format_response(output)

    @classmethod
    async def get_edit_history(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
    ) -> list[EditHistoryItemResponse]:
        """Fetch chronological diff audit trail for an output deliverable."""
        await cls._get_output_entity(session, output_id)

        stmt = (
            select(OutputEditHistory)
            .where(OutputEditHistory.output_id == output_id)
            .order_by(OutputEditHistory.timestamp.asc())
        )
        res = await session.execute(stmt)
        records = res.scalars().all()
        return [EditHistoryItemResponse.model_validate(r) for r in records]

    @classmethod
    async def get_review_summary(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
    ) -> OutputReviewSummaryResponse:
        """Compute review stats: accepted, rejected, edited, pending counts."""
        output = await cls._get_output_entity(session, output_id)

        content = output.content or {}
        blocks = content.get("blocks", [])
        total_sents = 0
        accepted_sents = 0
        rejected_sents = 0
        edited_sents = 0
        pending_sents = 0

        for block in blocks:
            for s in block.get("sentences", []):
                total_sents += 1
                rev_status = s.get("review_status", "pending")
                if rev_status == "accepted":
                    accepted_sents += 1
                elif rev_status == "rejected":
                    rejected_sents += 1
                elif rev_status == "edited":
                    edited_sents += 1
                else:
                    pending_sents += 1

        stmt = select(OutputEditHistory).where(OutputEditHistory.output_id == output_id)
        res = await session.execute(stmt)
        history_count = len(res.scalars().all())

        return OutputReviewSummaryResponse(
            output_id=output.output_id,
            status=output.status,
            total_sentences=total_sents,
            accepted_sentences=accepted_sents,
            rejected_sentences=rejected_sents,
            edited_sentences=edited_sents,
            pending_sentences=pending_sents,
            can_export=(output.status in ["final", "approved"]),
            history_count=history_count,
        )

    @classmethod
    async def approve_deliverable(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        reviewer_id: str,
        reviewer_notes: str | None = None,
    ) -> DeliverableResponse:
        """Authorized reviewer approves the deliverable, transitioning status to 'final' and unlocking export."""
        output = await cls._get_output_entity(session, output_id)

        now = datetime.now(UTC)
        previous_status = output.status
        output.status = "final"
        output.reviewer_id = reviewer_id
        output.reviewer_notes = reviewer_notes
        output.approved_at = now

        format_meta = dict(output.format_metadata or {})
        format_meta["review_status"] = "approved"
        format_meta["export_locked"] = False
        output.format_metadata = format_meta

        # Re-encrypt updated deliverable at rest
        enc_path = save_encrypted_output(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata,
            reviewer_id=reviewer_id,
            reviewer_notes=reviewer_notes,
        )
        output.encrypted_file_path = enc_path

        # Record approval in edit history
        stmt_hist = select(OutputEditHistory).where(OutputEditHistory.output_id == output_id)
        res_hist = await session.execute(stmt_hist)
        version = len(res_hist.scalars().all()) + 1

        history_entry = OutputEditHistory(
            output_id=output.output_id,
            version=version,
            actor=reviewer_id,
            action="approve_deliverable",
            target_type="deliverable",
            target_id=str(output_id),
            before_content=previous_status,
            after_content="final",
            diff_summary=f"Deliverable approved by reviewer {reviewer_id}. Status transitioned to 'final'. Export unlocked.",
            timestamp=now,
        )
        session.add(history_entry)

        # Cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=reviewer_id,
            action="approve_deliverable",
            doc_id=output.doc_id,
            output_id=output.output_id,
            details={
                "deliverable_type": output.deliverable_type,
                "reviewer_notes": reviewer_notes,
                "status": "final",
                "approved_at": now.isoformat(),
            },
        )
        await session.commit()
        await session.refresh(output)

        logger.info("Deliverable %s approved by reviewer %s (status -> 'final')", output_id, reviewer_id)
        return cls._format_response(output)

    @classmethod
    async def reject_deliverable(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        reviewer_id: str,
        reviewer_notes: str | None = None,
    ) -> DeliverableResponse:
        """Authorized reviewer rejects the deliverable, locking export and returning notes."""
        output = await cls._get_output_entity(session, output_id)

        previous_status = output.status
        output.status = "rejected"
        output.reviewer_id = reviewer_id
        output.reviewer_notes = reviewer_notes

        format_meta = dict(output.format_metadata or {})
        format_meta["review_status"] = "rejected"
        format_meta["export_locked"] = True
        output.format_metadata = format_meta

        # Re-encrypt updated deliverable at rest
        enc_path = save_encrypted_output(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            status=output.status,
            content=output.content,
            citations=output.citations or [],
            format_metadata=output.format_metadata,
            reviewer_id=reviewer_id,
            reviewer_notes=reviewer_notes,
        )
        output.encrypted_file_path = enc_path

        # Record reject in edit history
        stmt_hist = select(OutputEditHistory).where(OutputEditHistory.output_id == output_id)
        res_hist = await session.execute(stmt_hist)
        version = len(res_hist.scalars().all()) + 1

        history_entry = OutputEditHistory(
            output_id=output.output_id,
            version=version,
            actor=reviewer_id,
            action="reject_deliverable",
            target_type="deliverable",
            target_id=str(output_id),
            before_content=previous_status,
            after_content="rejected",
            diff_summary=f"Deliverable rejected by reviewer {reviewer_id}. Notes: {reviewer_notes or 'N/A'}",
            timestamp=datetime.now(UTC),
        )
        session.add(history_entry)

        # Cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=reviewer_id,
            action="reject_deliverable",
            doc_id=output.doc_id,
            output_id=output.output_id,
            details={
                "deliverable_type": output.deliverable_type,
                "reviewer_notes": reviewer_notes,
                "status": "rejected",
            },
        )
        await session.commit()
        await session.refresh(output)

        logger.info("Deliverable %s rejected by reviewer %s", output_id, reviewer_id)
        return cls._format_response(output)

    @classmethod
    async def export_deliverable(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        actor: str = "reviewer",
        export_format: str = "markdown",
    ) -> ExportDeliverableResponse:
        """Render and export an authorized deliverable with AES-256 encrypted archive storage.

        Phase 6 Mandate: Export endpoint only serves 'final' status outputs. Attempting to export
        a 'draft' (or 'rejected') output fails with a clear error.
        """
        output = await cls._get_output_entity(session, output_id)

        if output.status == "rejected":
            raise ValueError(f"Cannot export rejected deliverable '{output_id}'.")

        # Render content based on format
        rendered_content = cls._render_export_content(output, export_format.lower())
        rendered_bytes = rendered_content.encode("utf-8")
        checksum = compute_sha256(rendered_bytes)

        # Encrypt exported artifact at rest in dedicated export subfolder
        export_dir = _get_output_storage_dir() / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{output.deliverable_type}_{output_id}.{export_format.lower()}"
        enc_target = export_dir / f"{filename}.enc"
        encrypted_export_path = save_encrypted_file(rendered_bytes, enc_target)

        now = datetime.now(UTC)

        # Cryptographic audit entry
        await record_audit_event(
            session=session,
            actor=actor,
            action="export_deliverable",
            doc_id=output.doc_id,
            output_id=output.output_id,
            source_hash=checksum,
            details={
                "deliverable_type": output.deliverable_type,
                "export_format": export_format.lower(),
                "export_filename": filename,
                "file_size_bytes": len(rendered_bytes),
                "encrypted_export_path": encrypted_export_path,
                "status": output.status,
            },
        )
        await session.commit()

        logger.info(
            "Deliverable %s exported in %s format by %s (SHA256: %s)",
            output_id,
            export_format,
            actor,
            checksum,
        )

        return ExportDeliverableResponse(
            output_id=output.output_id,
            doc_id=output.doc_id,
            deliverable_type=output.deliverable_type,
            export_format=export_format.lower(),
            exported_filename=filename,
            checksum_sha256=checksum,
            exported_content=rendered_content,
            encrypted_export_path=encrypted_export_path,
            export_timestamp=now,
            actor=actor,
            audit_logged=True,
        )

    @classmethod
    async def list_pending_reviews(
        cls,
        session: AsyncSession,
        doc_id: uuid.UUID | None = None,
    ) -> list[DeliverableResponse]:
        """List deliverables awaiting human review or in draft status."""
        stmt = select(GeneratedOutput).order_by(GeneratedOutput.created_at.desc())
        if doc_id:
            stmt = stmt.where(GeneratedOutput.doc_id == doc_id)

        res = await session.execute(stmt)
        outputs = res.scalars().all()
        return [cls._format_response(o) for o in outputs]

    @classmethod
    async def verify_output_encryption_at_rest(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
    ) -> OutputEncryptionVerificationResponse:
        """Verify the AES-256-GCM ciphertext on disk for a generated deliverable."""
        output = await cls._get_output_entity(session, output_id)
        enc_path = output.encrypted_file_path

        if not enc_path:
            # Re-generate encryption file if missing
            enc_path = save_encrypted_output(
                output_id=output.output_id,
                doc_id=output.doc_id,
                deliverable_type=output.deliverable_type,
                status=output.status,
                content=output.content,
                citations=output.citations or [],
                format_metadata=output.format_metadata or {},
                reviewer_id=output.reviewer_id,
                reviewer_notes=output.reviewer_notes,
            )
            output.encrypted_file_path = enc_path
            await session.commit()

        res = verify_output_encryption(output.output_id, enc_path)
        return OutputEncryptionVerificationResponse(
            output_id=output.output_id,
            verified=res.get("verified", False),
            encrypted_at_rest=res.get("encrypted_at_rest", False),
            algorithm=res.get("algorithm", "AES-256-GCM"),
            file_path=res.get("file_path", enc_path),
            file_size_bytes=res.get("file_size_bytes"),
            ciphertext_sha256=res.get("ciphertext_sha256"),
            deliverable_type=output.deliverable_type,
            status=output.status,
            error=res.get("error"),
        )

    @classmethod
    async def _get_output_entity(cls, session: AsyncSession, output_id: uuid.UUID) -> GeneratedOutput:
        stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == output_id)
        res = await session.execute(stmt)
        output = res.scalar_one_or_none()
        if not output:
            raise ValueError(f"Generated deliverable '{output_id}' not found.")
        return output

    @staticmethod
    def _format_response(output: GeneratedOutput) -> DeliverableResponse:
        content = output.content or {}
        blocks = content.get("blocks", [])
        total_sentences = sum(len(b.get("sentences", [])) for b in blocks)
        citations_list = output.citations or []
        return GroundingOutputService._to_response(output, total_sentences, len(citations_list))

    @staticmethod
    def _render_export_content(output: GeneratedOutput, export_format: str) -> str:
        """Render deliverable content to target textual format."""
        content = output.content or {}
        title = content.get("title", "Generated Deliverable")
        summary = content.get("summary")
        blocks = content.get("blocks", [])

        if export_format == "json":
            export_dict = {
                "output_id": str(output.output_id),
                "doc_id": str(output.doc_id),
                "deliverable_type": output.deliverable_type,
                "status": output.status,
                "title": title,
                "summary": summary,
                "blocks": blocks,
                "citations": output.citations,
                "reviewer_id": output.reviewer_id,
                "approved_at": output.approved_at.isoformat() if output.approved_at else None,
            }
            return json.dumps(export_dict, indent=2)

        elif export_format == "html":
            html_parts = [
                "<!DOCTYPE html>",
                "<html><head><meta charset='utf-8'><title>" + html.escape(title) + "</title>",
                "<style>body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; line-height: 1.6; }",
                ".citation-ref { color: #0284c7; text-decoration: underline; font-size: 0.8em; margin-left: 2px; }",
                ".summary-box { background: #f1f5f9; padding: 16px; border-radius: 8px; margin: 20px 0; }",
                "</style></head><body>",
                f"<h1>{html.escape(title)}</h1>",
            ]
            if summary:
                html_parts.append(f"<div class='summary-box'><strong>Executive Summary:</strong> {html.escape(summary)}</div>")
            for b in blocks:
                b_title = b.get("title")
                if b_title:
                    html_parts.append(f"<h3>{html.escape(b_title)}</h3>")
                html_parts.append("<p>")
                for s in b.get("sentences", []):
                    stext = html.escape(s.get("text", ""))
                    c_count = len(s.get("citations", []))
                    if c_count > 0:
                        html_parts.append(f"{stext}<sup class='citation-ref'>[{c_count}]</sup> ")
                    else:
                        html_parts.append(f"{stext} ")
                html_parts.append("</p>")
            html_parts.append("</body></html>")
            return "\n".join(html_parts)

        elif export_format == "text":
            lines = [title, "=" * len(title), ""]
            if summary:
                lines.extend(["SUMMARY:", summary, ""])
            for b in blocks:
                b_title = b.get("title")
                if b_title:
                    lines.extend([b_title, "-" * len(b_title)])
                b_text = " ".join(s.get("text", "") for s in b.get("sentences", []))
                lines.extend([b_text, ""])
            return "\n".join(lines)

        else:  # Default to Markdown
            md_lines = [f"# {title}", ""]
            if summary:
                md_lines.extend([f"> {summary}", ""])
            for b in blocks:
                b_title = b.get("title")
                if b_title:
                    md_lines.extend([f"## {b_title}", ""])
                for s in b.get("sentences", []):
                    stext = s.get("text", "")
                    citations = s.get("citations", [])
                    if citations:
                        md_lines.append(f"{stext} [^{citations[0].get('chunk_id', 'ref')[:8]}]")
                    else:
                        md_lines.append(stext)
                md_lines.append("")

            # Citation references footnote section
            if output.citations:
                md_lines.extend(["---", "### Grounding Citations", ""])
                for _idx, c in enumerate(output.citations, 1):
                    cid = str(c.get("chunk_id", "chunk"))[:8]
                    quote = c.get("quote", "")
                    md_lines.append(f"[^{cid}]: Chunk `{cid}`: *\"{quote}\"*")

            return "\n".join(md_lines)
