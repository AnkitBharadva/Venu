# SIH26155 — GenAI Platform for Automated Content Transformation

> **Core Mandate:** Fully offline, air-gapped AI platform that ingests heterogeneous source content (PDF, DOCX, PPTX, images, video, audio) and transforms it into operator-selected deliverables with 100% claim-to-chunk provenance, tamper-evident cryptographic audit trails, and zero outbound network egress.

---

## Architecture Overview

```
                      [ OPERATOR DASHBOARD (React + Tailwind) ]
                                          │
                            Port 3000     │ (Port 80 / Nginx)
                                          ▼
                      [ FASTAPI CORE BACKEND (Air-Gapped) ]
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
      [ PostgreSQL 16 ]            [ Qdrant Vector ]         [ FalkorDB Graph ]
    - Metadata & Schemas         - Semantic Chunks         - Entity Relationships
    - Append-Only Audit Log      - Cosine Similarity       - Graph Grounding Paths
    - Hash Chaining (SHA-256)    - Grounding /trace        - Cypher Graph Engine
```

### Security & Air-Gap Non-Negotiables
1. **Zero External Network Egress:** Docker compose defines an isolated bridge network with `internal: true`. Containers have no default gateway to the internet.
2. **No Cloud Telemetry or APIs:** No OpenAI, Anthropic, or external cloud SDKs. All reasoning, embeddings, OCR, and transcription execute locally.
3. **Tamper-Evident Audit Logging:** Every operator action (upload, generate, edit, approve, export) is cryptographically chained (`hash = sha256(prev_hash + actor + action + timestamp + details)`). The Postgres `audit_log` table is guarded by database triggers preventing `UPDATE` and `DELETE`.
4. **Encryption At-Rest:** Source documents and generated deliverables are encrypted using AES-256 with keys managed locally.

---

## Local Setup

### Prerequisites
- **Docker** and **Docker Compose** (Docker Compose v2+) OR
- **Python 3.11** with Conda environment `tri` + **Node.js 20+**

---

### Option A: Standard Deployment via Docker Compose (Recommended)

1. **Clone repository and enter root:**
   ```bash
   cd D:/Venu
   ```

2. **Initialize environment variables:**
   ```bash
   cp .env.example .env
   ```

3. **Build and launch all services in air-gapped enclave:**
   ```bash
   docker compose up --build -d
   ```

4. **Verify container health:**
   ```bash
   docker compose ps
   ```
   All five containers (`genai-postgres`, `genai-qdrant`, `genai-falkordb`, `genai-backend`, `genai-frontend`) will show `healthy`.

