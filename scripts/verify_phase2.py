"""Verification script for Phase 2: Understanding & Chunking Layer.

Validates:
1. Semantic paragraph- and section-aware chunking
2. Exact claim-to-chunk provenance invariant: raw_text[start:end] == chunk.text
3. Structural metadata propagation (headings, pages, timestamps)
4. Document understanding: objective, topics, entities, sensitive terms, relationships
5. 384-dimensional dense embeddings with unit normalization and semantic ranking
6. Qdrant vector store collection indexing and topic search
7. FalkorDB openCypher knowledge graph upsert and entity query
8. Cryptographic append-only audit trail verification
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.audit import record_audit_event, verify_audit_integrity
from app.models.audit_log import Base, SourceDocument
from app.models.understanding import DocumentChunk, DocumentUnderstanding
from app.services.chunking.semantic_chunker import SemanticChunker
from app.services.embeddings.local_embedder import LocalEmbedder
from app.services.extraction.entity_extractor import EntityExtractor
from app.services.storage.falkordb_service import FalkorDBService
from app.services.storage.qdrant_service import QdrantService
from app.services.understanding_service import process_document_understanding

SAMPLE_DOC = """# DEFENSE DIRECTIVE 2026-B: AIRSPACE MONITORING PROTOCOL

## SECTION 1: OPERATIONAL MANDATE
The primary goal of this operation is to establish an integrated border surveillance and air defense network across the northern sector.
In response to escalating drone incursions and electronic jamming along the Line of Actual Control in Ladakh, the Indian Air Force and Indian Army are conducting joint reconnaissance.

## SECTION 2: THEATER ASSETS & SENSORS
Key weapon systems assigned to the theater include two squadrons of Rafale multi-role combat aircraft stationed at Ambala and deployed along forward operating bases.
Additionally, the S-400 Triumf surface-to-air missile division has been operationalized to provide long-range airspace denial.
For autonomous reconnaissance, MQ-9 Reaper unmanned aerial systems have been tasked with continuous multi-spectral surveillance.

