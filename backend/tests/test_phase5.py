"""Test suite for Phase 5: Security & Audit Layer.

Validates:
1. RBAC: Operator is strictly blocked (HTTP 403) from approving, rejecting, or exporting deliverables.
2. Reviewer / Approver: Successfully approves, rejects, and exports deliverables with audit logging.
3. Human Review Gatekeeper: Safety-critical advisories cannot be exported until formally approved.
4. Cryptographic Hash Chain: Tamper detection flags corrupted audit records and pinpoints exact record ID.
5. Output Encryption at Rest: Deliverables and exports are stored as AES-256-GCM authenticated ciphertexts.
6. Offline Enclave / Zero Outbound Egress: Pipeline executes with zero non-loopback network calls.
"""

import socket
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.audit import record_audit_event, verify_audit_integrity
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rbac import (
    Permission,
    Role,
    create_access_token,
    get_current_user,
    verify_access_token,
)
from app.core.security import compute_sha256, read_decrypted_file
from app.main import app
from app.models.audit_log import AuditLog, GeneratedOutput, SourceDocument
from app.models.understanding import DocumentChunk
from app.services.grounding.output_service import GroundingOutputService
from app.services.review_service import HumanReviewRequiredError, ReviewService
from app.services.security.output_encryption import (
    read_decrypted_output,
    save_encrypted_output,
    verify_output_encryption,
)


@pytest.fixture
def operator_token() -> str:
    return create_access_token(user_id="operator_alice", role=Role.OPERATOR.value)


@pytest.fixture
def reviewer_token() -> str:
    return create_access_token(user_id="reviewer_bob", role=Role.REVIEWER.value)


@pytest.fixture
def admin_token() -> str:
    return create_access_token(user_id="admin_carol", role=Role.ADMIN.value)


