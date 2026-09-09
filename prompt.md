# SIH26155 — GenAI Platform for Automated Content Transformation
## Build Prompt for Antigravity (Phase-by-Phase)


**Core Mandate:** Fully offline, air-gapped-capable AI system that ingests heterogeneous source content (text, docs, images, video/audio) and transforms it into operator-selected deliverables (LinkedIn post, Twitter/X thread, Advisory, Infographic brief, Executive Summary, Presentation, Video package), with every generated claim traceable back to its source span, every action logged, and no external network calls at inference time.

**Non-negotiable constraints for every phase below:**
- No internet calls at runtime (no OpenAI/Anthropic/Google API keys, no telemetry SDKs, no CDN fetches in the app itself).
- Every LLM-generated claim must carry a pointer back to the source chunk/span it came from.
- Every operator action (upload, generate, edit, approve, export) is written to an append-only audit log.
- Uploaded source content and generated outputs are encrypted at rest.
- Nothing is marked "final"/exportable without an explicit human-review approval step.

---

## Tech Stack (finalized — resolve ambiguity before Phase 0)

| Layer | Component | Notes |
|---|---|---|
| Reasoning LLM | Qwen3-8B or Qwen3-14B via Ollama/vLLM | Pick based on demo GPU; do not promise 32B+ you can't run live |
| Vision-language | Qwen3-VL-4B | Image/slide/infographic understanding |
| ASR (dev) | Whisper medium.en | Local, CPU/GPU both viable |
| ASR (deploy target) | NVIDIA Canary-Qwen 2.5B | Only if deployment GPU confirmed; otherwise standardize on Whisper everywhere and drop this from the pitch |
| Document parsing | Docling | Structured PDF/DOCX/PPTX layout extraction |
| OCR | PaddleOCR | Scanned documents, images with embedded text |
| Vector store | Qdrant | Semantic retrieval / grounding |
| Graph store | FalkorDB | Entity-relationship grounding, cross-document linking |
| Orchestration | Python (FastAPI backend) | |
| Frontend | React + Tailwind | Operator dashboard |

**Before Phase 0:** confirm actual demo hardware (GPU model + VRAM). This decides your final model sizes. Don't build against a spec you can't demo live.

---

## Phase 0 — Repo Scaffolding & Environment

**Goal:** A running skeleton with all services stubbed, before any real logic.

**Tasks:**
1. Monorepo structure: `/backend` (FastAPI), `/frontend` (React), `/models` (local model configs/weights refs), `/infra` (docker-compose for Qdrant, FalkorDB, Postgres).
2. `docker-compose.yml` bringing up: Postgres (metadata + audit log), Qdrant, FalkorDB, backend, frontend. No external network egress in any container.
3. Health-check endpoint per service.
4. `.env.example` documenting every config var — no secrets committed.
5. CI stub (lint + type check) — optional but adds polish points.

**Acceptance criteria:** `docker-compose up` brings up all services; frontend loads a blank dashboard; backend `/health` returns 200 for every dependency (DB, Qdrant, FalkorDB) with zero outbound network calls (verify with `docker network` isolation or a firewall rule during test).

**Deliverable checkpoint:** commit + short README section "Local Setup."

---

## Phase 1 — Ingestion Pipeline

**Goal:** Accept any supported source type and normalize it into clean text + metadata.

**Inputs supported:** plain text, PDF, DOCX, PPTX, images (PNG/JPG/scanned PDF), audio/video files.

**Tasks:**
1. File-type router in backend: dispatches to Docling (structured docs), PaddleOCR (scanned/image), Whisper (audio/video → transcript).
2. Normalize every input into a common `SourceDocument` schema: `{doc_id, original_filename, content_type, raw_text, structural_metadata (headings/pages/timestamps), upload_timestamp, uploader_id, checksum}`.
3. Encrypt the raw uploaded file at rest (AES-256, key from local KMS/env — never hardcoded) before writing to disk.
4. Write an audit log entry on every upload: `{actor, action:"upload", doc_id, timestamp, source_hash}`.
5. Error handling: corrupt files, unsupported formats, OCR/ASR low-confidence flags surfaced to operator rather than silently guessed.

**Acceptance criteria:** upload each supported file type through the API, get back a normalized `SourceDocument` JSON with readable extracted text; audit log has one row per upload; original file is unreadable without the decryption key when inspected directly on disk.

---