5. **Access the Application:**
   - **Frontend Blank Dashboard:** [http://localhost:3000](http://localhost:3000)
   - **Backend Aggregate Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
   - **Backend API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs) (dev mode)
   - **Air-Gap Verification Probe:** [http://localhost:8000/health/airgap](http://localhost:8000/health/airgap)

---

### Option B: Local Native Development (Conda `tri` + Node)

1. **Activate the Conda environment:**
   ```powershell
   conda activate tri
   ```

2. **Install backend dependencies:**
   ```powershell
   pip install -r backend/requirements.txt
   ```

3. **Run backend unit & health tests:**
   ```powershell
   pytest backend/tests/ -v
   ```

4. **Run code quality checks:**
   ```powershell
   ruff check backend/
   mypy backend/app
   ```

5. **Start FastAPI Backend locally:**
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
   ```

6. **Start React Frontend locally:**
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Health Check & Egress Verification

### 1. Aggregate Health Check
```bash
curl -s http://localhost:8000/health | jq .
```
**Sample response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-09T17:15:00.000000+00:00",
  "environment": "development",
  "airgap_strict_mode": true,
  "dependencies": {
    "postgres": {
      "status": "healthy",
      "latency_ms": 1.45,
      "database": "genai_platform"
    },
    "qdrant": {
      "status": "healthy",
      "latency_ms": 2.10,
      "host": "qdrant:6333",
      "collections_count": 0
    },
    "falkordb": {
      "status": "healthy",
      "latency_ms": 0.88,
      "host": "falkordb:6379"
    }
  }
}
```

### 2. Proof of Zero Outbound Network Egress
To prove that containers cannot send telemetry or phone-home requests, verify the airgap isolation probe:
```bash
curl -s http://localhost:8000/health/airgap | jq .
```
Or execute an outbound network request directly inside any container:
```bash
docker compose exec backend curl -I --connect-timeout 2 https://google.com
```
*Result:* Returns `Failed to connect to google.com: Network is unreachable` due to the `internal: true` Docker bridge configuration.

---

## Repository Monorepo Structure

```
.
├── .github/
│   └── workflows/
│       └── ci.yml                 # CI quality pipeline (ruff, mypy, pytest, npm typecheck)
├── .env.example                   # Complete configuration variable documentation
├── .gitignore                     # Monorepo gitignore rules
├── docker-compose.yml             # Air-gapped multi-container topology
├── README.md                      # Architecture and setup guide
├── backend/                       # FastAPI Core Orchestrator
│   ├── app/
│   │   ├── api/                   # Health and monitoring routers
│   │   │   └── health.py          # /health, /health/live, /health/ready, /health/airgap
│   │   ├── core/                  # Settings, Postgres, Qdrant & FalkorDB clients
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── qdrant_client.py
│   │   │   └── falkordb_client.py
│   │   ├── models/                # SQLAlchemy ORM schemas
│   │   │   └── audit_log.py       # Source documents, audit log, deliverables
│   │   └── main.py                # FastAPI lifecycle, CORS, router mounts
│   ├── tests/                     # Pytest test suite
│   │   └── test_health.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── ruff.toml
│   └── mypy.ini
├── frontend/                      # React + TypeScript + Tailwind Operator UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── BlankDashboard.tsx # Operator dashboard skeleton (Phase 0)
│   │   │   └── ServiceStatus.tsx  # Real-time enclave dependency health card
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── Dockerfile                 # Multi-stage build with Nginx reverse proxy
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── models/                        # Air-Gapped Local Model Weight Specs & Configs
│   ├── README.md
│   ├── configs/
│   │   ├── qwen3_8b.yaml          # Reasoning LLM config
│   │   ├── qwen3_vl_4b.yaml       # Vision-Language model config
│   │   ├── whisper_medium.yaml    # Audio/Video transcription config
│   │   └── bge_small_en.yaml      # Vector embeddings model config
│   └── weights/
│       └── .gitkeep               # Mount directory for local offline weights
├── infra/                         # Service Infrastructure Configs
│   ├── postgres/
│   │   └── init.sql               # Relational metadata + append-only audit trigger
│   ├── qdrant/
│   │   └── config.yaml            # Air-gapped vector store configuration
│   └── falkordb/
│       └── README.md              # FalkorDB graph persistence guide
└── scripts/
    ├── verify_phase0.py           # Self-contained Phase 0 verification script
    ├── verify_phase1.py           # Self-contained Phase 1 ingestion verification script
    └── verify_phase2.py           # Self-contained Phase 2 understanding & chunking verification
```

---

## Phase 1 — Ingestion Pipeline API Reference

### 1. Ingest Multi-Modal Document
```bash
curl -X POST http://localhost:8000/api/v1/ingest/upload \
  -F "file=@sample_report.pdf" \
  -F "uploader_id=operator_primary"
```

**Supported Inputs & Router Dispatch:**
| Input Category | Supported Formats | Engine / Dispatch | Extracted Structure |
|---|---|---|---|
| **Plain & Markdown** | `.txt`, `.md`, `.csv`, `.json` | `TextParser` | Markdown headings, lines, word count |
| **Structured Documents** | `.pdf`, `.docx`, `.pptx` | `DoclingParser` | Page bounds, headings, tables, slides, speaker notes |
| **Images & Scans** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.tiff` | `OCRParser` (PaddleOCR) | Text lines, coordinates, confidence scores |
| **Audio & Video** | `.wav`, `.mp3`, `.m4a`, `.mp4`, `.mkv`, `.mov` | `WhisperParser` | Transcripts with second-accurate `timestamps` |

### 2. Verify AES-256 At-Rest Encryption
```bash
curl http://localhost:8000/api/v1/ingest/documents/<DOC_ID>/verify-encryption
```

### 3. Verify Tamper-Evident Audit Chain
```bash
curl http://localhost:8000/api/v1/audit/verify-chain
```

---

## Phase 2 — Understanding & Chunking Layer API Reference

### 1. Process Document Understanding & Chunking
```bash
curl -X POST http://localhost:8000/api/v1/understand/process/<DOC_ID>?actor=operator_primary
```
Triggers:
- **Semantic paragraph & section-aware chunking** preserving exact character offsets (`raw_text[start:end] == chunk.text`).
- **Entity, Topic, Intent & Sensitive Terms Extraction** (grounded in `chunk_id`s).
- **384-dimensional dense embeddings** generated via local model (`bge-small-en-v1.5` compatible).
- **Vector upsert into Qdrant** collection `source_chunks`.
- **Knowledge graph upsert into FalkorDB** (Document, Chunk, Entity, Topic nodes with Cypher relations).
- **Cryptographically chained audit event** (`process_understanding`) committed to PostgreSQL.

### 2. Retrieve Grounded Chunks with Exact Offsets
```bash
curl http://localhost:8000/api/v1/understand/documents/<DOC_ID>/chunks
```
Returns structured, addressable chunks with exact `char_offset_start`, `char_offset_end`, section `heading`, `page_number`, `timestamp_start/end`, and `offset_verified: true`.

### 3. Retrieve Document Intelligence (Objective, Topics, Entities, Sensitivities)
```bash
curl http://localhost:8000/api/v1/understand/documents/<DOC_ID>/understanding
```
Returns:
- `objective`: Extracted mission mandate or operational intent.
- `topics`: Thematic topic tags.
- `key_entities`: Categorized entity mentions (`ORGANIZATION`, `WEAPON_SYSTEM`, `LOCATION`, `TACTIC_TECHNIQUE`, `PERSON`, `DATE_TIME`) with mention counts and referencing `chunk_ids`.
- `sensitive_terms`: Advisory markers (`TOP SECRET`, `CVE-2024-XXXX`, `CBRN`, `DEFCON`) with severity ranking and referencing `chunk_ids`.
- `relationships`: Semantic relation triples with grounding `chunk_id`.

### 4. Vector Semantic Search via Qdrant
```bash
curl -X POST http://localhost:8000/api/v1/understand/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "border radar and air defense missiles", "doc_id": "<DOC_ID>", "top_k": 3}'
```
Returns ranked semantic chunks with Cosine similarity score, text span, and character offsets.

### 5. FalkorDB Knowledge Graph Query
```bash
curl http://localhost:8000/api/v1/understand/graph/entity/Rafale
```
Returns connected entity graph, relationship types (`OPERATED_BY`, `STATIONED_AT`, `DEPLOYED_WITH`), and referencing `chunk_ids`.

---

## Phase 3 — Grounding & Retrieval Service API Reference

### 1. Hybrid Vector-Graph Context Retrieval (`/retrieve`)
```bash
curl -X POST http://localhost:8000/api/v1/grounding/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "air-gapped isolated security perimeter",
    "doc_id": "<DOC_ID>",
    "top_k": 4,
    "include_graph": true,
    "alpha": 0.7
  }'
