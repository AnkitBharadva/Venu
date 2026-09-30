"""AIZ Infographic Visual API Router.

Provides endpoints for on-demand infographic compilation, live browser preview,
and template discovery adhering to the aiz-infographic 5-layer system.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit_log import GeneratedOutput, SourceDocument
from app.models.understanding import DocumentChunk
from app.services.infographics.aiz_infographic_engine import AIZInfographicEngine

logger = logging.getLogger("app.api.infographics")

router = APIRouter(prefix="/api/v1/infographics", tags=["AIZ Infographic Visual Engine"])

# In-memory card cache with size bounding for instant preview & high-res PNG export
_POST_CARDS_CACHE: dict[str, dict[str, Any]] = {}
MAX_POST_CACHE_SIZE = 120


def _cache_post_card(card_id: str, data: dict[str, Any]) -> None:
    if len(_POST_CARDS_CACHE) >= MAX_POST_CACHE_SIZE:
        oldest = next(iter(_POST_CARDS_CACHE))
        _POST_CARDS_CACHE.pop(oldest, None)
    _POST_CARDS_CACHE[card_id] = data


class RenderInfographicRequest(BaseModel):
    """Payload to render an AIZ infographic from arbitrary structured deliverable content."""

    title: str = Field(default="Intelligence Infographic", description="Main infographic title")
    summary: str | None = Field(default=None, description="Executive takeaway or briefing summary")
    deliverable_type: str = Field(default="infographic", description="Source deliverable type")
    blocks: list[dict[str, Any]] = Field(default_factory=list, description="List of grounded content blocks")
    key_metrics: list[dict[str, Any]] | None = Field(default=None, description="Optional KPI metrics")
    citations: list[dict[str, Any]] | None = Field(default=None, description="Grounding citations")
    template: str = Field(default="auto", description="Template: auto, tactical_defense, technical_architecture, process_flow")
    theme: str = Field(default="dark", description="Visual theme: dark, light")


class GeneratePostCardRequest(BaseModel):
    """Payload to generate a tailored visual card for a specific post."""

    post_text: str = Field(..., description="The actual text of the post to be visualized")
    title: str | None = Field(default=None, description="Optional custom headline/hook for the post card")
    deliverable_type: str = Field(default="linkedin_post", description="Post type: linkedin_post, twitter_thread, executive_summary, advisory, custom_post")
    doc_id: uuid.UUID | None = Field(default=None, description="Source document ID for grounding context")
    output_id: uuid.UUID | None = Field(default=None, description="Source deliverable output ID if available")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio: 16:9, 1:1, 4:3, or 9:16")
    theme: str = Field(default="dark", description="Visual theme key or alias")
    sequence_index: int | None = Field(default=None, description="Sequence index for multi-part threads (e.g. 1)")
    sequence_total: int | None = Field(default=None, description="Total count in thread sequence (e.g. 4)")
    sequence_label: str | None = Field(default=None, description="Sequence badge label (e.g. Tweet 1/4)")
    font_family: str = Field(default="sans", description="Font pairing: sans, serif, mono")
    layout_preset: str = Field(default="hero", description="Layout preset: hero, split, technical, minimal")
    brand_name: str | None = Field(default=None, description="Optional organization or brand name")
    classification: str | None = Field(default=None, description="Security or grounding classification label")


class PostCardResponse(BaseModel):
    """Response containing post card metadata, preview URL, and direct PNG download URL."""

    card_id: str
    title: str
    deliverable_type: str
    aspect_ratio: str
    theme: str
    preview_url: str
    png_download_url: str
    html: str
    sequence_index: int | None = None
    sequence_total: int | None = None
    sequence_label: str | None = None
    post_text: str | None = None
    font_family: str | None = None
    layout_preset: str | None = None
    brand_name: str | None = None
    classification: str | None = None


class GenerateThreadCardsRequest(BaseModel):
    """Payload to generate individual visual cards for each post in a thread or deliverable."""

    post_text: str | None = Field(default=None, description="Raw text of the thread or multi-part post")
    title: str | None = Field(default=None, description="Optional thread title")
    deliverable_type: str = Field(default="twitter_thread", description="Deliverable type: twitter_thread, linkedin_post, etc.")
    doc_id: uuid.UUID | None = Field(default=None, description="Source document ID")
    output_id: uuid.UUID | None = Field(default=None, description="Source deliverable output ID")
    blocks: list[dict[str, Any]] | None = Field(default=None, description="Structured blocks if available")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio: 16:9, 1:1, 4:3, or 9:16")
    theme: str = Field(default="dark", description="Visual theme key or alias")
    font_family: str = Field(default="sans", description="Font pairing: sans, serif, mono")
    layout_preset: str = Field(default="hero", description="Layout preset: hero, split, technical, minimal")
    brand_name: str | None = Field(default=None, description="Optional organization or brand name")
    classification: str | None = Field(default=None, description="Security or grounding classification label")


class ThreadCardsResponse(BaseModel):
    """Response containing individual visual cards for all posts in the sequence."""

    total_cards: int
    deliverable_type: str
    cards: list[PostCardResponse]


class TemplateMetadataResponse(BaseModel):
    """Metadata response describing available templates and canvases."""

    template_id: str
    name: str
    description: str
    recommended_for: str


@router.get(
    "/preview/{output_id}",
    response_class=Response,
    summary="Live standalone HTML preview of an AIZ infographic deliverable",
)
async def preview_infographic(
    output_id: uuid.UUID,
    theme: str = Query(default="dark", description="Theme: dark or light"),
    template: str = Query(default="auto", description="Template: auto, tactical_defense, technical_architecture, process_flow"),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Compile deliverable and return standalone, air-gapped HTML for direct browser/iframe preview."""
    stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == output_id)
    res = await session.execute(stmt)
    output = res.scalar_one_or_none()
    if not output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable '{output_id}' not found.",
        )

    try:
        html_content = AIZInfographicEngine.render_from_deliverable(
            deliverable=output,
            template=template,
            theme=theme,
        )
        return Response(content=html_content, media_type="text/html; charset=utf-8")
    except Exception as exc:
        logger.error("Failed to render AIZ infographic for %s: %s", output_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Infographic rendering failed: {exc}",
        ) from exc