## Phase 2 — Understanding & Chunking Layer

**Goal:** Turn raw normalized text into structured, addressable units for grounding.

**Tasks:**
1. Chunk `raw_text` into semantically coherent spans (e.g. paragraph/section-aware, not fixed-token blind splitting) — preserve `char_offset_start/end` and structural metadata (page, heading, timestamp for video) per chunk.
2. Run entity/intent extraction over the full document using the reasoning LLM: extract key entities, topics, stated objective/intent, sensitive terms (for advisory-type inputs).
3. Generate embeddings per chunk (use a local embedding model compatible with Qdrant — e.g. a small open embedding model served alongside Qwen3).
4. Upsert chunks + embeddings into Qdrant, keyed by `doc_id` + `chunk_id`.
5. Upsert extracted entities + relationships into FalkorDB (entity nodes, co-occurrence/relationship edges, linked back to `chunk_id`).

**Acceptance criteria:** for a sample document, querying Qdrant by a topic returns the correct chunks; querying FalkorDB for an entity returns its relationships and the chunks it appears in; every chunk has a stored offset that maps back exactly into the original text.

---

## Phase 3 — Grounding & Retrieval Service

**Goal:** A reusable service that any output-generation adapter calls to fetch grounded context, and that the UI calls to resolve "why did it say this" queries.

**Tasks:**
1. `/retrieve` endpoint: given a query/topic + doc_id, returns top-k relevant chunks (Qdrant) + related entities (FalkorDB), merged and ranked.
2. `/trace` endpoint: given a `(output_id, sentence_index)`, returns the source chunk(s) and offsets that sentence was generated from. This is the backbone of the "hover a sentence → see source paragraph" UI feature.
3. Enforce that generation adapters (Phase 4) cannot emit a claim without an associated chunk citation — this is a hard contract, not optional metadata.

**Acceptance criteria:** for any generated sentence in any output type, `/trace` resolves to a real, correct span in the original source document. Build a test set of 10 sentences across 3 output types and manually verify all 10 trace correctly.

---

## Phase 4 — Output Generation Adapters

**Goal:** One modular adapter per deliverable type, sharing a common interface, so adding a new format later is config, not new code.

**Common adapter interface:**
```
generate(source_doc_id, retrieved_context, params: {audience, tone, language, detail_level, objective, style}) 
  -> { content, citations: [{sentence_id, chunk_id, offset}], format_metadata }
```

**Adapters to build (in priority order for demo impact):**
1. **LinkedIn Post** — professional tone, hook + body + CTA, hashtag suggestions.
2. **Twitter/X Thread** — char-limited, thread-numbered, hook-first tweet.
3. **Executive Summary** — 150–300 word briefing, key findings + implications.
4. **Advisory** — structured sections (Summary, Details, Risk/Impact, Recommended Actions), most safety-critical → route through mandatory human review before export (see Phase 6).
5. **Presentation** — slide titles + bullet content + speaker notes (JSON structure the frontend renders as a slide preview; not a rendered .pptx unless time permits).
6. **Video Package** — script, storyboard beats, scene descriptions, narration text, subtitle (SRT-style) text, visual recommendations. Explicitly NOT a rendered video file — matches the spec wording exactly.
7. **Infographic** — content blocks + layout recommendations + key messaging hierarchy. Explicitly NOT a rendered image.

**Tasks per adapter:**
- Prompt template with strict system instructions: "only state facts present in the provided context; every sentence must map to a provided chunk_id."
- Post-generation citation-linking pass (map each output sentence back to the chunk(s) it drew from — can be done via the reasoning LLM re-checking its own output, or a lighter-weight semantic similarity match against the retrieved chunks).
- Multi-select support: if operator selects multiple formats, run adapters in parallel/sequence against the same retrieved context and return all outputs together.

**Acceptance criteria:** submit one source document, select 3+ output types, get back correctly formatted content for each with citations resolvable via `/trace`.

---

## Phase 5 — Security & Audit Layer

**Goal:** Make the "defence-level" claim demonstrable, not just asserted in the README.