@pytest.fixture
async def seeded_document_with_advisory(tmp_path):
    """Seed a test source document, chunk, and an unapproved Advisory deliverable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ingest document
        content = (
            "DEFENCE DIRECTIVE 2026: Critical infrastructure resilience standards require "
            "mandatory cryptographic audit chaining and offline air-gapped isolation for all GenAI pipelines."
        )
        files = {"file": ("directive.txt", content.encode("utf-8"), "text/plain")}
        upload_resp = await client.post(
            "/api/v1/ingest/upload",
            files=files,
            headers={"X-User-Role": "operator", "X-User-Id": "operator_alice"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["document"]["doc_id"]

        # 2. Process understanding & chunking
        proc_resp = await client.post(
            f"/api/v1/understand/process/{doc_id}",
            headers={"X-User-Role": "operator", "X-User-Id": "operator_alice"},
        )
        assert proc_resp.status_code == 200

        # 3. Generate Advisory deliverable (safety-critical, requires human review)
        gen_resp = await client.post(
            "/api/v1/generate",
            json={
                "doc_id": doc_id,
                "deliverable_types": ["advisory"],
                "actor": "operator_alice",
            },
            headers={"X-User-Role": "operator", "X-User-Id": "operator_alice"},
        )
        assert gen_resp.status_code == 201
        advisory_output = gen_resp.json()["deliverables"][0]

        return {
            "doc_id": doc_id,
            "output_id": advisory_output["output_id"],
            "deliverable": advisory_output,
        }


# ==============================================================================
# 1. RBAC Token and Permission Tests
# ==============================================================================


def test_jwt_token_generation_and_verification():
    """Verify HMAC-SHA256 JWT creation, payload claims, and signature verification."""
    token = create_access_token(user_id="test_operator", role="operator", expires_in=3600)
    assert token is not None
    assert len(token.split(".")) == 3

    claims = verify_access_token(token)
    assert claims["sub"] == "test_operator"
    assert claims["role"] == "operator"
    assert "exp" in claims


def test_jwt_token_tampering_rejected():
    """Tampering with token payload or signature must raise HTTP 401."""
    token = create_access_token(user_id="operator_1", role="operator")
    parts = token.split(".")
    tampered_sig = parts[0] + "." + parts[1] + ".invalidSignature12345"

    with pytest.raises(Exception):
        verify_access_token(tampered_sig)


# ==============================================================================
# 2. RBAC Operator Blocking (Separation of Duties)
# ==============================================================================


@pytest.mark.anyio
async def test_operator_blocked_from_approve(seeded_document_with_advisory, operator_token):
    """Operator must receive HTTP 403 Forbidden when attempting to approve a deliverable."""
    output_id = seeded_document_with_advisory["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test using Bearer Token
        resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/approve",
            json={"reviewer_notes": "Attempting illegal approval"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 403
        assert "lacks mandatory permission 'approve'" in resp.text

        # Test using X-User-Role header
        resp_hdr = await client.post(
            f"/api/v1/review/outputs/{output_id}/approve",
            json={"reviewer_notes": "Attempting illegal approval via header"},
            headers={"X-User-Role": "operator", "X-User-Id": "operator_attacker"},
        )
        assert resp_hdr.status_code == 403


@pytest.mark.anyio
async def test_operator_blocked_from_reject(seeded_document_with_advisory, operator_token):
    """Operator must receive HTTP 403 Forbidden when attempting to reject a deliverable."""
    output_id = seeded_document_with_advisory["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/reject",
            json={"reviewer_notes": "Attempting illegal rejection"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 403
        assert "lacks mandatory permission 'reject'" in resp.text


@pytest.mark.anyio
async def test_operator_blocked_from_export(seeded_document_with_advisory, operator_token):
    """Operator must receive HTTP 403 Forbidden when attempting to export a deliverable."""
    output_id = seeded_document_with_advisory["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 403
        assert "lacks mandatory permission 'export'" in resp.text


# ==============================================================================
# 3. Human Review Gatekeeper (Advisory Export Lock)
# ==============================================================================


@pytest.mark.anyio
async def test_advisory_export_locked_until_approved(seeded_document_with_advisory, reviewer_token):
    """Safety-critical Advisory cannot be exported by Reviewer until formally approved."""
    output_id = seeded_document_with_advisory["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Reviewer attempts export on unapproved advisory
        resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 403
        assert "requires explicit human reviewer approval before export" in resp.json()["detail"]["message"]

        # Reviewer approves the deliverable
        approve_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/approve",
            json={"reviewer_notes": "Grounding citations verified against defence standards. Approved."},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] in ["approved", "final"]
        assert approve_resp.json()["reviewer_id"] == "reviewer_bob"

        # Now export succeeds
        export_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert export_resp.status_code == 200
        export_data = export_resp.json()
        assert export_data["output_id"] == output_id
        assert export_data["export_format"] == "markdown"
        assert len(export_data["checksum_sha256"]) == 64
        assert "DEFENCE DIRECTIVE 2026" in export_data["exported_content"] or "Grounding Citations" in export_data["exported_content"]
        assert export_data["audit_logged"] is True


# ==============================================================================
# 4. Output Encryption at Rest (AES-256-GCM)
# ==============================================================================


@pytest.mark.anyio
async def test_output_encrypted_at_rest(seeded_document_with_advisory, reviewer_token):
    """Verify that the generated deliverable payload on disk is AES-256-GCM encrypted ciphertext."""
    output_id = seeded_document_with_advisory["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        verify_resp = await client.get(
            f"/api/v1/review/outputs/{output_id}/verify-encryption",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert verify_resp.status_code == 200
        vdata = verify_resp.json()
        assert vdata["verified"] is True
        assert vdata["encrypted_at_rest"] is True
        assert vdata["algorithm"] == "AES-256-GCM"

        file_path = Path(vdata["file_path"])
        assert file_path.exists()
        raw_ciphertext = file_path.read_bytes()

        # Plaintext title or JSON keys must NOT appear unencrypted in the file on disk
        assert b'"status": "draft"' not in raw_ciphertext
        assert b'"deliverable_type": "advisory"' not in raw_ciphertext

        # Reading and decrypting via enclave function succeeds
        decrypted = read_decrypted_output(file_path)
        assert decrypted["output_id"] == output_id
        assert decrypted["deliverable_type"] == "advisory"


@pytest.mark.anyio
async def test_tampered_encrypted_file_detected():
    """Corrupting bytes of an encrypted file must cause decryption failure."""
    dummy_id = uuid.uuid4()
    dummy_doc = uuid.uuid4()
    saved_path = save_encrypted_output(
        output_id=dummy_id,
        doc_id=dummy_doc,
        deliverable_type="briefing",
        status="draft",
        content={"title": "Secret"},
        citations=[],
        format_metadata={},
    )
    p = Path(saved_path)
    assert p.exists()

    # Verify initially valid
    check = verify_output_encryption(dummy_id, p)
    assert check["verified"] is True

    # Mutate ciphertext byte
    tampered_bytes = bytearray(p.read_bytes())
    tampered_bytes[20] ^= 0xFF  # Corrupt a byte
    p.write_bytes(tampered_bytes)

    # Decryption must fail due to GCM authentication tag mismatch
    check_corrupted = verify_output_encryption(dummy_id, p)
    assert check_corrupted["verified"] is False
    assert "Decryption failed" in check_corrupted["error"]


# ==============================================================================
# 5. Cryptographic Hash Chain & Tamper Detection
# ==============================================================================


@pytest.mark.anyio
async def test_audit_hash_chain_tamper_detection(seeded_document_with_advisory, reviewer_token):
    """Modifying an audit row in the database must break the hash chain and identify the corrupted ID."""
    output_id = seeded_document_with_advisory["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request approval & approve to create multiple chained audit entries
        await client.post(
            f"/api/v1/review/outputs/{output_id}/request-approval",
            json={"notes": "Ready for review"},
            headers={"X-User-Role": "operator", "X-User-Id": "operator_alice"},
        )
        await client.post(
            f"/api/v1/review/outputs/{output_id}/approve",
            json={"reviewer_notes": "Looks good"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )

        # 1. Verify chain is initially valid
        verify_resp = await client.get("/api/v1/audit/verify-chain")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True
        assert verify_resp.json()["total_records"] >= 3

        # 2. Directly tamper with one record in the database
        db_gen = app.dependency_overrides[get_db]()
        session = await anext(db_gen)
        try:
            stmt = select(AuditLog).where(AuditLog.action == "request_approval")
            res = await session.execute(stmt)
            target_entry = res.scalar_one_or_none()
            assert target_entry is not None
            tampered_id = target_entry.id

            # Maliciously change the actor to unauthorized user
            target_entry.actor = "malicious_hacker"
            await session.commit()
        finally:
            await session.close()

        # 3. Re-verify audit chain: must detect tampering and flag the exact record
        verify_resp_tampered = await client.get("/api/v1/audit/verify-chain")
        assert verify_resp_tampered.status_code == 200
        tdata = verify_resp_tampered.json()
        assert tdata["valid"] is False
        assert tdata["record_id"] == tampered_id
        assert f"Tampered record at id {tampered_id}" in tdata["error"]


# ==============================================================================
# 6. Network Cut Proof: Complete Pipeline Offline Verification
# ==============================================================================


@pytest.mark.anyio
async def test_full_pipeline_with_strict_network_cut(reviewer_token):
    """Strict network isolation: intercept socket connections to prove zero non-loopback calls.

    Simulates cutting external network access. Full pipeline (upload -> understand ->
    retrieve -> generate -> review -> export -> trace) must succeed completely offline.
    """
    real_connect = socket.socket.connect

    def airgap_socket_guard(self, address):
        host = address[0] if isinstance(address, tuple) else address
        # Allow only loopback addresses and unix sockets
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise PermissionError(
                f"AIRGAP VIOLATION: Attempted outbound network connection to '{host}'. "
                f"Enclave strictly prohibits external egress."
            )
        return real_connect(self, address)

    with patch.object(socket.socket, "connect", airgap_socket_guard):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Step 1: Upload source
            doc_text = "OFFLINE AIR-GAP DIRECTIVE: All sensitive operations occur inside isolated enclave."
            upload_resp = await client.post(
                "/api/v1/ingest/upload",
                files={"file": ("airgap.txt", doc_text.encode("utf-8"), "text/plain")},
                headers={"X-User-Role": "operator", "X-User-Id": "operator_offline"},
            )
            assert upload_resp.status_code == 201
            doc_id = upload_resp.json()["document"]["doc_id"]

            # Step 2: Understand & chunk
            proc_resp = await client.post(
                f"/api/v1/understand/process/{doc_id}",
                headers={"X-User-Role": "operator", "X-User-Id": "operator_offline"},
            )
            assert proc_resp.status_code == 200

            # Step 3: Retrieve grounded context
            ret_resp = await client.post(
                "/api/v1/grounding/retrieve",
                json={"query": "sensitive operations", "doc_id": doc_id, "top_k": 3},
            )
            assert ret_resp.status_code == 200

            # Step 4: Multi-select generation
            gen_resp = await client.post(
                "/api/v1/generate",
                json={
                    "doc_id": doc_id,
                    "deliverable_types": ["executive_summary", "linkedin_post"],
                    "actor": "operator_offline",
                },
                headers={"X-User-Role": "operator", "X-User-Id": "operator_offline"},
            )
            assert gen_resp.status_code == 201
            delivs = gen_resp.json()["deliverables"]
            assert len(delivs) == 2

            # Step 5: Trace first deliverable
            trace_resp = await client.get(f"/api/v1/grounding/trace/{delivs[0]['output_id']}")
            assert trace_resp.status_code == 200
            assert trace_resp.json()["coverage_pct"] == 100.0

            # Step 6: Reviewer approves and exports
            approve_resp = await client.post(
                f"/api/v1/review/outputs/{delivs[0]['output_id']}/approve",
                json={"reviewer_notes": "Reviewed offline payload. Approved."},
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert approve_resp.status_code == 200

            export_resp = await client.post(
                f"/api/v1/review/outputs/{delivs[0]['output_id']}/export",
                json={"export_format": "markdown"},
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert export_resp.status_code == 200

            # Step 7: Cryptographic audit check
            audit_verify = await client.get("/api/v1/audit/verify-chain")
            assert audit_verify.status_code == 200
            assert audit_verify.json()["valid"] is True