@router.get(
    "/export-png/{output_id}",
    response_class=Response,
    summary="Download high-resolution 2x retina PNG of the infographic",
)
async def export_infographic_png(
    output_id: uuid.UUID,
    theme: str = Query(default="dark", description="Theme: dark or light"),
    template: str = Query(default="auto", description="Template: auto, tactical_defense, technical_architecture, process_flow"),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Render high-resolution PNG image directly using local headless Chromium."""
    stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == output_id)
    res = await session.execute(stmt)
    output = res.scalar_one_or_none()
    if not output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable '{output_id}' not found.",
        )

    try:
        html_content = AIZInfographicEngine.render_from_deliverable(
            deliverable=output,
            template=template,
            theme=theme,
        )
        png_bytes = await AIZInfographicEngine.render_png_bytes(html_content, scale=2)
        filename = f"aiz_infographic_{str(output_id)[:8]}.png"
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.error("Failed to render PNG for %s: %s", output_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PNG rendering failed: {exc}",
        ) from exc


@router.post(
    "/render",
    response_class=Response,
    summary="Compile custom structured content directly into an AIZ infographic HTML",
)
async def render_custom_infographic(
    request: RenderInfographicRequest,
) -> Response:
    """Render an ad-hoc infographic from JSON content blocks and return standalone HTML."""
    try:
        payload = {
            "output_id": str(uuid.uuid4()),
            "doc_id": "custom-render",
            "deliverable_type": request.deliverable_type,
            "status": "final",
            "content": {
                "title": request.title,
                "summary": request.summary,
                "blocks": request.blocks,
            },
            "format_metadata": {
                "key_metrics": request.key_metrics or [],
            },
            "citations": request.citations or [],
        }
        html_content = AIZInfographicEngine.render_from_deliverable(
            deliverable=payload,
            template=request.template,
            theme=request.theme,
        )
        return Response(content=html_content, media_type="text/html; charset=utf-8")
    except Exception as exc:
        logger.error("Custom infographic rendering failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Render request failed: {exc}",
        ) from exc


@router.post(
    "/generate-post-card",
    response_model=PostCardResponse,
    summary="Compile a specific post's text and underlying document context into a tailored visual card",
)
async def generate_post_card(
    request: GeneratePostCardRequest,
    session: AsyncSession = Depends(get_db),
) -> PostCardResponse:
    """Generate high-impact, air-gapped visual card tailored specifically to a post and document context."""
    doc_id = request.doc_id
    doc_title = None
    citations: list[dict[str, Any]] = []
    chunks: list[Any] = []
    output_title = request.title

    # 1. If output_id supplied, load deliverable to extract grounding citations and original doc_id
    if request.output_id:
        stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == request.output_id)
        res = await session.execute(stmt)
        output = res.scalar_one_or_none()
        if output:
            if not doc_id:
                doc_id = output.doc_id
            citations = output.citations or []
            if not output_title and output.content:
                output_title = output.content.get("title")

    # 2. If doc_id supplied, load document context and chunks for verifiable claim provenance
    if doc_id:
        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        if doc:
            doc_title = doc.original_filename

        chunk_stmt = select(DocumentChunk).where(DocumentChunk.doc_id == doc_id).order_by(DocumentChunk.chunk_index)
        chunk_res = await session.execute(chunk_stmt)
        chunks = list(chunk_res.scalars().all())

    card_id = f"post_{uuid.uuid4().hex[:12]}"
    try:
        html_content = AIZInfographicEngine.render_from_post(
            post_text=request.post_text,
            title=output_title,
            deliverable_type=request.deliverable_type,
            doc_id=str(doc_id) if doc_id else "source-doc",
            doc_title=doc_title,
            chunks=chunks,
            citations=citations,
            aspect_ratio=request.aspect_ratio,
            theme=request.theme,
            output_id=card_id,
            status="final",
            sequence_index=request.sequence_index,
            sequence_total=request.sequence_total,
            sequence_label=request.sequence_label,
            font_family=request.font_family,
            layout_preset=request.layout_preset,
            brand_name=request.brand_name,
            classification=request.classification,
        )

        _cache_post_card(
            card_id,
            {
                "html": html_content,
                "title": output_title or "Post Visual Card",
                "deliverable_type": request.deliverable_type,
                "aspect_ratio": request.aspect_ratio,
                "theme": request.theme,
                "font_family": request.font_family,
                "layout_preset": request.layout_preset,
                "brand_name": request.brand_name,
                "classification": request.classification,
            },
        )

        return PostCardResponse(
            card_id=card_id,
            title=output_title or "Post Visual Card",
            deliverable_type=request.deliverable_type,
            aspect_ratio=request.aspect_ratio,
            theme=request.theme,
            preview_url=f"/api/v1/infographics/post-card-preview/{card_id}",
            png_download_url=f"/api/v1/infographics/post-card-png/{card_id}",
            html=html_content,
            sequence_index=request.sequence_index,
            sequence_total=request.sequence_total,
            sequence_label=request.sequence_label,
            post_text=request.post_text,
            font_family=request.font_family,
            layout_preset=request.layout_preset,
            brand_name=request.brand_name,
            classification=request.classification,
        )
    except Exception as exc:
        logger.error("Failed to generate post visual card: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Post visual card generation failed: {exc}",
        ) from exc


@router.post(
    "/generate-thread-cards",
    response_model=ThreadCardsResponse,
    summary="Generate dedicated visual cards for every individual post in a thread or sequence",
)
async def generate_thread_cards(
    request: GenerateThreadCardsRequest,
    session: AsyncSession = Depends(get_db),
) -> ThreadCardsResponse:
    """Compile each tweet or post in a thread into its own dedicated, sequentially-numbered visual card."""
    doc_id = request.doc_id
    doc_title: str | None = None
    citations: list[dict[str, Any]] = []

    if request.output_id:
        stmt = select(GeneratedOutput).where(GeneratedOutput.output_id == request.output_id)
        res = await session.execute(stmt)
        output = res.scalar_one_or_none()
        if output:
            doc_id = output.doc_id
            citations = output.citations or []
            if not request.title and output.content:
                request.title = output.content.get("title")
            if not request.blocks and output.content:
                request.blocks = output.content.get("blocks")

    if doc_id:
        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        if doc:
            doc_title = doc.original_filename

    try:
        compiled_cards = AIZInfographicEngine.render_thread_cards(
            text=request.post_text,
            blocks=request.blocks,
            title=request.title,
            deliverable_type=request.deliverable_type,
            doc_id=str(doc_id) if doc_id else "source-doc",
            doc_title=doc_title,
            citations=citations,
            aspect_ratio=request.aspect_ratio,
            theme=request.theme,
            status="final",
            font_family=request.font_family,
            layout_preset=request.layout_preset,
            brand_name=request.brand_name,
            classification=request.classification,
        )

        response_cards: list[PostCardResponse] = []
        for c in compiled_cards:
            _cache_post_card(
                c["card_id"],
                {
                    "html": c["html"],
                    "title": c["title"],
                    "deliverable_type": request.deliverable_type,
                    "aspect_ratio": request.aspect_ratio,
                    "theme": request.theme,
                    "font_family": request.font_family,
                    "layout_preset": request.layout_preset,
                    "brand_name": request.brand_name,
                    "classification": request.classification,
                },
            )
            response_cards.append(
                PostCardResponse(
                    card_id=c["card_id"],
                    title=c["title"],
                    deliverable_type=request.deliverable_type,
                    aspect_ratio=request.aspect_ratio,
                    theme=request.theme,
                    preview_url=c["preview_url"],
                    png_download_url=c["png_download_url"],
                    html=c["html"],
                    sequence_index=c["sequence_index"],
                    sequence_total=c["sequence_total"],
                    sequence_label=c["sequence_label"],
                    post_text=c["post_text"],
                    font_family=request.font_family,
                    layout_preset=request.layout_preset,
                    brand_name=request.brand_name,
                    classification=request.classification,
                )
            )

        return ThreadCardsResponse(
            total_cards=len(response_cards),
            deliverable_type=request.deliverable_type,
            cards=response_cards,
        )
    except Exception as exc:
        logger.error("Failed to generate thread visual cards: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Thread cards generation failed: {exc}",
        ) from exc


@router.get(
    "/styling-options",
    summary="List available visual themes, fonts, layouts, and aspect ratios",
)
async def get_styling_options() -> dict[str, Any]:
    """Return styling options available for visual card and infographic synthesis."""
    themes_list = [
        {
            "id": k,
            "name": v["name"],
            "primary": v["primary"],
            "accent": v["accent"],
            "bg": v["bg"],
        }
        for k, v in AIZInfographicEngine.THEMES.items()
    ]
    fonts_list = [
        {"id": "sans", "label": "Modern Sans", "desc": "Clean, sharp UI system sans-serif"},
        {"id": "serif", "label": "Editorial Serif", "desc": "Executive, scholarly serif typography"},
        {"id": "mono", "label": "Terminal Mono", "desc": "Tactical cybersecurity monospace"},
    ]
    layouts_list = [
        {"id": "hero", "label": "Hero Quote", "desc": "Prominent executive statement hook"},
        {"id": "split", "label": "Split Matrix", "desc": "Categorized multi-point takeaways"},
        {"id": "technical", "label": "Terminal Spec", "desc": "Command-line terminal block with provenance"},
        {"id": "minimal", "label": "Minimalist", "desc": "High-whitespace clean editorial layout"},
    ]
    ratios_list = [
        {"id": "16:9", "label": "16:9 Landscape", "dims": "1200x675", "desc": "X / LinkedIn feed"},
        {"id": "1:1", "label": "1:1 Square", "dims": "1080x1080", "desc": "Carousel & feed"},
        {"id": "4:3", "label": "4:3 Memo", "dims": "1200x900", "desc": "Executive briefing"},
        {"id": "9:16", "label": "9:16 Story/Reel", "dims": "1080x1920", "desc": "Vertical mobile reels & shorts"},
    ]
    return {
        "themes": themes_list,
        "fonts": fonts_list,
        "layouts": layouts_list,
        "aspect_ratios": ratios_list,
    }


@router.get(
    "/post-card-preview/{card_id}",
    response_class=Response,
    summary="Live standalone HTML preview of a generated post visual card",
)
async def preview_post_card(card_id: str) -> Response:
    """Return standalone, air-gapped HTML of a generated post card for iframe preview."""
    cached = _POST_CARDS_CACHE.get(card_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post card '{card_id}' not found or session expired. Please re-generate.",
        )
    return Response(content=cached["html"], media_type="text/html; charset=utf-8")


@router.get(
    "/post-card-png/{card_id}",
    response_class=Response,
    summary="Download high-resolution 2x retina PNG of a generated post visual card",
)
async def download_post_card_png(card_id: str) -> Response:
    """Render high-resolution PNG image directly using local headless Chromium."""
    cached = _POST_CARDS_CACHE.get(card_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post card '{card_id}' not found or session expired. Please re-generate.",
        )

    try:
        png_bytes = await AIZInfographicEngine.render_png_bytes(cached["html"], scale=2)
        filename = f"post_visual_{card_id[:8]}.png"
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.error("Failed to render post card PNG for %s: %s", card_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Post card PNG rendering failed: {exc}",
        ) from exc


@router.post(
    "/export-post-png",
    response_class=Response,
    summary="Directly generate and download high-resolution PNG for a post in one call",
)
async def export_post_png_direct(
    request: GeneratePostCardRequest,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Generate post card HTML and immediately render & stream pixel-perfect PNG binary."""
    card_resp = await generate_post_card(request=request, session=session)
    try:
        png_bytes = await AIZInfographicEngine.render_png_bytes(card_resp.html, scale=2)
        filename = f"post_visual_{card_resp.card_id[:8]}.png"
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.error("Failed to render direct post PNG: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Direct post PNG rendering failed: {exc}",
        ) from exc


@router.get(
    "/templates",
    response_model=list[TemplateMetadataResponse],
    summary="List available AIZ infographic templates and reference specifications",
)
async def list_templates() -> list[TemplateMetadataResponse]:
    """Catalog of available visual templates adhering to the aiz-infographic reference system."""
    return [
        TemplateMetadataResponse(
            template_id="social_post_card",
            name="Social Post & Executive Card (16:9 / 1:1)",
            description="High-impact visual card tailored specifically to a post (LinkedIn, X, Executive Brief) grounded in document context.",
            recommended_for="LinkedIn posts, X/Twitter threads, executive memo cards, social sharing",
        ),
        TemplateMetadataResponse(
            template_id="tactical_defense",
            name="Tactical Defense Directive",
            description="Hero KPI badges, cryptographic isolation status, protocol cards, and tamper-proof verification audit footer.",
            recommended_for="Defense directives, security advisories, policy enforcements",
        ),
        TemplateMetadataResponse(
            template_id="technical_architecture",
            name="Technical Architecture Breakdown",
            description="Multi-column component grid, vector-graph dimension analysis, and enclave security boundaries.",
            recommended_for="System designs, data pipeline documentation, vector/graph specifications",
        ),
        TemplateMetadataResponse(
            template_id="process_flow",
            name="Sequential Process & Pipeline Flow",
            description="Step-by-step chevron cards with stage numbers, milestone verification, and source chunk links.",
            recommended_for="Ingestion workflows, standard operating procedures, audit lifecycles",
        ),
        TemplateMetadataResponse(
            template_id="executive_brief",
            name="Executive Intelligence Brief",
            description="High-level focal takeaway, executive KPI strip, strategic findings, and compliance seal.",
            recommended_for="Command briefings, leadership summaries, quarterly reviews",
        ),
    ]
