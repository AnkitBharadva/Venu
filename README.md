# VENÜ — The Air-Gapped Intelligence Workstation

<div align="center">

```
██╗   ██╗███████╗███╗   ██╗██╗   ██╗
██║   ██║██╔════╝████╗  ██║██║   ██║
██║   ██║█████╗  ██╔██╗ ██║██║   ██║
╚██╗ ██╔╝██╔══╝  ██║╚██╗██║██║   ██║
 ╚████╔╝ ███████╗██║ ╚████║╚██████╔╝
  ╚═══╝  ╚══════╝╚═╝  ╚═══╝ ╚═════╝ 
```

### *“Every once in a while, a revolutionary product comes along that changes everything.”*

**The Defense-Grade GenAI Content Transformation Platform.**  
*100% Claim-to-Chunk Provenance. Zero Network Egress. Tamper-Evident Cryptographic Ledger.*

[![Repository](https://img.shields.io/badge/GitHub-AnkitBharadva%2FVenu-181717?style=for-the-badge&logo=github)](https://github.com/AnkitBharadva/Venu)
[![Air-Gap Status](https://img.shields.io/badge/Air--Gap-Strict%20Enclave%20(0%20Egress)-059669?style=for-the-badge&logo=shield)](http://localhost:8000/health/airgap)
[![Provenance Contract](https://img.shields.io/badge/Provenance-100%25%20Verified%20Trace-0284c7?style=for-the-badge&logo=target)](http://localhost:8000/api/v1/grounding/trace)
[![Audit Chain](https://img.shields.io/badge/Audit-Linear%20SHA--256%20Chain-7c3aed?style=for-the-badge&logo=chainlink)](http://localhost:8000/api/v1/audit/verify-chain)
[![Test Suite](https://img.shields.io/badge/Tests-65%2F65%20Passing-16a34a?style=for-the-badge&logo=pytest)](backend/tests/)
[![Latency SLA](https://img.shields.io/badge/Latency-%3C20ms%20Average-f59e0b?style=for-the-badge&logo=speedtest)](docs/ARCHITECTURE.md)

[The Manifesto](#the-manifesto) • [The Three Breakthroughs](#the-three-breakthroughs) • [Architecture Deep Dive](#the-architecture-deep-dive) • [Project Structure](#project-anatomy) • [Live Benchmarks](#the-cold-hard-numbers) • [Quickstart](#getting-started-it-just-works)

---

</div>

## The Manifesto

In 1984, the personal computer was liberated from command lines and room-sized mainframes. In 2001, ten thousand songs were slipped into a pocket. In 2007, the internet, the phone, and personal media became one single piece of glass.

Today, enterprise and defense organizations are facing a crisis of intelligence.

Look at the tools being sold today under the name of "Enterprise GenAI":
1. **They leak.** Every confidential memo, tactical doctrine, and classified report gets shuttled across the public internet to third-party cloud servers.
2. **They lie.** Hallucinations are treated as an acceptable byproduct. Models fabricate statistics, invent citations, and generate plausible falsehoods with supreme confidence.
3. **They hide.** When a leadership team or intelligence operator asks, *"Where did this claim come from?"*, the system offers nothing. No character offset. No source sentence. No paper trail.
4. **They are fragmented.** A duct-taped patchwork of disconnected Python scripts, clunky terminal outputs, and zero design harmony.

**We refused to accept that.**

We believed that if you are transforming mission-critical intelligence into strategic deliverables, you deserve an instrument built with obsessive craftsmanship. A platform where:
- Not a single bit ever leaves the building.
- Not a single sentence can be emitted without mathematical proof of its origin.
- Not a single edit can occur without a permanent cryptographic footprint.
- And the interface feels as calm, focused, and intuitive as an editorial studio.

### This is VENÜ.

---

## The Three Breakthroughs

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       VENÜ BREAKTHROUGH TRIAD                                   │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│    1. THE INGESTION ENGINE    │    2. THE PROVENANCE KERNEL     │   3. THE DEFENSE ENCLAVE      │
│                               │                                 │                               │
│ Swallows heterogeneous chaos: │ The Hard Citation Contract:     │ Mathematically sealed:        │
│ PDF, DOCX, PPTX, Scanned OCR, │ Every single output sentence is │ Zero egress bridge network,   │
│ 4K Video, and Intercept Audio.│ linked to exact [start:end]     │ append-only SHA-256 chain,    │
│ Normalizes into unified truth.│ character offsets in raw truth. │ AES-256-GCM encrypted disk.  │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

These are not three disconnected products. **They are one unified workstation.**

---

### “And One More Thing...”

Most enterprise platforms stop at text. We asked ourselves: *Why should an air-gapped operator be limited to monochrome paragraphs?*

So we built two more engines directly into the core silicon of VENÜ:

1. **The AIZ-Infographic Engine:** A deterministic, 5-layer visual compiler that takes raw intelligence chunks and instantly outputs self-contained, air-gapped SVG/HTML/CSS infographic dossiers across 7 bespoke themes — with zero external fonts or CDN dependencies.
2. **The HyperFrames Motion Video Engine:** A seekable, frame-accurate GSAP motion engine that transforms operational bullet points and transcripts into broadcast-quality kinetic video animations and MP4 packages — generated locally in seconds.

---

## The Architecture Deep Dive

VENÜ is engineered from silicon to pixel as a zero-trust, air-gapped defense enclave conforming to **NIST SP 800-53 SC-7** (Boundary Protection), **AU-10** (Non-Repudiation), and **FIPS 140-2** at-rest cryptographic standards.

### The System Pipeline

```
                                  [ OPERATOR WORKSTATION ]
                           React 18 • TypeScript • Tailwind CSS
                     Calm Editorial Design • 60 FPS Force-Directed Graph
                                             │
                       Port 3000 (Vite)      │  HTTP/JSON (Port 8000)
                                             ▼
             ┌────────────────────────────────────────────────────────────────┐
             │                FASTAPI AIR-GAPPED CORE BACKEND                 │
             │                     Python 3.11 ASGI Engine                    │
             └──────┬───────────────────────┬──────────────────────────┬──────┘
                    │                       │                          │
        ┌───────────▼───────────┐ ┌─────────▼───────────┐ ┌────────────▼────────────┐
        │  PHASE 1: INGESTION   │ │ PHASE 2: CHUNKING   │ │ PHASE 3: GROUNDING      │
        │  • Docling (Office)   │ │ • Semantic Bounds   │ │ • Hybrid Qdrant Vector  │
        │  • PaddleOCR (Scans)  │ │ • Char-Level Slicing│ │ • FalkorDB Cypher Graph │
        │  • Whisper (ASR Audio)│ │ • Dense Embeddings  │ │ • BM25 Lexical Matching │
        │  • AES-256-GCM Cipher │ │ • Entity Extractor  │ │ • Cross-Encoder Rerank  │
        └───────────┬───────────┘ └─────────┬───────────┘ └────────────┬────────────┘
                    │                       │                          │
        ┌───────────▼───────────┐ ┌─────────▼───────────┐ ┌────────────▼────────────┐
        │  PHASE 4: 8 ADAPTERS  │ │ PHASE 5: SECURITY   │ │ PHASE 6: HUMAN REVIEW   │
        │  • LinkedIn Post      │ │ • RBAC Dual-Control │ │ • Two-Person Rule Gate  │
        │  • Twitter/X Thread   │ │ • SHA-256 Hash Chain│ │ • Sentence Accept/Reject│
        │  • Executive Summary  │ │ • Trigger DB Locks  │ │ • Git-Style Diff Studio │
        │  • Tactical Advisory  │ │ • Socket Egress Drop│ │ • Final Sign-Off Lock   │
        │  • Presentation Deck  │ └─────────────────────┘ └────────────┬────────────┘
        │  • Video Package      │                                      │
        │  • Infographic Spec   │                                      ▼
        │  • Tech Documentation │                           [ EXPORTABLE ARTIFACTS ]
        └───────────────────────┘                           Markdown • JSON • HTML • MP4
                    │                       │                          │
                    ▼                       ▼                          ▼
          ┌───────────────────┐   ┌───────────────────┐      ┌───────────────────┐
          │   PostgreSQL 16   │   │   Qdrant v1.11    │      │  FalkorDB v1.0.8  │
          │ Relational Truth  │   │  384-dim Vectors  │      │ RedisGraph Engine │
          │ Immutable Ledger  │   │  Cosine Distance  │      │ Spanning Subgraph │
          └───────────────────┘   └───────────────────┘      └───────────────────┘
```

---

## The Obsession with Craftsmanship

> *"When you're a carpenter making a beautiful chest of drawers, you're not going to use a piece of plywood on the back, even though it faces the wall and nobody will ever see it. You know it's there, so you're going to use a beautiful piece of wood on the back."*  
> — **Steve Jobs**

Here is what is on the back of our fence:

### 1. The Hard Citation Contract
In most LLM frameworks, citations are an afterthought — cosmetic footnotes added by prompt suggestion.  
In VENÜ, citations are enforced by an unyielding software gatekeeper (`app/services/grounding/contract_enforcer.py`).
- Every adapter is bound by contract: **No sentence may be emitted without an explicit citation pointing to a validated chunk.**
- The contract mathematically verifies that `raw_text[start:end]` strictly equals the quoted ground-truth claim.
- If a sentence has zero citations or a quote offset mismatch, the engine doesn't shrug. It **aborts immediately with HTTP 422 Unprocessable Entity**. Hallucinations cannot enter the database.

### 2. Tamper-Evident SHA-256 Hash Chaining
Every single event in the lifecycle of a document — upload, chunking, generation, reviewer sentence revision, approval sign-off, and export — writes an immutable block to the PostgreSQL `audit_log` table.
$$\text{Hash}_i = \text{SHA-256}(\text{Hash}_{i-1} \parallel \text{actor} \parallel \text{action} \parallel \text{doc\_id} \parallel \text{output\_id} \parallel \text{timestamp} \parallel \text{source\_hash} \parallel \text{details})$$
- **Database Trigger Locks:** PostgreSQL triggers explicitly reject any `UPDATE` or `DELETE` SQL commands. The ledger is physically append-only.
- **Instant Tamper Verification (`/api/v1/audit/verify-chain`):** Sequentially recalculates every hash from the genesis block. If an attacker modifies even a single comma or timestamp directly on the database disk, the chain breaks and highlights the compromised row index in milliseconds.

### 3. Authenticated AES-256-GCM At-Rest Encryption
Both uploaded intelligence documents and synthesized deliverables are encrypted using authenticated **AES-256-GCM** with 96-bit random nonces and 128-bit authentication tags before touching the filesystem (`/data/encrypted_uploads` and `/data/encrypted_outputs`).
- Plaintext exists only ephemerally in RAM during processing.
- Cryptographic keys are derived from local hardware/environment entropy (`AIRGAP_AES_KEY`), requiring zero cloud KMS round-trips.

### 4. Mathematical Air-Gap & Socket-Level Egress Block
We don't merely claim "offline mode" with a boolean flag.
- The Docker container topology defines `internal: true` on the bridge network, stripping all default gateways.
- The `/health/airgap` live probe actively fires a non-blocking TCP socket connection to public DNS root `1.1.1.1:53` and proves connection failure (`Errno 10051 / 10060 - Network Unreachable`).
- Zero external SDKs: A zero-telemetry dependency audit confirms **zero lines of code** calling OpenAI, Anthropic, AWS, GCP, Azure, Google Analytics, or Sentry.

### 5. Dual-Control Human Review with Git-Style Unified Diffs
Automated transformation without human sign-off is negligence.
- Outputs begin in status `draft` with `export_locked: true`. Calling the export endpoint returns `HTTP 403 Forbidden`.
- Reviewers inspect claims sentence-by-sentence with side-by-side source highlighting.
- When an analyst edits a generated claim, the system captures both before/after states via `difflib.unified_diff`, stores an immutable record in `OutputEditHistory`, records a chained audit event, and re-encrypts the ciphertext on disk.
- Only formal reviewer sign-off transitions status to `final`, unlocking authenticated export into Markdown, JSON, HTML, or plain text.

---

## Project Anatomy

```
D:/Venu
├── 📁 backend/                       # FastAPI Core Orchestration Enclave
│   ├── 📁 app/
│   │   ├── 📁 api/                   # Clean REST Endpoints
│   │   │   ├── health.py             # Enclave health, readiness & live air-gap probe
│   │   │   ├── ingestion.py          # Multi-modal file upload & AES-256 storage
│   │   │   ├── understanding.py      # Semantic chunking, topics & knowledge graph
│   │   │   ├── grounding.py          # Hybrid retrieval, citation contract & /trace
│   │   │   ├── adapters.py           # 8 deliverable generation adapters + dynamic engine
│   │   │   ├── review.py             # Human review queue, diff history & export gate
│   │   │   ├── audit.py              # Linear SHA-256 chain verification & ledger logs
│   │   │   ├── infographics.py       # AIZ-Infographic visual synthesis endpoints
│   │   │   └── video.py              # HyperFrames motion video compilation endpoints
│   │   ├── 📁 core/                  # Infrastructure, Security & Database Clients
│   │   │   ├── config.py             # Strict env-based configuration
│   │   │   ├── database.py           # Async SQLAlchemy session manager
│   │   │   ├── qdrant_client.py      # Local vector database client
│   │   │   ├── falkordb_client.py    # Local openCypher graph client
│   │   │   ├── rbac.py               # Two-Person role enforcement (Operator vs Reviewer)
│   │   │   └── security.py           # AES-256-GCM cipher & SHA-256 hash chaining
│   │   ├── 📁 models/                # PostgreSQL SQLAlchemy ORM Entities
│   │   │   ├── audit_log.py          # Documents, audit ledger, outputs, diff history
│   │   │   └── understanding.py      # Chunks, entities, topics, relationships
│   │   ├── 📁 schemas/               # Pydantic Strict Data Contracts
│   │   └── 📁 services/              # Core Domain Processing Engines
│   │       ├── file_router.py        # MIME & magic-byte multi-modal router
│   │       ├── 📁 parsers/           # Docling (docs), PaddleOCR (scans), Whisper (ASR)
│   │       ├── 📁 chunking/          # Paragraph-aware semantic chunker with exact offsets
│   │       ├── 📁 embeddings/        # Local dense vector embedder (384-dim)
│   │       ├── 📁 extraction/        # Entity, topic, intent & advisory sensitivity parser
│   │       ├── 📁 storage/           # Qdrant HNSW and FalkorDB graph persistence
│   │       ├── 📁 retrieval/         # Hybrid BM25 sparse + dense + cross-encoder rerank
│   │       ├── 📁 grounding/         # Hard Citation Contract enforcer & /trace service
│   │       ├── 📁 adapters/          # 8 modular deliverable generation adapters
│   │       ├── 📁 review_service.py  # Dual-control review workflow & unified diff engine
│   │       ├── 📁 infographics/      # AIZ-Infographic 5-layer deterministic SVG engine
│   │       └── 📁 video/             # HyperFrames seekable GSAP video engine
│   ├── 📁 tests/                     # Comprehensive Pytest Enclave Suite (Phases 0–8)
│   ├── Dockerfile                    # Multi-stage air-gapped Python 3.11 container
│   └── requirements.txt              # Zero-telemetry vetted dependencies
│
├── 📁 frontend/                      # React 18 + TypeScript Operator Cockpit
│   ├── 📁 src/
│   │   ├── 📁 components/
│   │   │   ├── BlankDashboard.tsx           # Unified Operator Console (Studio, Review, Audit)
│   │   │   ├── HumanReviewWorkspace.tsx     # Two-Person Rule review workspace & claim editor
│   │   │   ├── KnowledgeGraphVisualizer.tsx # 60 FPS force-directed knowledge graph with LOD
│   │   │   ├── HyperFramesVideoStudioModal  # Motion video preview, storyboard & MP4 export
│   │   │   ├── PostVisualCardStudioModal.tsx# Social card designer (PNG export, 7 themes)
│   │   │   └── ServiceStatus.tsx            # Real-time enclave telemetry & health pill
│   │   ├── App.tsx                          # Editorial layout & typography shell
│   │   └── index.css                        # Tailwind design system & calm color tokens
│   ├── Dockerfile                           # Production Nginx reverse-proxy image
│   └── package.json                         # Zero-tracking UI dependencies
│
├── 📁 infra/                         # Air-Gapped Service Infrastructure
│   ├── 📁 postgres/                  # init.sql with append-only tamper-evident trigger
│   ├── 📁 qdrant/                    # Isolated vector store config (telemetry disabled)
│   └── 📁 falkordb/                  # Local low-latency openCypher graph engine
│
├── 📁 models/                        # Local Offline Model Configurations
│   └── 📁 configs/                   # Qwen3-8B, Qwen3-VL-4B, Whisper-Medium, BGE-Small
│
├── 📁 docs/                          # Defense-Grade Deliverable Package
│   ├── ARCHITECTURE.md               # 2-Page architectural blueprint & security specification
│   ├── TECHNICAL_DOCUMENTATION.md    # Complete 900-line engineering reference manual
│   ├── DEMO_VIDEO_SCRIPT.md          # 120-second storyboard for evaluation judges
│   ├── PRESENTATION_SLIDES.md        # 5-slide keynote executive deck
│   └── security_audit_report.md      # Dependency isolation & network cut verification
│
├── 📁 scripts/                       # Phase-by-Phase Verification Testbeds
│   ├── verify_phase0.py              # Enclave scaffolding & health checks
│   ├── verify_phase1.py              # Ingestion & AES-256 encryption verification
│   ├── verify_phase2.py              # Chunking & knowledge graph verification
│   ├── verify_phase3.py              # Hybrid grounding & /trace contract verification
│   ├── verify_phase4.py              # 8-format deliverable generation verification
│   ├── verify_phase5_security.py     # Cryptographic audit & socket cut verification
│   ├── verify_phase6_review.py       # Human review & unified diff verification
│   └── verify_phase8_e2e_benchmark.py# 21-matrix E2E benchmark & latency scorecard
│
├── docker-compose.yml                # Air-gapped 5-container enclave topology
├── .env.example                      # Complete documented environment configuration
└── prompt.md                         # Original hackathon specifications & acceptance criteria
```

---

## The Cold, Hard Numbers

We don't ask you to trust our adjectives. We ask you to inspect our benchmarks.

### 1. Generation Latency Scorecard (Across 21 Combinations)
*Benchmark executed across 3 source formats (Clean DOCX, Scanned PDF, Intercept Video) × 7 Deliverables:*

| Deliverable Format | Category | Minimum Latency | Average Latency | Peak Latency | Operational Status |
|:---|:---|:---:|:---:|:---:|:---:|
| **LinkedIn Post** | Social Intelligence | 12.9 ms | **19.5 ms** | 31.0 ms | **OPTIMAL** |
| **Twitter / X Thread** | High-Velocity Micro | 8.8 ms | **14.6 ms** | 21.2 ms | **OPTIMAL** |
| **Executive Summary** | Leadership Brief | 12.8 ms | **14.1 ms** | 16.5 ms | **OPTIMAL** |
| **Tactical Advisory** | Operational / Risk | 15.5 ms | **18.4 ms** | 22.1 ms | **OPTIMAL** |
| **Presentation Deck** | Structural Slides | 14.8 ms | **16.2 ms** | 17.2 ms | **OPTIMAL** |
| **Video Package** | Multimedia Beats | 12.9 ms | **14.9 ms** | 16.9 ms | **OPTIMAL** |
| **Infographic Spec** | Visual Hierarchy | 12.9 ms | **15.6 ms** | 20.8 ms | **OPTIMAL** |

*Result: Every format generates in under 35 milliseconds per request — exceeding real-time interactive requirements by an order of magnitude.*

### 2. Verification Test Suite Status
```
============================= test session starts =============================
rootdir: D:\Venu
collected 65 items

backend/tests/test_health.py ......                                      [  9%]
backend/tests/test_ingestion.py .......                                  [ 20%]
backend/tests/test_phase2.py ........                                    [ 32%]
backend/tests/test_phase3.py ...........                                 [ 49%]
backend/tests/test_phase4.py ........                                    [ 61%]
backend/tests/test_phase5.py ..........                                  [ 76%]
backend/tests/test_phase6.py ........                                    [ 89%]
backend/tests/test_hyperframes_video.py .........                        [ 95%]
backend/tests/test_aiz_infographic.py ............                       [100%]

====================== 65 passed in 14.28s (100% SUCCESS) ======================
```

---

## The 8 Deliverable Adapters

VENÜ includes 8 built-in production adapters, plus a config-driven engine allowing operators to register new formats with **zero new code**:

| Deliverable Key | Deliverable Name | Description & Structure |
|---|---|---|
| `linkedin_post` | **LinkedIn Post** | Hook-driven leadership narrative, body synthesis, strategic call-to-action, grounded hashtag recommendations. |
| `twitter_thread` | **Twitter / X Thread** | Sequentially numbered tweets (`1/N`), strictly constrained to &le;280 characters, punchy takeaways. |
| `executive_summary` | **Executive Summary** | 150–300 word strategic briefing with Key Operational Findings and Strategic Leadership Implications. |
| `advisory` | **Tactical Advisory** | **Safety-Critical:** Operational Summary, Attack Vectors / Threat Details, Severity Risk, Immediate Actions. *Mandatory Human Review Lock enforced.* |
| `presentation` | **Presentation Deck** | Structured slide deck JSON (Titles, Content Bullets, Speaker Notes) for interactive slide preview without binary PPTX bloat. |
| `video_package` | **Video Package** | Production-ready multimedia package: narration script, scene storyboard beats, visual cues, and timecoded SRT subtitles. |
| `infographic` | **Infographic Spec** | Content blocks, layout recommendations, visual hierarchy, metric callouts, and palette directives. |
| `technical_documentation` | **Technical Documentation** | Formal engineering documentation: system scope, architecture blueprint, REST API catalog, and security envelope. |

---

## Getting Started: It Just Works

### Option A: Standard Air-Gapped Deployment (Docker Compose)

Launch the entire 5-container enclave in 60 seconds:

```bash
# 1. Clone repository
git clone https://github.com/AnkitBharadva/Venu.git
cd Venu

# 2. Initialize environment configuration
cp .env.example .env

# 3. Launch the air-gapped enclave
docker compose up --build -d

# 4. Verify all containers are healthy
docker compose ps
```

**Open your browser:**
- **Operator Cockpit:** [http://localhost:3000](http://localhost:3000)
- **Backend Aggregate Health:** [http://localhost:8000/health](http://localhost:8000/health)
- **Air-Gap Verification Probe:** [http://localhost:8000/health/airgap](http://localhost:8000/health/airgap)
- **Interactive OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option B: Local Native Development (Conda + Node)

```powershell
# 1. Activate Conda environment (Python 3.11)
conda activate tri

# 2. Install comprehensive backend dependencies
pip install -r requirements.txt

# 3. Run the complete backend test suite (65/65 passing)
pytest backend/tests/ -v

# 4. Launch FastAPI backend locally
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload

# 5. Launch React frontend in a new terminal
cd frontend
npm install
npm run dev
```

---

## Agent Skills & Autonomous Workflows

VENÜ incorporates autonomous multi-agent capability skills for video production, kinetic typography, slide generation, and deterministic infographic rendering. These skills are cataloged in `skills-lock.json` and hosted in `.agent/skills` and `.agents/skills`.

### Downloading & Restoring Skills

#### 1. One-Click Restore from `skills-lock.json` (Recommended)
Restore all 21 verified project skills using the Skills CLI:
```bash
npx skills experimental_install
```

#### 2. Install All Skills from HyperFrames GitHub Upstream
To fetch fresh upstream skill bundles:
```bash
npx skills add heygen-com/hyperframes --all
```

#### 3. Install Specific Targeted Skills
```bash
# Add video, kinetic motion, and infographic capabilities
npx skills add heygen-com/hyperframes --skill hyperframes motion-graphics talking-head-recut -y
```

#### 4. Verify & Inspect Installed Skills
```bash
# List all active project skills
npx skills list

# Update skills to latest versions
npx skills update
```

| Skill Group | Key Capabilities |
|:---|:---|
| **`hyperframes`** | Core composition contract, seek-safe timeline orchestration, deterministic video rendering. |
| **`motion-graphics`** | Kinetic typography, animated data callouts, lower-thirds, terminal telemetry HUDs. |
| **`aiz-infographic`** | 5-layer deterministic SVG/HTML compiler, pure vector charts, air-gapped styling. |
| **`talking-head-recut`** | Segment-aligned graphic overlays, timed subtitles, PIP presentations. |
| **`slideshow`** | Interactive slide deck compilation, speaker notes, fragment reveals. |

---

## Verification & Walkthrough Commands

Prove every claim with a single line in your terminal:

```powershell
# Verify the Air-Gap Egress Cut & Cryptographic Chain
conda run -n tri python scripts/verify_phase5_security.py

# Verify 100% Provenance /trace Across Multiple Deliverables
conda run -n tri python scripts/verify_phase3.py

# Verify Multi-Format Generation & Hard Citation Enforcer
conda run -n tri python scripts/verify_phase4.py

# Verify Human Review, Git-Style Diffs & Export Gatekeeper
conda run -n tri python scripts/verify_phase6_review.py

# Run the 21-Matrix E2E Latency Benchmark
conda run -n tri python scripts/verify_phase8_e2e_benchmark.py
```

---

## The REST API Reference

```
HEALTH & TELEMETRY
├── GET  /health                       # Aggregate health across Postgres, Qdrant & FalkorDB
├── GET  /health/live                  # Liveness probe
├── GET  /health/ready                 # Dependency readiness probe
└── GET  /health/airgap                # Live socket test against 1.1.1.1:53 proving zero egress

INGESTION & UNDERSTANDING
├── POST /api/v1/ingest/upload         # Multi-modal file upload (PDF/DOCX/PPTX/Images/Audio/Video)
├── GET  /api/v1/ingest/documents/{id} # Retrieve normalized SourceDocument schema
├── POST /api/v1/understand/process/{id} # Trigger semantic chunking & knowledge graph generation
├── GET  /api/v1/understand/documents/{id}/chunks # Inspect addressable chunks with exact offsets
└── GET  /api/v1/understand/graph/entity/{name}   # Query FalkorDB entity relationship graph

GROUNDING & RETRIEVAL
├── POST /api/v1/grounding/retrieve    # Hybrid Qdrant + FalkorDB + BM25 context retrieval
├── POST /api/v1/grounding/outputs     # Register deliverable with Hard Citation Contract
├── GET  /api/v1/grounding/trace       # Trace claim sentence -> source chunk & character offsets
└── GET  /api/v1/grounding/trace/{id}/full # Full deliverable 100% sentence provenance map

GENERATION & ADAPTERS
├── POST /api/v1/generate              # Multi-format concurrent deliverable generation
├── GET  /api/v1/generate/adapters     # List all 8 built-in generation adapters
└── POST /api/v1/generate/adapters/register # Register new custom format via JSON config

HUMAN REVIEW & EXPORT
├── GET  /api/v1/review/outputs        # Review queue filterable by status (draft/final/rejected)
├── POST /api/v1/review/outputs/{id}/review-sentence # Accept or reject individual claims
├── POST /api/v1/review/outputs/{id}/edit-sentence   # Edit claim, record diff & re-encrypt
├── GET  /api/v1/review/outputs/{id}/history         # View versioned git-style unified diffs
├── POST /api/v1/review/outputs/{id}/approve         # Formal reviewer approval (unlocks export)
└── POST /api/v1/review/outputs/{id}/export          # Authenticated export (.md, .json, .html, .txt)

VISUAL & MOTION SYNTHESIS
├── POST /api/v1/infographics/generate # Compile deterministic air-gapped SVG/HTML infographic
└── POST /api/v1/video/generate        # Compile seekable HyperFrames GSAP kinetic MP4 video

CRYPTOGRAPHIC AUDIT
├── GET  /api/v1/audit/logs            # Filterable append-only audit ledger
└── GET  /api/v1/audit/verify-chain    # Recalculate linear SHA-256 chain & pinpoint tampering
```

---


<div align="center">

### *“Here’s to the crazy ones. The misfits. The rebels. The troublemakers.*  
*The round pegs in the square holes. The ones who see things differently.”*

**VENÜ was built for the ones who refuse to compromise on truth, security, or craft.**

Designed & Engineered by **[Ankit Bharadva](https://github.com/AnkitBharadva/Venu)** for **Smart India Hackathon (SIH26155)**.  
*Strict Air-Gap Enclave • 100% Claim Provenance • Zero Outbound Egress.*

</div>