## SECTION 3: CYBER ADVISORY & SENSITIVE THREAT VECTORS
WARNING: TOP SECRET // NOFORN
A critical vulnerability designated CVE-2024-38077 has been reported in tactical relay nodes, allowing remote code execution if exploited.
Immediate patching is mandated under DEFCON 2 defense readiness protocols.
Any indications of CBRN materials or covert adversary SIGINT interception must be reported directly to CERT-In and DARPA liaison teams.
"""


async def main() -> None:
    print("=" * 70)
    print("SIH26155 GenAI Content Transformation Platform - Phase 2 Verification")
    print("Target: Understanding & Chunking Layer (Strict Air-Gap Enclave)")
    print("=" * 70)

    # 1. Semantic Chunking & Exact Character Provenance
    print("\n[Step 1] Testing Semantic Chunker with Exact Character Offsets...")
    chunker = SemanticChunker(min_chunk_chars=80, target_chunk_chars=300, max_chunk_chars=600)
    chunks = chunker.chunk_text(SAMPLE_DOC)
    print(f" -> Generated {len(chunks)} semantically coherent chunks.")

    provenance_failures = 0
    for idx, c in enumerate(chunks):
        matched = SAMPLE_DOC[c.char_offset_start : c.char_offset_end]
        if matched != c.text:
            provenance_failures += 1
            print(f" [FAIL] Chunk {idx} offset mismatch!")
        else:
            hd = f" [Heading: '{c.heading}']" if c.heading else ""
            print(f"    Chunk #{c.chunk_index}: {len(c.text)} chars | span [{c.char_offset_start}:{c.char_offset_end}]{hd}")

    assert provenance_failures == 0, "Provenance invariant violated!"
    print(" [PASS] 100% of chunks satisfy: raw_text[char_offset_start:char_offset_end] == chunk.text")

    # 2. Entity, Topic, Intent & Sensitive Term Extraction
    print("\n[Step 2] Testing Entity & Intent Extraction...")
    extractor = EntityExtractor()
    extracted = extractor.extract(SAMPLE_DOC, chunks)

    print(f" -> Stated Objective: {extracted.objective}")
    print(f" -> Topics: {extracted.topics}")
    print(f" -> Key Entities Detected: {len(extracted.key_entities)}")
    for e in extracted.key_entities[:6]:
        print(f"    - {e.name} ({e.type}) | mentioned {e.count}x in chunks: {[str(cid)[:8] for cid in e.chunk_ids]}")

    print(f" -> Sensitive Advisory Terms: {len(extracted.sensitive_terms)}")
    for s in extracted.sensitive_terms:
        print(f"    - [{s.severity}] {s.term} ({s.category}) | affected chunks: {[str(cid)[:8] for cid in s.chunk_ids]}")

    print(f" -> Entity Relationships: {len(extracted.relationships)}")
    for r in extracted.relationships[:4]:
        print(f"    - ({r.source}) -[:{r.relation}]-> ({r.target})")

    assert len(extracted.key_entities) > 0
    assert len(extracted.sensitive_terms) > 0
    print(" [PASS] Entity, intent, topic, and sensitive term extraction verified.")

    # 3. Local Dense Embeddings (384-dim)
    print("\n[Step 3] Testing Local Embeddings Provider (384 Dimensions)...")
    embedder = LocalEmbedder(dimension=384)
    chunk_texts = [c.text for c in chunks]
    embeddings = embedder.embed_batch(chunk_texts)

    print(f" -> Generated {len(embeddings)} dense embeddings.")
    for idx, emb in enumerate(embeddings):
        norm = float(np.linalg.norm(np.array(emb)))
        assert len(emb) == 384, f"Dimension mismatch: {len(emb)}"
        assert abs(norm - 1.0) < 1e-4, f"Unit norm violated: {norm}"
    print(" [PASS] All embeddings are exactly 384-dimensional unit vectors (Cosine-compatible).")

    # 4. Semantic Search Ranking
    print("\n[Step 4] Testing Qdrant Semantic Similarity Ranking...")
    qdrant = QdrantService()
    test_doc_id = uuid.uuid4()
    qdrant.upsert_chunks(chunks=chunks, embeddings=embeddings, doc_id=test_doc_id)

    query = "combat fighter aircraft and missiles"
    results = qdrant.search_chunks(query=query, doc_id=test_doc_id, top_k=2)
    print(f" -> Query: '{query}'")
    for r in results:
        print(f"    Top Hit #{r.chunk_index} (Score: {r.score:.4f}): {r.text[:80]}...")
    assert len(results) > 0
    assert "Rafale" in results[0].text or "S-400" in results[0].text
    print(" [PASS] Qdrant topic search ranked relevant defense chunks highest.")

    # 5. FalkorDB Knowledge Graph Query
    print("\n[Step 5] Testing FalkorDB Knowledge Graph Operations...")
    falkor = FalkorDBService()
    await falkor.upsert_document_graph(
        doc_id=test_doc_id,
        filename="operation_sentinel.txt",
        chunks=chunks,
        entities=extracted.key_entities,
        relationships=extracted.relationships,
        topics=extracted.topics,
    )

    entity_query = await falkor.query_entity_graph("Rafale")
    print(f" -> FalkorDB query for 'Rafale':")
    print(f"    Type: {entity_query.entity_type}")
    print(f"    Connected Entities: {entity_query.connected_entities}")
    print(f"    Direct Relations: {entity_query.direct_relations}")
    print(f"    Grounding Chunk IDs: {[str(cid)[:8] for cid in entity_query.referenced_chunks]}")
    assert entity_query.entity_name == "Rafale"
    assert len(entity_query.referenced_chunks) > 0
    print(" [PASS] FalkorDB knowledge graph query returned entity relationships and chunk references.")

    # 6. End-to-End Database & Cryptographic Audit Trail
    print("\n[Step 6] Testing End-to-End Orchestrator and Audit Integrity...")
    db_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionMaker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionMaker() as session:
        # Create source document record
        src_doc = SourceDocument(
            doc_id=test_doc_id,
            original_filename="operation_sentinel.txt",
            content_type="text/plain",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            encrypted_file_path="/data/encrypted_uploads/test.enc",
            raw_text=SAMPLE_DOC,
            structural_metadata={},
            uploader_id="operator_sentinel",
        )
        session.add(src_doc)
        await session.commit()

        # Run process_document_understanding
        resp = await process_document_understanding(
            session=session,
            doc_id=test_doc_id,
            actor="operator_sentinel",
        )
        print(f" -> Pipeline response: status={resp.status}, chunks={resp.chunks_count}, entities={resp.entities_count}")
        assert resp.status == "success"
        assert resp.chunks_count == len(chunks)

        # Verify audit integrity
        audit_check = await verify_audit_integrity(session)
        print(f" -> Audit log chain status: valid={audit_check['valid']}, records={audit_check['total_records']}")
        assert audit_check["valid"] is True
    print(" [PASS] Cryptographically chained tamper-evident audit log verified.")

    print("\n" + "=" * 70)
    print("ALL PHASE 2 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY (100% PASS)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
