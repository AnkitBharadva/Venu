"""Unit and Integration Tests for HyperFrames Video Generation Engine.

Verifies deterministic seekable timeline construction, multi-scene storyboarding,
air-gapped vendor GSAP loading, styling options, and API endpoints.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.video.hyperframes_engine import HyperFramesVideoEngine, get_local_gsap_code


@pytest.fixture
def sample_post_text() -> str:
    return (
        "1/4 CERT Units: prioritize tactile interaction cues; no ambiguity in web density "
        "or facial entrapment. Hands reach out confirming active entanglement."
    )


@pytest.fixture
def sample_thread_blocks() -> list[dict]:
    return [
        {
            "block_index": 0,
            "title": "Entanglement Vector",
            "sentences": [
                {
                    "sentence_id": "s1",
                    "sentence_index": 0,
                    "text": "A person is struggling against a thick web of spiderwebs covering their face.",
                    "citations": [{"chunk_id": "chunk_001", "char_offset_start": 0, "char_offset_end": 45, "quote": "thick web of spiderwebs covering their face"}],
                }
            ],
        },
        {
            "block_index": 1,
            "title": "Kinetic Evidence",
            "sentences": [
                {
                    "sentence_id": "s2",
                    "sentence_index": 1,
                    "text": "Hands reach out, fingers curled as if grasping — visual evidence confirms entanglement.",
                    "citations": [{"chunk_id": "chunk_002", "char_offset_start": 46, "char_offset_end": 90, "quote": "fingers curled as if grasping"}],
                }
            ],
        },
        {
            "block_index": 2,
            "title": "Tactile Priority",
            "sentences": [
                {
                    "sentence_id": "s3",
                    "sentence_index": 2,
                    "text": "CERT Units: prioritize tactile interaction cues; no ambiguity in web density.",
                    "citations": [{"chunk_id": "chunk_003", "char_offset_start": 91, "char_offset_end": 140, "quote": "prioritize tactile interaction cues"}],
                }
            ],
        },
    ]


def test_theme_resolution_and_aliases():
    """Verify theme resolution and aliases."""
    key, pal = HyperFramesVideoEngine.resolve_theme("midnight_navy")
    assert key == "midnight_navy"
    assert pal["primary"] == "#818cf8"

    key, pal = HyperFramesVideoEngine.resolve_theme("terminal")
    assert key == "terminal_green"
    assert pal["primary"] == "#22c55e"

    key, pal = HyperFramesVideoEngine.resolve_theme("amber")
    assert key == "sunset_amber"

    key, pal = HyperFramesVideoEngine.resolve_theme("crimson")
    assert key == "crimson_alert"

    key, pal = HyperFramesVideoEngine.resolve_theme("cyber_dark")
    assert key == "dark"


def test_local_gsap_loading():
    """Verify local GSAP code is available without CDN."""
    code = get_local_gsap_code()
    assert len(code) > 100
    assert "gsap" in code


def test_render_from_post_structure(sample_post_text):
    """Verify single post video compilation adheres to HyperFrames contract."""
    result = HyperFramesVideoEngine.render_from_post(
        text=sample_post_text,
        title="Tactical Entanglement Advisory",
        deliverable_type="twitter_thread",
        aspect_ratio="16:9",
        theme="terminal_green",
        font_family="mono",
        motion_style="kinetic",
        brand_name="CERT COMMAND",
        classification="RESTRICTED // VERIFIED",
        duration=12.0,
    )

    assert result["video_id"].startswith("hf_video_")
    assert result["aspect_ratio"] == "16:9"
    assert result["theme"] == "terminal_green"
    assert result["duration"] == 12.0

    html_doc = result["html"]
    # Check HyperFrames core specification markers
    assert 'data-composition-id="main"' in html_doc
    assert 'data-width="1920"' in html_doc
    assert 'data-height="1080"' in html_doc
    assert 'data-duration="12.0"' in html_doc
    assert 'class="clip"' in html_doc
    assert 'window.__timelines["main"] = tl;' in html_doc

    # Check branding and classification
    assert "CERT COMMAND" in html_doc
    assert "RESTRICTED // VERIFIED" in html_doc

    # Check scenes
    assert 'id="scene-hook"' in html_doc
    assert 'id="scene-content"' in html_doc
    assert 'id="scene-prov"' in html_doc
    assert 'id="scene-outro"' in html_doc

    # Check interactive controls
    assert "hf-player" in html_doc
    assert "hf-scrubber" in html_doc


def test_render_vertical_reel_9_16(sample_post_text):
    """Verify 9:16 vertical reel video layout for mobile shorts and reels."""
    result = HyperFramesVideoEngine.render_from_post(
        text=sample_post_text,
        title="Tactical Directive",
        aspect_ratio="9:16",
        theme="sunset_amber",
        duration=10.0,
    )

    assert result["aspect_ratio"] == "9:16"
    html_doc = result["html"]
    assert 'data-width="1080"' in html_doc
    assert 'data-height="1920"' in html_doc
    assert 'data-duration="10.0"' in html_doc


def test_render_thread_video_multi_scenes(sample_thread_blocks):
    """Verify multi-scene thread video sequence generation."""
    result = HyperFramesVideoEngine.render_thread_video(
        blocks=sample_thread_blocks,
        title="Tactical Thread Sequence",
        deliverable_type="twitter_thread",
        aspect_ratio="16:9",
        theme="midnight_navy",
        seconds_per_scene=4.0,
    )

    assert result["total_scenes"] == 3
    # 3 scenes * 4.0s + 3.0s outro = 15.0s
    assert result["duration"] == 15.0

    html_doc = result["html"]
    assert 'id="chapter-1"' in html_doc
    assert 'id="chapter-2"' in html_doc
    assert 'id="chapter-3"' in html_doc
    assert 'id="scene-outro"' in html_doc
    assert "Tweet 1/3" in html_doc
    assert "Tweet 2/3" in html_doc
    assert "Tweet 3/3" in html_doc
    assert 'window.__timelines["main"] = tl;' in html_doc


@pytest.mark.asyncio
async def test_video_api_styling_options():
    """Test GET /api/v1/video/styling-options."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/video/styling-options")
        assert res.status_code == 200
        data = res.json()
        assert "themes" in data
        assert len(data["themes"]) == 7
        assert "fonts" in data
        assert "motion_styles" in data
        assert "aspect_ratios" in data
        ratio_ids = [r["id"] for r in data["aspect_ratios"]]
        assert "16:9" in ratio_ids
        assert "9:16" in ratio_ids
        assert "1:1" in ratio_ids
        assert "4:3" in ratio_ids


