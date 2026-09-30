"""Unit and integration test suite for AIZ-Infographic visual synthesis layer."""

import re
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.infographics import AIZInfographicEngine
from app.services.review_service import ReviewService


@pytest.fixture
def sample_deliverable_data():
    """Mock grounded deliverable structure matching Phase 4 & Phase 5 models."""
    chunk_id = uuid.uuid4()
    return {
        "output_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "deliverable_type": "infographic",
        "status": "final",
        "content": {
            "title": "Air-Gap Defense Directive 2026",
            "summary": "Mandatory perimeter isolation and cryptographic standards across tactical enclaves.",
            "blocks": [
                {
                    "block_index": 0,
                    "title": "Perimeter Enclave Isolation",
                    "sentences": [
                        {
                            "sentence_id": "sent_1",
                            "text": "All computing hardware must operate disconnected from external telecommunications.",
                            "citations": [
                                {
                                    "chunk_id": chunk_id,
                                    "quote": "Perimeter Enclave Isolation requires disconnected telecommunications.",
                                    "char_offset_start": 0,
                                    "char_offset_end": 74,
                                }
                            ],
                        }
                    ],
                },
                {
                    "block_index": 1,
                    "title": "Cryptographic Data Protection",
                    "sentences": [
                        {
                            "sentence_id": "sent_2",
                            "text": "Storage at rest is secured via authenticated AES-256-GCM ciphers.",
                            "citations": [
                                {
                                    "chunk_id": chunk_id,
                                    "quote": "Data stored at rest must be secured using authenticated AES-256-GCM ciphers.",
                                    "char_offset_start": 75,
                                    "char_offset_end": 150,
                                }
                            ],
                        }
                    ],
                },
            ],
        },
        "format_metadata": {
            "key_metrics": [
                {"value": "100%", "label": "Air-Gap Isolation", "badge": "Hardware"},
                {"value": "1024-D", "label": "BGE-M3 Dense Vectors", "badge": "Neural"},
                {"value": "AES-256", "label": "Cryptographic Rest", "badge": "GCM"},
                {"value": "DEFCON-2", "label": "Operational Readiness", "badge": "Mandatory"},
            ]
        },
        "citations": [
            {
                "chunk_id": str(chunk_id),
                "quote": "Perimeter Enclave Isolation requires disconnected telecommunications.",
                "char_offset_start": 0,
                "char_offset_end": 74,
            }
        ],
    }


def test_aiz_infographic_render_from_deliverable_structure(sample_deliverable_data):
    """Verify complete HTML5 infographic structure according to 5-layer system."""
    html_output = AIZInfographicEngine.render_from_deliverable(
        deliverable=sample_deliverable_data,
        template="tactical_defense",
        theme="dark",
    )

    # 1. Valid HTML5 Doctype and Meta
    assert html_output.startswith("<!DOCTYPE html>")
    assert '<meta name="security-enclave" content="Air-Gapped Tier-4">' in html_output
    assert "<title>Air-Gap Defense Directive 2026 — AIZ Infographic</title>" in html_output

    # 2. Layer 1 & 2: Canvases and Snippets
    assert "aiz-canvas" in html_output
    assert "Perimeter Enclave Isolation" in html_output
    assert "Cryptographic Data Protection" in html_output

    # 3. Layer 3: Styles
    assert "--aiz-bg:" in html_output
    assert "--aiz-primary:" in html_output
    assert "@media print" in html_output

    # 4. Layer 4: Elements (SVG Charts & Interactive Toolbar)
    assert "<svg" in html_output
    assert "aiz-citation-chip" in html_output
    assert "Save PNG" in html_output
    assert "Print / PDF" in html_output
    assert "Toggle Theme" in html_output
    assert "aizOpenCitation" in html_output