```
Merges Qdrant dense vector similarity (`alpha=0.7`) with FalkorDB openCypher entity neighborhood traversal (`1 - alpha = 0.3`). Returns ranked chunks with composite scores, entity overlaps, and aggregated context formatted with chunk headers for generation adapters.

### 2. Register Deliverable with Hard Claim-Citation Contract (`/outputs`)
```bash
curl -X POST http://localhost:8000/api/v1/grounding/outputs \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "<DOC_ID>",
    "deliverable_type": "executive_summary",
    "content": {
      "title": "Tactical Executive Briefing",
      "blocks": [{
        "block_index": 0,
        "title": "Perimeter Security",
        "sentences": [{
          "sentence_id": "sent_1",
          "sentence_index": 0,
          "text": "The platform operates in an air-gapped security perimeter with zero external network connectivity.",
          "citations": [{
            "chunk_id": "<CHUNK_ID>",
            "char_offset_start": 0,
            "char_offset_end": 105,
            "quote": "The platform operates in an air-gapped security perimeter..."
          }]
        }]
      }]
    }
  }'
```
**Hard Gatekeeper Enforcement:**
- If any sentence contains **0 citations**, the request is immediately rejected with **HTTP 422 Unprocessable Entity** (`UncitedClaimViolationError`).
- If a citation references a non-existent or foreign `chunk_id`, the request is rejected with **HTTP 422** (`InvalidCitationChunkError`).
- If quote offsets fail verbatim verification against `raw_text[start:end]`, the request is rejected with **HTTP 422** (`GroundingQuoteMismatchError`).
- On success: commits a cryptographically chained audit event (`create_grounded_deliverable`).

### 3. Sentence Provenance Trace (`/trace`)
```bash
# Trace a specific sentence
curl "http://localhost:8000/api/v1/grounding/trace?output_id=<OUTPUT_ID>&sentence_index=0"

# Trace entire deliverable (100% sentence-by-sentence coverage)
curl "http://localhost:8000/api/v1/grounding/trace/<OUTPUT_ID>/full"
```
Powers the UI **hover a sentence → see source paragraph** capability. Returns exact character offsets `[char_offset_start : char_offset_end]`, source chunk ID, section heading, page number, verbatim quote, surrounding document context (`context_before`, `context_after`), and `trace_verified: true`.

### 4. Verification Suite & Standalone Verification Runner
```powershell
# Run backend pytest suite (33 passing unit/integration tests)
conda run -n tri pytest backend/tests/ -v

