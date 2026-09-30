"""HyperFrames Video Generation API Router.

Provides endpoints for on-demand motion video compilation, live browser preview,
interactive playback, and H.264 MP4 export using the HyperFrames architecture.
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
from app.services.video.hyperframes_engine import HyperFramesVideoEngine, get_local_gsap_code

logger = logging.getLogger("app.api.video")

router = APIRouter(prefix="/api/v1/video", tags=["HyperFrames Motion Video Engine"])

# In-memory video cache with size bounding for instant playback & MP4 export
_VIDEO_CACHE: dict[str, dict[str, Any]] = {}
MAX_VIDEO_CACHE_SIZE = 80


def _cache_video(video_id: str, data: dict[str, Any]) -> None:
    if len(_VIDEO_CACHE) >= MAX_VIDEO_CACHE_SIZE:
        oldest = next(iter(_VIDEO_CACHE))
        _VIDEO_CACHE.pop(oldest, None)
    _VIDEO_CACHE[video_id] = data


class GeneratePostVideoRequest(BaseModel):
    """Payload to generate a tailored HyperFrames motion video for a specific post."""

    post_text: str = Field(..., description="The actual text of the post to be visualized")
    title: str | None = Field(default=None, description="Optional custom headline/hook for the video")
    deliverable_type: str = Field(default="linkedin_post", description="Post type: linkedin_post, twitter_thread, etc.")
    doc_id: uuid.UUID | None = Field(default=None, description="Source document ID for grounding context")
    output_id: uuid.UUID | None = Field(default=None, description="Source deliverable output ID if available")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio: 16:9, 9:16, 1:1, or 4:3")
    theme: str = Field(default="dark", description="Visual theme palette key or alias")
    font_family: str = Field(default="sans", description="Font pairing: sans, serif, mono")
    motion_style: str = Field(default="kinetic", description="Motion style: kinetic, tactical, editorial, minimal")
    brand_name: str | None = Field(default=None, description="Optional organization or brand name")
    classification: str | None = Field(default=None, description="Security or grounding classification label")
    duration: float = Field(default=12.0, description="Total video duration in seconds")


class GenerateThreadVideoRequest(BaseModel):
    """Payload to generate a multi-scene HyperFrames motion video covering an entire thread."""

    post_text: str | None = Field(default=None, description="Raw text of the thread or multi-part post")
    title: str | None = Field(default=None, description="Optional thread title")
    deliverable_type: str = Field(default="twitter_thread", description="Deliverable type")
    doc_id: uuid.UUID | None = Field(default=None, description="Source document ID")
    output_id: uuid.UUID | None = Field(default=None, description="Source deliverable output ID")
    blocks: list[dict[str, Any]] | None = Field(default=None, description="Structured blocks if available")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio: 16:9, 9:16, 1:1, or 4:3")
    theme: str = Field(default="dark", description="Visual theme palette key or alias")
    font_family: str = Field(default="sans", description="Font pairing: sans, serif, mono")
    motion_style: str = Field(default="kinetic", description="Motion style: kinetic, tactical, editorial, minimal")
    brand_name: str | None = Field(default=None, description="Optional organization or brand name")
    classification: str | None = Field(default=None, description="Security or grounding classification label")
    seconds_per_scene: float = Field(default=4.5, description="Seconds per chapter scene in the sequence")


class VideoResponse(BaseModel):
    """Response containing video metadata, preview URL, and direct MP4 download URL."""

    video_id: str
    title: str
    deliverable_type: str
    aspect_ratio: str
    theme: str
    font_family: str
    motion_style: str
    brand_name: str
    classification: str
    duration: float
    total_scenes: int | None = None
    preview_url: str
    mp4_download_url: str
    html: str


@router.post(
    "/generate-post-video",
    response_model=VideoResponse,
    summary="Compile a standalone HyperFrames motion video for a specific post",
)
async def generate_post_video(
    request: GeneratePostVideoRequest,
    session: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Compile a deterministic HyperFrames motion video with kinetic typography and provenance."""
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

    if doc_id:
        doc_stmt = select(SourceDocument).where(SourceDocument.doc_id == doc_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        if doc:
            doc_title = doc.original_filename

    try:
        compiled = HyperFramesVideoEngine.render_from_post(
            text=request.post_text,
            title=request.title,
            deliverable_type=request.deliverable_type,
            doc_id=str(doc_id) if doc_id else "source-doc",
            doc_title=doc_title,
            citations=citations,
            aspect_ratio=request.aspect_ratio,
            theme=request.theme,
            font_family=request.font_family,
            motion_style=request.motion_style,
            brand_name=request.brand_name,
            classification=request.classification,
            duration=request.duration,
        )

        _cache_video(
            compiled["video_id"],
            {
                "html": compiled["html"],
                "title": compiled["title"],
                "aspect_ratio": compiled["aspect_ratio"],
                "theme": compiled["theme"],
                "duration": compiled["duration"],
            },
        )

        return VideoResponse(
            video_id=compiled["video_id"],
            title=compiled["title"],
            deliverable_type=compiled["deliverable_type"],
            aspect_ratio=compiled["aspect_ratio"],
            theme=compiled["theme"],
            font_family=compiled["font_family"],
            motion_style=compiled["motion_style"],
            brand_name=compiled["brand_name"],
            classification=compiled["classification"],
            duration=compiled["duration"],
            total_scenes=1,
            preview_url=compiled["preview_url"],
            mp4_download_url=compiled["mp4_download_url"],
            html=compiled["html"],
        )
    except Exception as exc:
        logger.error("Failed to generate post video: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Post video generation failed: {exc}",
        ) from exc


@router.post(
    "/generate-thread-video",
    response_model=VideoResponse,
    summary="Compile a multi-scene HyperFrames motion video for an entire thread",
)
async def generate_thread_video(
    request: GenerateThreadVideoRequest,
    session: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Compile a multi-scene HyperFrames motion video sequence for an entire thread or deliverable."""
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
        compiled = HyperFramesVideoEngine.render_thread_video(
            blocks=request.blocks,
            text=request.post_text,
            title=request.title,
            deliverable_type=request.deliverable_type,
            doc_id=str(doc_id) if doc_id else "source-doc",
            doc_title=doc_title,
            citations=citations,
            aspect_ratio=request.aspect_ratio,
            theme=request.theme,
            font_family=request.font_family,
            motion_style=request.motion_style,
            brand_name=request.brand_name,
            classification=request.classification,
            seconds_per_scene=request.seconds_per_scene,
        )

        _cache_video(
            compiled["video_id"],
            {
                "html": compiled["html"],
                "title": compiled["title"],
                "aspect_ratio": compiled["aspect_ratio"],
                "theme": compiled["theme"],
                "duration": compiled["duration"],
            },
        )

        return VideoResponse(
            video_id=compiled["video_id"],
            title=compiled["title"],
            deliverable_type=compiled["deliverable_type"],
            aspect_ratio=compiled["aspect_ratio"],
            theme=compiled["theme"],
            font_family=compiled["font_family"],
            motion_style=compiled["motion_style"],
            brand_name=compiled["brand_name"],
            classification=compiled["classification"],
            duration=compiled["duration"],
            total_scenes=compiled.get("total_scenes", 1),
            preview_url=compiled["preview_url"],
            mp4_download_url=compiled["mp4_download_url"],
            html=compiled["html"],
        )
    except Exception as exc:
        logger.error("Failed to generate thread video: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Thread video generation failed: {exc}",
        ) from exc


@router.get(
    "/preview/{video_id}",
    summary="Live interactive browser preview of compiled HyperFrames video",
)
async def preview_video(video_id: str) -> Response:
    """Serve the self-contained HyperFrames HTML composition for live browser playback."""
    cached = _VIDEO_CACHE.get(video_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video composition '{video_id}' not found or session expired. Please re-compile.",
        )
    return Response(
        content=cached["html"],
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Security-Policy": "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:;",
        },
    )


@router.get(
    "/export-mp4/{video_id}",
    summary="Render and download high-quality H.264 MP4 video",
)
async def export_mp4(video_id: str) -> Response:
    """Render the HyperFrames HTML composition into H.264 MP4 bytes via local Chromium & FFmpeg."""
    cached = _VIDEO_CACHE.get(video_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video composition '{video_id}' not found. Please re-compile.",
        )

    try:
        mp4_bytes = await HyperFramesVideoEngine.render_mp4_bytes(
            html_content=cached["html"],
            aspect_ratio=cached.get("aspect_ratio", "16:9"),
            duration=cached.get("duration", 10.0),
        )

        title_slug = (cached.get("title") or "hyperframes_video").lower()
        import re
        title_slug = re.sub(r"[^a-z0-9]+", "_", title_slug).strip("_") or "video"
        filename = f"{title_slug}.mp4"

        return Response(
            content=mp4_bytes,
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.error("Failed to render MP4 video: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MP4 rendering failed: {exc}",
        ) from exc


@router.get(
    "/styling-options",
    summary="List available visual themes, fonts, motion styles, and aspect ratios",
)
async def get_styling_options() -> dict[str, Any]:
    """Return styling options available for HyperFrames video generation."""
    themes_list = [
        {
            "id": k,
            "name": v["name"],
            "primary": v["primary"],
            "accent": v["accent"],
            "bg": v["bg"],
        }
        for k, v in HyperFramesVideoEngine.THEMES.items()
    ]
    fonts_list = [
        {"id": "sans", "label": "Modern Sans", "desc": "Clean, sharp UI system sans-serif"},
        {"id": "serif", "label": "Editorial Serif", "desc": "Executive, scholarly serif typography"},
        {"id": "mono", "label": "Terminal Mono", "desc": "Tactical cybersecurity monospace"},
    ]
    motion_styles = [
        {"id": "kinetic", "label": "Kinetic Typography", "desc": "Dynamic text staggers, scales, and blur-in hooks"},
        {"id": "tactical", "label": "Tactical Cyber", "desc": "High-contrast terminal boxes with command prompt reveals"},
        {"id": "editorial", "label": "Executive Editorial", "desc": "Smooth elegant fade-ins and scholarly quotation cards"},
        {"id": "minimal", "label": "Clean Minimalist", "desc": "Distraction-free high-whitespace motion"},
    ]
    ratios_list = [
        {"id": "16:9", "label": "16:9 Landscape", "dims": "1920x1080", "desc": "YouTube, X, LinkedIn feed"},
        {"id": "9:16", "label": "9:16 Vertical Reel", "dims": "1080x1920", "desc": "Shorts, Reels, Stories"},
        {"id": "1:1", "label": "1:1 Square", "dims": "1080x1080", "desc": "Carousel feeds & Instagram"},
        {"id": "4:3", "label": "4:3 Memo", "dims": "1440x1080", "desc": "Executive briefing memo"},
    ]
    return {
        "themes": themes_list,
        "fonts": fonts_list,
        "motion_styles": motion_styles,
        "aspect_ratios": ratios_list,
    }


@router.get(
    "/vendor/gsap.min.js",
    summary="Serve local air-gapped GSAP 3 JavaScript",
)
async def get_vendor_gsap() -> Response:
    """Serve local air-gapped GSAP library."""
    code = get_local_gsap_code()
    return Response(content=code, media_type="application/javascript")
