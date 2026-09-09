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
    └── verify_phase0.py           # Self-contained Phase 0 verification script
```

---

## Phase Roadmap
- **[x] Phase 0: Repo Scaffolding & Environment** — Running skeleton with all 5 services stubbed, zero egress network, health checks, CI stub.
- **[ ] Phase 1: Ingestion Pipeline** — Docling, PaddleOCR, Whisper router, AES-256 encryption at rest, audit logging on upload.
- **[ ] Phase 2: Understanding & Chunking Layer** — Semantic chunking, entity extraction, local embeddings, Qdrant & FalkorDB upserts.
- **[ ] Phase 3: Grounding & Retrieval Service** — `/retrieve` and `/trace` endpoints, strict claim-citation contract.
- **[ ] Phase 4: Output Generation Adapters** — LinkedIn, Twitter, Exec Summary, Advisory, Presentation, Video Package, Infographic.
- **[ ] Phase 5: Security & Audit Layer** — RBAC, tamper-evident hash chain verification, network-cut live proof.
- **[ ] Phase 6: Human Review & Approval Workflow** — Draft state, sentence-level review, reviewer diff history, export lock.
- **[ ] Phase 7: Operator Dashboard** — Complete interactive React UI with hover-to-source inspection.
- **[ ] Phase 8: Testing, Hardening & Deliverables Packaging** — Architecture document, demo script, and final packaging.
