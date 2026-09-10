# Security & Audit Architecture Report: Defence-Grade Enclave Verification

**Project:** SIH26155 — Air-Gapped GenAI Platform for Automated Content Transformation  
**Phase:** Phase 5 — Security & Audit Layer  
**Classification:** DEFENCE-GRADE AIR-GAPPED ENCLAVE (STRICT ZERO-EGRESS)  
**Verification Date:** September 2026  

---

## 1. Executive Summary & Security Posture

The platform is designed to operate in high-security, mission-critical, and defence environments where **zero external network egress** is non-negotiable. To satisfy the mandate of demonstrable defence-level security rather than unverified assertions, Phase 5 establishes four cryptographically provable security guarantees:

1. **Role-Based Access Control (RBAC) with Strict Separation of Duties:** Operates on the principle of dual-control / two-man rule. Operators can upload documents, trigger semantic chunking, and generate deliverables, but are cryptographically and procedurally blocked (HTTP 403 Forbidden) from approving, rejecting, or exporting deliverables. Only authorized Reviewers/Approvers can authorize output publication.
2. **Tamper-Evident Append-Only Cryptographic Audit Log:** Every action (ingestion, chunking, retrieval, generation, approval request, review approval, rejection, and export) commits an immutable row chained via SHA-256 (`hash = sha256(prev_hash + actor + action + doc_id + output_id + timestamp + source_hash + details)`). Any modification, deletion, or insertion breaks the chain and is programmatically pinpointed to the exact compromised row ID.
3. **Authenticated Encryption at Rest (AES-256-GCM):** Raw uploaded source files, intermediate normalized representations, generated deliverables, and exported artifacts are encrypted using AES-256-GCM with unique 96-bit nonces before touching disk. Storage keys are loaded exclusively from local KMS / protected enclave environment configuration—never hardcoded.
4. **Offline Air-Gap Proof with Zero External Telemetry:** A verified network-cut suite proves that 100% of the ingestion, understanding, vector retrieval, adapter generation, citation tracing, review, and export pipelines execute successfully with zero external socket connections.

---

## 2. Role-Based Access Control (RBAC) Matrix

Access control is enforced at both the API router and service layer via FastAPI dependency injection (`backend/app/core/rbac.py`). Authentication supports both self-contained HMAC-SHA256 JWT tokens and enclave identity headers (`X-User-Role`, `X-User-Id`).

| Role | Upload Sources | Process & Chunk | Hybrid Retrieval | Generate Deliverables | Request Review | Approve / Reject | Export Assets | Verify Hash Chain |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Operator** |  **Allowed** |  **Allowed** |  **Allowed** |  **Allowed** |  **Allowed** | ❌ **BLOCKED (403)** | ❌ **BLOCKED (403)** |  **Allowed** |
| **Reviewer / Approver** | ❌ Blocked |  Allowed |  Allowed | ❌ Blocked |  Allowed |  **Allowed** |  **Allowed** |  **Allowed** |
| **Enclave Admin** |  Allowed |  Allowed |  Allowed |  Allowed |  Allowed |  Allowed |  Allowed |  Allowed |

### Mandatory Review Gatekeeper (Advisory Protection)
For safety-critical formats such as **Advisories**, the system enforces a strict programmatic lock:
- When an Advisory is generated, its format metadata is stamped with `requires_human_review: true`, `review_status: "pending_review"`, and `export_locked: true`.
- Even if a Reviewer calls `POST /api/v1/review/outputs/{id}/export`, the system rejects the export with `HTTP 403 Forbidden` (`HumanReviewRequiredError`) until the deliverable has been explicitly transitioned to `approved` state by a human reviewer.

---

## 3. Tamper-Evident SHA-256 Cryptographic Hash Chaining

The audit log table (`audit_log` in PostgreSQL/SQLite) forms a linear cryptographic hash chain rooted at a deterministic genesis block:

$$\text{Hash}_n = \text{SHA-256}\Big(\text{Hash}_{n-1} \parallel \text{actor} \parallel \text{action} \parallel \text{doc\_id} \parallel \text{output\_id} \parallel \text{timestamp\_iso} \parallel \text{source\_hash} \parallel \text{canonical\_json(details)}\Big)$$

### Mathematical Tamper Detection
- When `GET /api/v1/audit/verify-chain` is invoked, `verify_audit_integrity()` iterates sequentially through all rows from `id = 1` to $N$.
- For each row $i$, it validates that $\text{prev\_hash}_i == \text{hash}_{i-1}$.
- It recomputes the expected hash using the stored canonical details and verifies $\text{hash}_i == \text{recomputed\_hash}$.
- If an adversary mutates any database cell (e.g. changing `actor` from `operator_alice` to `malicious_hacker`), the hash of that row changes. Consequently, row $i$'s hash no longer matches its stored hash, and row $i+1$'s `prev_hash` does not match row $i$'s hash.
- The verification endpoint immediately flags `valid: false`, providing the exact corrupted row ID and failure reason.

---

## 4. Encryption at Rest Architecture (AES-256-GCM)

All persisted binary and JSON payloads are protected against offline physical inspection or disk theft using authenticated Galois/Counter Mode encryption (`backend/app/core/security.py`):

1. **Key Derivation:** A 256-bit symmetric key is supplied via `STORAGE_ENCRYPTION_KEY`.
2. **Payload Structure:**
   $$\text{Stored Payload} = [12\text{-byte Nonce}] \parallel [\text{Ciphertext}] \parallel [16\text{-byte GCM Authentication Tag}]$$
3. **Tamper Rejection:** Modifying even a single bit of the encrypted `.enc` file causes the underlying AES-GCM decryption routine to reject the authentication tag, preventing chosen-ciphertext attacks or corrupted data restoration.
4. **Scope of Coverage:**
   - **Uploads:** `storage/encrypted_uploads/{doc_id}.enc`
   - **Outputs:** `storage/encrypted_outputs/{output_id}.enc`
   - **Exports:** `storage/encrypted_outputs/exports/{deliverable_type}_{output_id}.{format}.enc`

---

## 5. Third-Party Dependency Tree Audit (Zero-Egress Certification)

An exhaustive audit of all dependencies in `backend/requirements.txt`, `backend/pyproject.toml`, and `frontend/package.json` was conducted to confirm the absence of telemetry, cloud SDKs, or unauthorized egress vectors.

### Backend Dependencies (`backend/requirements.txt`)

| Package | Pinned Version | Purpose / Architectural Justification | Outbound Telemetry Audit |
| :--- | :--- | :--- | :--- |
| `fastapi` | `>=0.110.0,<1.0.0` | High-performance ASGI web framework |  **Zero outbound calls**. Strictly serves local HTTP endpoints. |
| `uvicorn[standard]` | `>=0.28.0,<1.0.0` | Local ASGI web server |  **Zero outbound calls**. Bound to local interfaces. |
| `pydantic` | `>=2.6.0,<3.0.0` | Data validation & strict contract enforcement |  Pure computational data modeling. Zero network IO. |
| `pydantic-settings` | `>=2.2.0,<3.0.0` | Environment configuration loading |  Local filesystem & OS environment parsing only. |
| `python-multipart` | `>=0.0.9` | Multipart form parsing for local file uploads |  Pure stream parsing library. Zero network egress. |
| `pypdf` | `>=5.0.0` | PDF text & metadata extraction parser |  Local PDF parsing only. No external telemetry. |
| `python-docx` | `>=1.1.0` | DOCX document structured parser |  Local XML/Zip extraction. Zero external egress. |
| `python-pptx` | `>=1.0.0` | PowerPoint slide structured parser |  Local XML/Zip extraction. Zero external egress. |
| `Pillow` | `>=10.0.0` | Image processing for OCR preparation |  Local image pixel transformations. Zero network IO. |
| `sqlalchemy[asyncio]`| `>=2.0.28,<3.0.0`| Database ORM & asynchronous session engine |  Connects only to internal Postgres container. |
| `asyncpg` | `>=0.29.0,<1.0.0` | High-throughput async Postgres driver |  Intra-enclave DB socket connection only. |
| `psycopg[binary]` | `>=3.1.18,<4.0.0` | Synchronous Postgres driver for migrations |  Intra-enclave DB socket connection only. |
| `redis` | `>=5.0.3,<6.0.0` | Redis/FalkorDB graph driver |  Intra-enclave graph query socket connection only. |
| `qdrant-client` | `>=1.8.0,<2.0.0` | Vector database client |  Connects only to internal Qdrant container over port 6333. |
| `httpx` | `>=0.27.0,<1.0.0` | Test client & local mock transport |  Used exclusively with `ASGITransport` for in-memory testing. |
| `python-dotenv` | `>=1.0.1,<2.0.0` | Local `.env` file loader |  Filesystem IO only. Zero network IO. |
| `PyYAML` | `>=6.0.1,<7.0.0` | YAML configuration parser for adapters |  Pure text parser. Zero network IO. |
| `cryptography` | `>=42.0.5,<44.0.0`| Cryptographic primitives (AES-GCM, SHA-256) |  C/Rust OpenSSL cryptographic engine. Zero network IO. |