def test_aiz_infographic_strict_airgap_compliance(sample_deliverable_data):
    """Enforce strict air-gap compliance: zero external script, font, or CSS calls."""
    html_output = AIZInfographicEngine.render_from_deliverable(sample_deliverable_data)

    # Check for external script or stylesheet links
    external_links = re.findall(r'<link[^>]+href=["\'](http[s]?://[^"\']+)["\']', html_output, re.I)
    assert len(external_links) == 0, f"Found external stylesheet link: {external_links}"

    external_scripts = re.findall(r'<script[^>]+src=["\'](http[s]?://[^"\']+)["\']', html_output, re.I)
    assert len(external_scripts) == 0, f"Found external script tag: {external_scripts}"

    # Check for external url(...) calls in styles
    external_css_urls = re.findall(r'url\(["\']?(http[s]?://[^"\')]+)["\']?\)', html_output, re.I)
    assert len(external_css_urls) == 0, f"Found external CSS url reference: {external_css_urls}"


def test_aiz_infographic_xss_sanitization():
    """Ensure all user and chunk text inputs are strictly HTML-escaped."""
    malicious_data = {
        "output_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "deliverable_type": "infographic",
        "status": "final",
        "content": {
            "title": '<script>alert("XSS")</script>',
            "summary": '<img src="x" onerror="evil()">',
            "blocks": [
                {
                    "block_index": 0,
                    "title": '<b onmouseover="hack()">Security Check</b>',
                    "sentences": [
                        {
                            "sentence_id": "s1",
                            "text": '<iframe src="javascript:alert(1)"></iframe>',
                            "citations": [],
                        }
                    ],
                }
            ],
        },
        "format_metadata": {},
        "citations": [],
    }

    html_output = AIZInfographicEngine.render_from_deliverable(malicious_data)

    assert '<script>alert("XSS")</script>' not in html_output
    assert "&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;" in html_output
    assert '<img src="x" onerror="evil()">' not in html_output
    assert '<iframe src="javascript:alert(1)">' not in html_output


def test_aiz_infographic_render_from_chunks():
    """Verify direct rendering from retrieved raw chunks."""
    class MockChunk:
        def __init__(self, idx: int):
            self.chunk_id = uuid.uuid4()
            self.text = f"Operational unit {idx}: Secure relay deployed with AES-256-GCM encryption."
            self.heading = f"Enclave Cluster {idx}"
            self.char_offset_start = idx * 100
            self.char_offset_end = (idx + 1) * 100

    chunks = [MockChunk(i) for i in range(4)]
    html_output = AIZInfographicEngine.render_from_chunks(
        chunks=chunks,
        title="Tactical Enclave Network",
        summary="Automated chunk visualization probe.",
    )

    assert "<!DOCTYPE html>" in html_output
    assert "Tactical Enclave Network" in html_output
    assert "Enclave Cluster 0" in html_output
    assert "Enclave Cluster 3" in html_output
    assert "aiz-kpi-card" in html_output


def test_aiz_infographic_export_integration(sample_deliverable_data):
    """Verify ReviewService export routing to AIZInfographicEngine."""
    class MockOutput:
        def __init__(self, d):
            self.output_id = d["output_id"]
            self.doc_id = d["doc_id"]
            self.deliverable_type = d["deliverable_type"]
            self.status = d["status"]
            self.content = d["content"]
            self.format_metadata = d["format_metadata"]
            self.citations = d["citations"]
            self.reviewer_id = None
            self.approved_at = None

    mock_output = MockOutput(sample_deliverable_data)

    # 1. Export as "infographic"
    infographic_export = ReviewService._render_export_content(mock_output, "infographic")
    assert "<!DOCTYPE html>" in infographic_export
    assert "aiz-canvas" in infographic_export

    # 2. Export as "aiz-infographic"
    aiz_export = ReviewService._render_export_content(mock_output, "aiz-infographic")
    assert "<!DOCTYPE html>" in aiz_export
    assert "aiz-canvas" in aiz_export

    # 3. Export as "html" for deliverable_type "infographic"
    html_export = ReviewService._render_export_content(mock_output, "html")
    assert "<!DOCTYPE html>" in html_export
    assert "aiz-canvas" in html_export

    # 4. Standard markdown remains intact
    md_export = ReviewService._render_export_content(mock_output, "markdown")
    assert md_export.startswith("# Air-Gap Defense Directive 2026")