**Tasks:**
1. RBAC: at minimum `operator` (upload, generate, request approval) and `reviewer/approver` (approve/reject, export) roles.
2. Append-only audit table: every upload, generation request, edit, approval, rejection, export logged with actor, timestamp, doc_id/output_id, action, and a hash chain (each row includes hash of previous row) so tampering is detectable.
3. Encryption at rest confirmed for both source uploads (Phase 1) and generated outputs.
4. Network isolation proof: a documented test where the container network is cut and the full pipeline (ingest → generate → trace) still completes successfully. Capture this as part of your demo video.
5. No third-party SDK in the dependency tree that performs outbound calls (audit `requirements.txt`/`package.json` — document this explicitly in the architecture doc).

**Acceptance criteria:** audit log shows a complete, tamper-evident trail for a full demo session; RBAC blocks an `operator` role from calling the approve/export endpoint; pipeline demonstrably works with network disabled.

---

## Phase 6 — Human Review & Approval Workflow

**Goal:** No output leaves the system without a human checkpoint — critical for advisory/threat-intel-adjacent content, and it's also your hallucination safety net.

**Tasks:**
1. Generated outputs start in status `draft`.
2. Reviewer UI: view output alongside its citations (hover-to-source), accept/edit/reject per section or per sentence.
3. `approve` transitions status to `final` and is the only status that unlocks export.
4. Any edit made by the reviewer is diffed and stored (don't silently overwrite — audit trail needs the "before" state too).
5. Export endpoint only serves `final` status outputs.

**Acceptance criteria:** attempting to export a `draft` output fails with a clear error; approving via the reviewer role transitions status and unlocks export; edits are visible in an audit/history view.

---

## Phase 7 — Operator Dashboard (Frontend)

**Goal:** The demo-facing surface. This is what judges actually watch.

**Tasks:**
1. Upload screen: drag-drop, file-type detection feedback, upload progress.
2. Output-type selector: multi-select checkboxes for all 7 formats, plus parameter controls (audience, tone, language, detail level, objective, style) as a config panel.
3. Generation results view: tabbed per output type, with inline citation highlighting — hovering/clicking a sentence shows the source paragraph/timestamp in a side panel (calls `/trace`).
4. Reviewer view (Phase 6 UI) accessible to `reviewer` role.
5. Audit log viewer (at least a simple filterable table) — useful for both the demo ("look, full traceability") and judge scrutiny.
6. A visible "Offline Mode: Active" indicator with the network-isolation proof surfaced somewhere in the UI — make the security story visual, not just documented.

**Acceptance criteria:** a judge can walk through the full flow — upload → select formats → generate → hover for source → approve → export — without touching the API directly.

---

## Phase 8 — Testing, Hardening & Deliverable Packaging

**Goal:** Meet every item in "Expected Solution/Deliverables for Evaluation" exactly.

**Tasks:**
1. End-to-end test pass across all 7 output types × at least 3 different source document types (a scanned PDF, a clean DOCX report, a short video clip).
2. Load/latency sanity check — know your generation time per format so you're not surprised live.
3. **Source Code:** clean repo, tagged release, pushed to GitHub/Drive as required.
4. **README:** setup instructions that actually work from a clean machine (test this literally — clone fresh, follow your own README, time it).
5. **Architecture Document (max 2 pages):** the pipeline diagram, tech stack table above, the grounding/traceability explanation, and the security envelope bullet list — this is your differentiation section, don't bury it.
6. **Demo Video (max 2 minutes):** script it tightly — suggested beats: (1) upload a real-world-ish document, (2) select 2–3 formats, (3) show generated output, (4) hover a sentence to show source traceability, (5) show the network-off proof, (6) show approval/export. That's your 2 minutes.
7. **Technical Presentation (max 5 slides):** Problem → Architecture (the diagram) → Security/Grounding differentiators → Tech stack → Impact/scalability (modular adapter story).

**Acceptance criteria:** all 5 deliverables exist, are internally consistent with each other (same architecture diagram everywhere, same numbers), and the README setup has been verified on a clean environment.

---

## Notes for whoever is prompting Antigravity phase-by-phase

- Feed one phase at a time as a separate task/session where possible — each phase has its own acceptance criteria, use them as the definition of done before moving on.
- Resolve the ASR duplication (Whisper vs Canary-Qwen) and the "Qwen 3.8 27b" model-size ambiguity in the stack table *before* Phase 0 — don't let the agent guess.
- Phase 3 (grounding/trace) is your single highest-leverage feature for judging — do not let time pressure cut it short in favor of adding more output-format adapters. Fewer formats with airtight traceability beats seven formats with none.
- Keep a running note of anything you *claim* in the architecture doc that isn't actually implemented — judges cross-check this against the demo.