### Frontend Dependencies (`frontend/package.json`)

| Package | Version | Purpose | Telemetry Audit |
| :--- | :--- | :--- | :--- |
| `react` | `^18.3.1` | UI Component Framework |  **Zero external analytics/telemetry**. |
| `react-dom` | `^18.3.1` | DOM Renderer for React |  Zero external analytics/telemetry. |
| `vite` | `^5.2.11` | Build tooling & bundler (dev only) |  Local bundling. Telemetry disabled. |
| `tailwindcss` | `^3.4.4` | CSS styling engine (build time only) |  Zero runtime footprint. |
| `typescript` | `^5.4.5` | Type checker (build time only) |  Zero runtime footprint. |

### Explicitly Excluded Packages (Prohibited in Air-Gap Enclave)
- ❌ `openai`, `anthropic`, `google-generativeai`, `cohere`: **STRICTLY PROHIBITED**. Cloud API SDKs would violate air-gap constraints.
- ❌ `langchain-community`: Excluded due to unnecessary cloud-integrations and telemetry risks.
- ❌ `sentry-sdk`, `mixpanel`, `google-analytics`, `segment`: Excluded to guarantee zero outbound telemetry.

---

## 6. Network Isolation Proof (Air-Gap Socket Guard)

To empirically verify that the system functions with zero network egress, automated tests intercept Python's OS socket connection layer (`socket.socket.connect`). Any outbound socket connection attempted to an IP address other than loopback (`127.0.0.1`, `localhost`, `::1`) immediately raises an uncatchable `PermissionError("AIRGAP VIOLATION")`.

### Test Trajectory Verified Under Strict Socket Interception
1. Ingest multi-modal document (`POST /api/v1/ingest/upload`).
2. Encrypt uploaded file at rest with AES-256-GCM.
3. Commit cryptographic audit row with SHA-256 hash chaining.
4. Process semantic chunking with exact character offsets (`POST /api/v1/understand/process/{id}`).
5. Execute hybrid vector-graph retrieval (`POST /api/v1/grounding/retrieve`).
6. Concurrently execute multi-select deliverable adapters (`POST /api/v1/generate`).
7. Enforce hard claim-citation contract gatekeeper (100% citation coverage).
8. Encrypt deliverable output at rest with AES-256-GCM.
9. Verify operator role is blocked from approving (HTTP 403 Forbidden).
10. Reviewer approves safety-critical advisory (`POST /api/v1/review/outputs/{id}/approve`).
11. Reviewer exports advisory into AES-256 encrypted archive (`POST /api/v1/review/outputs/{id}/export`).
12. Trace sentence provenance to source document text spans (`GET /api/v1/grounding/trace/{id}`).
13. Cryptographically verify complete audit hash chain (`GET /api/v1/audit/verify-chain`).

**Result:** 100% of pipeline stages succeed with zero outbound network calls.