def test_aiz_infographic_api_templates_and_render():
    """Verify FastAPI endpoints for template discovery and ad-hoc rendering."""
    client = TestClient(app)

    # 1. GET /api/v1/infographics/templates
    t_resp = client.get("/api/v1/infographics/templates")
    assert t_resp.status_code == 200
    templates = t_resp.json()
    assert len(templates) >= 4
    template_ids = [t["template_id"] for t in templates]
    assert "tactical_defense" in template_ids
    assert "technical_architecture" in template_ids
    assert "process_flow" in template_ids
    assert "executive_brief" in template_ids

    # 2. POST /api/v1/infographics/render
    render_payload = {
        "title": "Ad-Hoc Network Architecture",
        "summary": "Live render payload test.",
        "deliverable_type": "technical_documentation",
        "template": "technical_architecture",
        "theme": "dark",
        "blocks": [
            {
                "block_index": 0,
                "title": "Edge Gateway",
                "sentences": [
                    {
                        "sentence_id": "s1",
                        "text": "DOCX and PDF parsers sanitize incoming data streams.",
                        "citations": [],
                    }
                ],
            }
        ],
        "key_metrics": [
            {"value": "100%", "label": "Air-Gap Isolated", "badge": "Hardware"}
        ],
    }

    r_resp = client.post("/api/v1/infographics/render", json=render_payload)
    assert r_resp.status_code == 200
    assert r_resp.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in r_resp.text
    assert "Ad-Hoc Network Architecture" in r_resp.text
    assert "Edge Gateway" in r_resp.text


def test_render_from_post_structure():
    """Verify render_from_post generates a tailored social card PNG/HTML for a specific post."""
    post_text = (
        "Groundbreaking developments in air-gap security: "
        "Recent strategic findings reveal critical operational mandates for modern defense environments.\n\n"
        "- All tactical intelligence processing must execute inside physically isolated air-gapped enclaves.\n"
        "- Dual-control human verification is strictly enforced before any deliverable export.\n"
        "- Tamper-proof linear SHA-256 hash chains guarantee character-level provenance.\n\n"
        "How is your defense organization enforcing dual-control review in air-gapped enclaves? #CyberSecurity #AirGap"
    )
    chunk_id = uuid.uuid4()
    mock_citations = [
        {
            "chunk_id": str(chunk_id),
            "quote": "All tactical intelligence processing must execute inside physically isolated air-gapped enclaves.",
            "char_offset_start": 0,
            "char_offset_end": 96,
        }
    ]

    html_card = AIZInfographicEngine.render_from_post(
        post_text=post_text,
        title="Operational Insight: Air-Gap Defense Directive",
        deliverable_type="linkedin_post",
        doc_id="test-doc-uuid",
        doc_title="DEFENSE_DIRECTIVE_2026.txt",
        citations=mock_citations,
        aspect_ratio="16:9",
        theme="dark",
    )

    # 1. Structure & Air-Gap
    assert "<!DOCTYPE html>" in html_card
    assert '<meta name="security-enclave" content="Air-Gapped Tier-4">' in html_card
    assert "aiz-post-card-canvas" in html_card
    assert "aiz-ratio-16-9" in html_card

    # 2. Post Content Elements
    assert "Operational Insight: Air-Gap Defense Directive" in html_card
    assert "LINKEDIN POST" in html_card
    assert "100% Grounded" in html_card
    assert "DEFENSE_DIRECTIVE_2026.txt" in html_card
    assert "All tactical intelligence processing" in html_card
    assert "Dual-control human verification" in html_card
    assert "How is your defense organization enforcing" in html_card
    assert "#CyberSecurity" in html_card
    assert f"Ref [{str(chunk_id)[:8]}]" in html_card

    # 3. Air-gap compliance: zero external urls
    assert not re.findall(r'<link[^>]+href=["\'](http[s]?://[^"\']+)["\']', html_card, re.I)
    assert not re.findall(r'<script[^>]+src=["\'](http[s]?://[^"\']+)["\']', html_card, re.I)


