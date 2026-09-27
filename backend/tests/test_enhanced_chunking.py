"""Comprehensive verification test suite for the enhanced Semantic Chunker.

Verifies:
1. Markdown table integrity: tables are never split mid-row or across chunks.
2. Code block integrity: fenced code blocks remain atomic.
3. Bullet and numbered list integrity: lists remain unified and items are never split mid-sentence.
4. Universal heading extraction:
   - Markdown headings (# H1, ## H2)
   - Numbered outline headings (1.1 Title, Section 1: Title)
   - All-caps standalone headings (AIR-GAP DEFENSE DIRECTIVE 2026)
5. Syntactic sentence boundary safety:
   - Prevents false splits on decimals (v3.11, 3.14)
   - Prevents false splits on abbreviations (e.g., i.e., Dr., etc.)
   - Prevents false splits on citations ([1], [12]) and technical identifiers (CVE-2024-38077).
6. Strict 100% claim-to-chunk provenance invariant:
   raw_text[chunk.char_offset_start:chunk.char_offset_end] == chunk.text
"""

from app.services.chunking.semantic_chunker import SemanticChunker
from app.services.embeddings.local_embedder import get_local_embedder


def test_markdown_table_atomic_preservation():
    """Verify markdown tables remain 100% intact as single atomic chunks."""
    text = (
        "# Security Architecture Review\n\n"
        "The following matrix outlines component isolation requirements:\n\n"
        "| Component | Standard | Enforcement | Status |\n"
        "|---|---|---|---|\n"
        "| Edge Relay | MIL-STD-810H | Hardware Air-Gap | Compliant |\n"
        "| Storage Enclave | AES-256-GCM | Ephemeral Keys | Active |\n"
        "| Ingestion Gateway | Docling Parser | Density Filtering | Verified |\n"
        "| Cryptographic Audit | SHA-256 Chain | Append-Only | Healthy |\n\n"
        "End of specification summary."
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_text(text)

    # Find chunk containing the table
    table_chunks = [c for c in chunks if c.metadata.get("is_table")]
    assert len(table_chunks) == 1, "The entire table must be contained in exactly 1 chunk"

    tbl_chunk = table_chunks[0]
    assert "| Edge Relay |" in tbl_chunk.text
    assert "| Cryptographic Audit |" in tbl_chunk.text
    assert tbl_chunk.verify_provenance(text) is True


def test_code_block_atomic_preservation():
    """Verify fenced code blocks remain 100% intact as atomic units."""
    text = (
        "## Setup Procedure\n\n"
        "Execute the following deployment command:\n\n"
        "```bash\n"
        "# Launch local air-gapped stack\n"
        "docker compose -f docker-compose.yml up -d\n"
        "curl http://localhost:8001/health\n"
        "```\n\n"
        "Ensure all containers return healthy before continuing."
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_text(text)

    code_chunks = [c for c in chunks if c.metadata.get("is_code")]
    assert len(code_chunks) == 1, "Code block must be preserved as an atomic chunk"
    assert "docker compose" in code_chunks[0].text
    assert code_chunks[0].verify_provenance(text) is True


def test_procedural_list_preservation():
    """Verify bulleted and numbered lists are kept intact without mid-item fragmentation."""
    text = (
        "### Mandatory Operational Procedures\n\n"
        "All operators must adhere strictly to the following checklist:\n\n"
        "- Step 1: Verify hardware air-gap cable disconnection.\n"
        "- Step 2: Validate local SHA-256 audit log integrity at /api/v1/audit/verify-chain.\n"
        "- Step 3: Ensure human reviewer sign-off prior to releasing draft outputs.\n"
        "- Step 4: Verify zero active telemetry connections on port 8001.\n\n"
        "Non-compliance results in immediate access revocation."
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_text(text)

    list_chunks = [c for c in chunks if c.metadata.get("is_list")]
    assert len(list_chunks) >= 1
    assert "Step 1" in list_chunks[0].text
    assert "Step 4" in list_chunks[0].text
    assert list_chunks[0].verify_provenance(text) is True


def test_universal_heading_extraction():
    """Verify chunker detects all-caps, outline, and markdown headings."""
    text = (
        "DEFENSE READINESS DIRECTIVE 2026\n\n"
        "1.1 PERIMETER BOUNDARIES\n"
        "Perimeter networks must operate under strict electromagnetic shielding.\n\n"
        "SECTION 2: CRYPTOGRAPHIC ISOLATION\n"
        "All cryptographic keys must remain within local HSM modules.\n\n"
        "## Section 3: Summary\n"
        "Final operational notes."
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_text(text)

    headings_found = [c.heading for c in chunks if c.heading]
    assert any("DEFENSE READINESS DIRECTIVE 2026" in h for h in headings_found)
    assert any("1.1 PERIMETER BOUNDARIES" in h for h in headings_found)
    assert any("SECTION 2: CRYPTOGRAPHIC ISOLATION" in h for h in headings_found)
    assert any("Section 3" in h for h in headings_found)

    for c in chunks:
        assert c.verify_provenance(text) is True


def test_syntactic_sentence_boundary_safety():
    """Verify sentence tokenizer does not falsely split on decimals, abbreviations, or citations."""
    text = (
        "### System Specifications\n\n"
        "The tactical gateway is running firmware v3.11 with Python 3.11.15 compatibility. "
        "For example, e.g., tactical relays running under DEFCON-2 must not drop packets. "
        "As noted in technical bulletin [1], Dr. Watson confirmed CVE-2024-38077 affects nodes. "
        "All updates must be applied immediately to avoid compromise."
    )

    chunker = SemanticChunker(target_chunk_chars=200, max_chunk_chars=350)
    chunks = chunker.chunk_text(text)

    # Ensure no chunk ends or starts with awkward partial token like "11." or "g.,"
    for c in chunks:
        assert not c.text.startswith("11")
        assert not c.text.startswith("g.,")
        assert not c.text.startswith("Watson")
        assert c.verify_provenance(text) is True


def test_embedding_breakpoint_detection():
    """Verify that LocalEmbedder provides neural semantic distance breakpoints on narrative text."""
    embedder = get_local_embedder()
    chunker = SemanticChunker(
        target_chunk_chars=250,
        max_chunk_chars=500,
        embedder=embedder,
        use_semantic_breakpoints=True,
    )

    narrative = (
        "The integrated air defense network coordinates radar installations across northern mountain passes. "
        "Early warning radars continuously sweep the airspace to detect low-altitude unmanned aerial targets. "
        "Meanwhile, cryptographic key distribution protocols govern authenticated tactical communication relays. "
        "Hardware security modules strictly enforce local key derivation functions with zero network egress. "
        "Finally, supply chain logistics and field maintenance depots receive weekly supply consignments."
    )

    chunks = chunker.chunk_text(narrative)
    assert len(chunks) >= 2, "Semantic distance should subdivide divergent narrative topics"
    for c in chunks:
        assert c.verify_provenance(narrative) is True
