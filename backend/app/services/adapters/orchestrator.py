"""Multi-Select Output Generation Orchestrator for Phase 4.

Coordinates:
1. One-time hybrid context retrieval (Qdrant + FalkorDB)
2. Concurrent adapter execution for all selected deliverable formats
3. Hard claim-citation contract enforcement and persistence via GroundingOutputService
4. Cryptographic append-only audit trail logging
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import SourceDocument
from app.models.understanding import DocumentUnderstanding
from app.schemas.adapters import (
    GenerateDeliverablesRequest,
    MultiDeliverableResponse,
)
from app.schemas.grounding import (
    CreateDeliverableRequest,
    DeliverableResponse,
    GroundedContextResponse,
)
from app.services.adapters.base import AdapterOutput, BaseDeliverableAdapter
from app.services.adapters.registry import get_adapter_registry
from app.services.grounding.output_service import GroundingOutputService
from app.services.grounding.retrieval_service import GroundingRetrievalService

logger = logging.getLogger("app.services.adapters.orchestrator")


class AdapterOrchestrationService:
    """Orchestrates multi-select generation adapters against a shared grounded context."""

    @classmethod
    async def generate_deliverables(
        cls,
        session: AsyncSession,
        request: GenerateDeliverablesRequest,
    ) -> MultiDeliverableResponse:
        """Run all requested adapters concurrently against the source document's grounded context."""
        # 1. Fetch SourceDocument
        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == request.doc_id)
        doc_res = await session.execute(doc_stmt)
        source_doc = doc_res.scalar_one_or_none()
        if not source_doc:
            raise ValueError(f"Source document '{request.doc_id}' not found.")

        # 2. Fetch DocumentUnderstanding for topics & entities
        und_stmt = select(DocumentUnderstanding).where(DocumentUnderstanding.doc_id == request.doc_id)
        und_res = await session.execute(und_stmt)
        understanding = und_res.scalar_one_or_none()

        doc_summary = understanding.summary if understanding else None
        topics = understanding.topics if understanding else []
        entities = [e.get("name") for e in (understanding.key_entities or [])] if understanding else []

        # 3. Determine guiding query for hybrid retrieval
        query = request.query
        if not query:
            if topics:
                query = " ".join(topics[:4])
            elif understanding and understanding.objective:
                query = understanding.objective
            else:
                query = source_doc.original_filename.replace("_", " ").replace("-", " ")

        # 4. Fetch grounded context ONCE for all adapters
        grounded_context: GroundedContextResponse = await GroundingRetrievalService.retrieve_grounded_context(
            session=session,
            query=query,
            doc_id=request.doc_id,
            top_k=request.top_k_chunks,
            include_graph=True,
            alpha=0.7,
        )

        # 5. Resolve requested adapters from registry
        registry = get_adapter_registry()
        active_adapters: list[BaseDeliverableAdapter] = []
        for dtype in request.deliverable_types:
            adapter = registry.get_adapter(dtype)
            active_adapters.append(adapter)

        # 6. Execute adapters concurrently
        async def run_adapter(adapter: BaseDeliverableAdapter) -> tuple[BaseDeliverableAdapter, AdapterOutput]:
            out = await adapter.generate(
                source_doc_id=request.doc_id,
                retrieved_chunks=grounded_context.retrieved_chunks,
                raw_text=source_doc.raw_text or "",
                params=request.parameters,
                doc_summary=doc_summary,
                key_entities=entities,
            )
            return adapter, out

        tasks = [run_adapter(a) for a in active_adapters]
        generated_outputs: list[tuple[BaseDeliverableAdapter, AdapterOutput]] = await asyncio.gather(*tasks)

        # 7. Validate each deliverable against the hard contract and persist to DB
        deliverable_responses: list[DeliverableResponse] = []

        for adapter, adapter_out in generated_outputs:
            # Enforce metadata annotations (safety-critical review required)
            format_meta = dict(adapter_out.format_metadata)
            if adapter_out.requires_human_review:
                format_meta["requires_human_review"] = True
                format_meta["review_status"] = "pending_review"
                format_meta["export_locked"] = True

            create_req = CreateDeliverableRequest(
                doc_id=request.doc_id,
                deliverable_type=adapter.deliverable_type,
                content=adapter_out.content,
                format_metadata=format_meta,
            )

            # Persists to generated_outputs and logs cryptographic audit event
            saved_deliv = await GroundingOutputService.create_grounded_deliverable(
                session=session,
                request=create_req,
                actor=request.actor,
            )
            deliverable_responses.append(saved_deliv)

        logger.info(
            "Successfully generated and validated %d deliverables for doc %s",
            len(deliverable_responses),
            request.doc_id,
        )

        return MultiDeliverableResponse(
            doc_id=request.doc_id,
            query_used=query,
            retrieved_chunks_count=len(grounded_context.retrieved_chunks),
            total_deliverables=len(deliverable_responses),
            deliverables=deliverable_responses,
            all_citations_verified=True,
        )
