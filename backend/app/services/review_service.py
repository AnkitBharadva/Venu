"""Review, Approval, and Export Service for Phase 5.

Implements:
1. Two-man rule & human-in-the-loop review workflow for safety-critical deliverables (e.g. Advisories).
2. Human reviewer approval/rejection state transitions.
3. Export authorization and format rendering (Markdown, JSON, HTML, Text).
4. AES-256-GCM encryption at rest for all exported assets.
5. Tamper-evident cryptographic audit logging on all review and export actions.
"""

import html
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.security import compute_sha256, save_encrypted_file
from app.models.audit_log import GeneratedOutput, SourceDocument
from app.schemas.grounding import DeliverableResponse
from app.schemas.review import ExportDeliverableResponse, OutputEncryptionVerificationResponse
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
    async def approve_deliverable(
        cls,
        session: AsyncSession,
        output_id: uuid.UUID,
        reviewer_id: str,
        reviewer_notes: str | None = None,
    ) -> DeliverableResponse:
        """Authorized reviewer approves the deliverable, unlocking export authorization."""
        output = await cls._get_output_entity(session, output_id)

        now = datetime.now(UTC)
        output.status = "approved"
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
                "status": "approved",
                "approved_at": now.isoformat(),
            },
        )
        await session.commit()
        await session.refresh(output)

        logger.info("Deliverable %s approved by reviewer %s", output_id, reviewer_id)
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
        """Render and export an authorized deliverable with AES-256 encrypted archive storage."""
        output = await cls._get_output_entity(session, output_id)

        # Gatekeeper: check whether deliverable requires human review
        format_meta = output.format_metadata or {}
        requires_review = (
            format_meta.get("requires_human_review", False)
            or output.deliverable_type == "advisory"
        )

        if requires_review and output.status != "approved":
            logger.warning(
                "Export blocked: Deliverable %s (%s) is in status '%s' but requires human review",
                output_id,
                output.deliverable_type,
                output.status,
            )
            raise HumanReviewRequiredError(
                f"Export blocked: Deliverable '{output_id}' of type '{output.deliverable_type}' "
                f"is safety-critical and requires explicit human reviewer approval before export. "
                f"Current status: '{output.status}'."
            )

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
                for idx, c in enumerate(output.citations, 1):
                    cid = str(c.get("chunk_id", "chunk"))[:8]
                    quote = c.get("quote", "")
                    md_lines.append(f"[^{cid}]: Chunk `{cid}`: *\"{quote}\"*")

            return "\n".join(md_lines)