@pytest.mark.asyncio
async def test_video_api_generate_and_preview(sample_post_text):
    """Test POST /api/v1/video/generate-post-video and GET /preview/{id}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "post_text": sample_post_text,
            "title": "Tactical Intelligence Post",
            "deliverable_type": "twitter_thread",
            "aspect_ratio": "16:9",
            "theme": "terminal_green",
            "font_family": "mono",
            "motion_style": "kinetic",
            "brand_name": "CYBER INTEL COMMAND",
            "classification": "TOP SECRET",
            "duration": 10.0,
        }
        res = await client.post("/api/v1/video/generate-post-video", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "video_id" in data
        assert data["theme"] == "terminal_green"
        assert data["aspect_ratio"] == "16:9"
        assert data["brand_name"] == "CYBER INTEL COMMAND"
        assert data["preview_url"] == f"/api/v1/video/preview/{data['video_id']}"
        assert data["mp4_download_url"] == f"/api/v1/video/export-mp4/{data['video_id']}"

        # Fetch live preview
        prev_res = await client.get(data["preview_url"])
        assert prev_res.status_code == 200
        assert "text/html" in prev_res.headers["content-type"]
        assert 'data-composition-id="main"' in prev_res.text
        assert "CYBER INTEL COMMAND" in prev_res.text


@pytest.mark.asyncio
async def test_video_api_generate_thread_video(sample_thread_blocks):
    """Test POST /api/v1/video/generate-thread-video."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "blocks": sample_thread_blocks,
            "title": "Full Thread Sequence Video",
            "deliverable_type": "twitter_thread",
            "aspect_ratio": "9:16",
            "theme": "midnight_navy",
            "font_family": "serif",
            "brand_name": "STRATEGIC ADVISORY",
            "classification": "EXECUTIVE MEMO",
            "seconds_per_scene": 4.0,
        }
        res = await client.post("/api/v1/video/generate-thread-video", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_scenes"] == 3
        assert data["aspect_ratio"] == "9:16"
        assert data["duration"] == 15.0

        # Check preview
        prev_res = await client.get(data["preview_url"])
        assert prev_res.status_code == 200
        assert "chapter-1" in prev_res.text
        assert "chapter-2" in prev_res.text
        assert "chapter-3" in prev_res.text
        assert "STRATEGIC ADVISORY" in prev_res.text


@pytest.mark.asyncio
async def test_vendor_gsap_endpoint():
    """Test GET /api/v1/video/vendor/gsap.min.js."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/video/vendor/gsap.min.js")
        assert res.status_code == 200
        assert "javascript" in res.headers["content-type"]
        assert len(res.text) > 100