def test_generate_post_card_api():
    """Verify FastAPI endpoint for post-specific card generation and preview."""
    client = TestClient(app)
    req_payload = {
        "post_text": "Critical telemetry alert: Unauthorized lateral movement detected in OT substation segment.\n\n- Air-gap isolation engaged across all transmission nodes.\n- AES-256 encrypted logs verified.\n\nImmediate command directive enforced.",
        "title": "Tactical Advisory Post Card",
        "deliverable_type": "advisory",
        "aspect_ratio": "16:9",
        "theme": "dark",
    }

    resp = client.post("/api/v1/infographics/generate-post-card", json=req_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "card_id" in data
    assert data["card_id"].startswith("post_")
    assert data["aspect_ratio"] == "16:9"
    assert "preview_url" in data
    assert "png_download_url" in data
    assert "<!DOCTYPE html>" in data["html"]
    assert "Tactical Advisory Post Card" in data["html"]

    # Test preview retrieval
    prev_resp = client.get(data["preview_url"])
    assert prev_resp.status_code == 200
    assert prev_resp.headers["content-type"].startswith("text/html")
    assert "aiz-post-card-canvas" in prev_resp.text


def test_auto_routing_social_deliverable_to_post_card(sample_deliverable_data):
    """Verify deliverable_type='linkedin_post' automatically compiles to tailored post card."""
    sample_deliverable_data["deliverable_type"] = "linkedin_post"
    html_output = AIZInfographicEngine.render_from_deliverable(sample_deliverable_data, template="auto")

    assert "aiz-post-card-canvas" in html_output
    assert "LINKEDIN POST" in html_output
    assert "100% Grounded" in html_output


@pytest.mark.asyncio
async def test_post_card_png_render_and_export():
    """Verify high-resolution PNG generation via Playwright sync engine in asyncio thread."""
    from fastapi.testclient import TestClient
    from app.main import app

    html = AIZInfographicEngine.render_from_post(
        post_text="Executive Summary: Air-gap verification passed.\n\n- Zero leaks detected across all segments.\n- Latency measured at 12ms.\n\nReady for field deployment.",
        title="Field Deployment Ready",
        deliverable_type="linkedin_post",
        aspect_ratio="16:9",
        theme="dark",
    )

    png_bytes = await AIZInfographicEngine.render_png_bytes(html, scale=2)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 10000

    # Also test API endpoint
    client = TestClient(app)
    gen_resp = client.post("/api/v1/infographics/generate-post-card", json={
        "post_text": "Announcing our new zero-trust airgap engine!\n\n- Provenance tracing\n- Deterministic visual outputs\n\nCheck out the demo.",
        "title": "Zero-Trust Visuals",
        "deliverable_type": "twitter_thread",
        "aspect_ratio": "1:1",
    })
    assert gen_resp.status_code == 200
    card_id = gen_resp.json()["card_id"]

    png_resp = client.get(f"/api/v1/infographics/post-card-png/{card_id}")
    assert png_resp.status_code == 200
    assert png_resp.headers["content-type"] == "image/png"
    assert png_resp.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_generate_thread_cards_post_by_post():
    """Verify multi-part social sequence generates distinct, numbered cards for each tweet/post."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    thread_text = """Thread: Strategic Intelligence Mandate
Structured 4-part Twitter/X thread with strict character limits and 100% claim provenance.

Social Sequence (X/Twitter)
Verified: <= 230 characters / card
Tweet 1/4
Claim #1
1 verified citation
1/4 A person is struggling against a thick web of spiderwebs covering their face.

Tweet 2/4
Claim #2
1 verified citation
2/4 Hands reach out, fingers curled as if grasping -- visual evidence confirms entanglement and active resistance.

Tweet 3/4
Claim #3
1 verified citation
3/4 CERT Units: prioritize tactile interaction cues; no ambiguity in web density or facial entrapment.

Tweet 4/4
Claim #4
1 verified citation
4/4 Systems Engineers: model threat vectors based on visible struggle, not inferred context."""

    resp = client.post("/api/v1/infographics/generate-thread-cards", json={
        "post_text": thread_text,
        "title": "Strategic Intelligence Mandate",
        "deliverable_type": "twitter_thread",
        "aspect_ratio": "16:9",
        "theme": "dark",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cards"] == 4
    assert len(data["cards"]) == 4

    # Verify each card is unique and sequentially marked
    labels = [c["sequence_label"] for c in data["cards"]]
    assert labels == ["Tweet 1/4", "Tweet 2/4", "Tweet 3/4", "Tweet 4/4"]

    # Verify tweet 1 card
    c1 = data["cards"][0]
    assert "A person is struggling against a thick web of spiderwebs" in c1["post_text"]
    assert "aiz-badge-sequence" in c1["html"]
    assert "TWEET 1/4" in c1["html"]
    assert "aiz-takeaway-hero" in c1["html"]

    # Verify tweet 2 card
    c2 = data["cards"][1]
    assert "Hands reach out, fingers curled" in c2["post_text"]
    assert "TWEET 2/4" in c2["html"]

    # Verify tweet 3 card
    c3 = data["cards"][2]
    assert "CERT Units: prioritize tactile interaction cues" in c3["post_text"]
    assert "TWEET 3/4" in c3["html"]

    # Verify tweet 4 card
    c4 = data["cards"][3]
    assert "Systems Engineers: model threat vectors" in c4["post_text"]
    assert "TWEET 4/4" in c4["html"]

    # Verify preview and PNG retrieval for card 1
    prev_r = client.get(c1["preview_url"])
    assert prev_r.status_code == 200
    assert "TWEET 1/4" in prev_r.text

    png_r = client.get(c1["png_download_url"])
    assert png_r.status_code == 200
    assert png_r.headers["content-type"] == "image/png"
    assert png_r.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_custom_styling_options_and_rendering():
    """Verify endpoint discoverability and custom styling compilation (themes, fonts, layouts, branding)."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Verify discoverable styling options endpoint
    opts_resp = client.get("/api/v1/infographics/styling-options")
    assert opts_resp.status_code == 200
    opts = opts_resp.json()
    assert len(opts["themes"]) >= 7
    assert any(t["id"] == "midnight_navy" for t in opts["themes"])
    assert any(t["id"] == "terminal_green" for t in opts["themes"])
    assert any(t["id"] == "sunset_amber" for t in opts["themes"])
    assert any(t["id"] == "crimson_alert" for t in opts["themes"])
    assert any(t["id"] == "high_contrast" for t in opts["themes"])

    assert len(opts["fonts"]) == 3
    assert [f["id"] for f in opts["fonts"]] == ["sans", "serif", "mono"]

    assert len(opts["layouts"]) == 4
    assert [l["id"] for l in opts["layouts"]] == ["hero", "split", "technical", "minimal"]

    assert len(opts["aspect_ratios"]) == 4
    assert any(r["id"] == "9:16" for r in opts["aspect_ratios"])

    # 2. Generate customized post card with specific styling
    gen_resp = client.post("/api/v1/infographics/generate-post-card", json={
        "post_text": "Zero-trust enclave isolation active: all tactical computations locked to local hardware.",
        "title": "Tactical Defensive Protocol",
        "deliverable_type": "advisory",
        "theme": "terminal_green",
        "font_family": "mono",
        "layout_preset": "technical",
        "brand_name": "TACTICAL CERT ENCLAVE",
        "classification": "DEFCON-1 MANDATORY",
        "aspect_ratio": "9:16",
    })
    assert gen_resp.status_code == 200
    card = gen_resp.json()
    html_card = card["html"]

    # Verify customized styling tags in HTML output
    assert "aiz-theme-terminal_green" in html_card
    assert "aiz-font-mono" in html_card
    assert "aiz-layout-technical" in html_card
    assert "aiz-ratio-9-16" in html_card
    assert "TACTICAL CERT ENCLAVE" in html_card
    assert "DEFCON-1 MANDATORY" in html_card
    assert "enclave_terminal://veritas.sh" in html_card
    assert "aiz-terminal-prompt" in html_card