# Run standalone Phase 3 verification (10 sentences across 3 deliverables)
conda run -n tri python scripts/verify_phase3.py
```

---

## Phase 4 — Output Generation Adapters API Reference

### 1. Multi-Select Deliverable Generation (`/generate`)
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "<DOC_ID>",
    "deliverable_types": [
      "linkedin_post",
      "twitter_thread",
      "executive_summary",
      "advisory",
      "presentation",
      "video_package",
      "infographic"
    ],
    "query": "air-gapped defense architecture",
    "parameters": {
      "audience": "Air Force & Cyber Command",
      "tone": "authoritative",
      "detail_level": "comprehensive"
    }
  }'
```
Retrieves grounded context **once** via hybrid Qdrant + FalkorDB search, then executes all requested adapters concurrently. Every generated sentence is linked to verified source chunks and stored in `generated_outputs` with cryptographic audit logging.

### 2. Built-in Generation Adapters (7 Formats)
| Deliverable Type | Name | Category | Specifics & Key Features |
|---|---|---|---|
| `linkedin_post` | **LinkedIn Post** | Social | Hook + Body + CTA structure with hashtag suggestions. |
| `twitter_thread` | **Twitter / X Thread** | Social | Sequential numbered tweets (`1/N`, `2/N`), strict 280-char cap. |
| `executive_summary` | **Executive Summary** | Executive | 150–300 word leadership briefing with Findings & Implications. |
| `advisory` | **Tactical Advisory** | Operational | **Safety-Critical:** Summary, Details, Risk, Actions. **Mandatory Human Review Lock** (`requires_human_review: true`, `export_locked: true`). |
| `presentation` | **Presentation Deck** | Presentation | Structured slide deck JSON (titles, bullets, speaker notes) for interactive slide preview (non-binary). |
| `video_package` | **Video Package** | Multimedia | Narration script, storyboard beats, scene descriptions, visual recommendations, timecoded SRT subtitles (explicitly non-rendered video). |
| `infographic` | **Infographic Spec** | Visual | Content blocks, layout recommendations, visual hierarchy, key metrics (explicitly non-rendered image). |

### 3. Dynamic Format Extensibility via Configuration (`/generate/adapters/register`)
Adding a new deliverable format requires **zero new code** — purely configuration:
```bash
curl -X POST http://localhost:8000/api/v1/generate/adapters/register \
  -H "Content-Type: application/json" \
  -d '{
    "deliverable_type": "tactical_flash_bulletin",
    "name": "Tactical Flash Bulletin",
    "description": "Rapid frontline intelligence alert",
    "category": "operational",
    "system_prompt_template": "Generate concise tactical bulletins with source chunk citations.",
    "block_structure": [
      {"index": 0, "title": "Immediate Threat Situation"},
      {"index": 1, "title": "Observed Asset Activity"},
      {"index": 2, "title": "Mandated Action"}
    ],
    "requires_human_review": false
  }'
```

### 4. Verification Suite & Standalone Verification Runner
```powershell
# Run complete backend pytest suite (42 passing unit & integration tests)
conda run -n tri pytest backend/tests/ -v

# Run standalone Phase 4 verification (all formats generated & traced)
conda run -n tri python scripts/verify_phase4.py
```

---

## Phase Roadmap
- **[x] Phase 0: Repo Scaffolding & Environment** — Running skeleton with all 5 services stubbed, zero egress network, health checks, CI stub.
- **[x] Phase 1: Ingestion Pipeline** — Multi-modal file router (Docling, PaddleOCR, Whisper), common SourceDocument schema, AES-256 encryption at rest, append-only tamper-evident audit logging, and low-confidence flags.
- **[x] Phase 2: Understanding & Chunking Layer** — Semantic paragraph/section-aware chunking preserving exact character offsets, entity/topic/intent/sensitive terms extraction, 384-dim dense embeddings, Qdrant vector store indexing, FalkorDB openCypher knowledge graph upsert, and claim-to-chunk provenance.
- **[x] Phase 3: Grounding & Retrieval Service** — `/retrieve` hybrid vector-graph endpoint, `/trace` sentence-level and full deliverable provenance endpoint, hard claim-citation contract gatekeeper (100% verified across 10 sentences and 3 output types), and React interactive hovercard inspector.
- **[x] Phase 4: Output Generation Adapters** — Common adapter interface, 7 modular adapters (LinkedIn, Twitter Thread, Executive Summary, Advisory, Presentation, Video Package, Infographic), dynamic config registration, multi-select concurrent generation, safety-critical human review gatekeeper, and interactive slide/storyboard/metric previews.
- **[ ] Phase 5: Security & Audit Layer** — RBAC, tamper-evident hash chain verification, network-cut live proof.
- **[ ] Phase 6: Human Review & Approval Workflow** — Draft state, sentence-level review, reviewer diff history, export lock.
- **[ ] Phase 7: Operator Dashboard** — Complete interactive React UI with hover-to-source inspection.
- **[ ] Phase 8: Testing, Hardening & Deliverables Packaging** — Architecture document, demo script, and final packaging.
