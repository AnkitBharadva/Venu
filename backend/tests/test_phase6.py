"""Phase 6: Human Review & Approval Workflow Integration Tests.

Validates:
1. Generated outputs start in status 'draft'.
2. Exporting 'draft' outputs is strictly rejected with a clear error.
3. Reviewers can accept, edit, and reject per sentence or per section.
4. Reviewer edits are unified-diffed and stored in immutable edit history (preserving before/after states).
5. Approving transitions status to 'final' and unlocks export.
6. Export endpoint only serves 'final' status outputs.
7. Full audit/history diff inspection endpoint.
8. Cryptographic hash chain verification over review lifecycle.
"""

import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rbac import create_access_token
from app.main import app


@pytest.fixture
def operator_token() -> str:
    return create_access_token(user_id="operator_alice", role="operator", expires_in=3600)


@pytest.fixture
def reviewer_token() -> str:
    return create_access_token(user_id="reviewer_bob", role="reviewer", expires_in=3600)


@pytest.fixture
async def seeded_document_with_draft_output(operator_token: str) -> dict:
    """Seeds a valid document, runs understanding, and generates a deliverable in 'draft' status."""
    raw_document_content = (
        "DEFENCE DIRECTIVE 2026: OPERATIONAL PROTOCOL ALPHA.\n\n"
        "Section 1: Air-Gap Perimeter Security.\n"
        "All sensitive computing assets must operate inside a physically disconnected Faraday facility. "
        "Zero network egress is tolerated under military defense regulations.\n\n"
        "Section 2: Tactical Cryptography Requirements.\n"
        "Data at rest must be encrypted using AES-256 authenticated ciphers with local key management. "
        "All operator and reviewer actions must be recorded in an immutable append-only audit trail.\n\n"
        "Section 3: Mandatory Human Review.\n"
        "No automated intelligence summary may be disseminated without formal reviewer sign-off."
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ingest document
        upload_resp = await client.post(
            "/api/v1/ingest/upload",
            files={"file": ("defence_spec.txt", io.BytesIO(raw_document_content.encode("utf-8")), "text/plain")},
            data={"uploader_id": "operator_alice"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["document"]["doc_id"]

        # 2. Process understanding & chunking
        proc_resp = await client.post(
            f"/api/v1/understand/process/{doc_id}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert proc_resp.status_code == 200

        # 3. Generate deliverable (starts in 'draft' status)
        gen_resp = await client.post(
            "/api/v1/generate",
            json={
                "doc_id": doc_id,
                "deliverable_types": ["executive_summary"],
                "actor": "operator_alice",
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert gen_resp.status_code == 201
        output = gen_resp.json()["deliverables"][0]

        return {
            "doc_id": doc_id,
            "output_id": output["output_id"],
            "deliverable": output,
        }


# ==============================================================================
# Task 1 & 5: Draft Status & Export Blocking
# ==============================================================================


@pytest.mark.anyio
async def test_generated_output_starts_in_status_draft(seeded_document_with_draft_output):
    """Task 1: Newly generated deliverables MUST start in status 'draft'."""
    output = seeded_document_with_draft_output["deliverable"]
    assert output["status"] == "draft"
    assert output["format_metadata"].get("export_locked") is True
    assert output["format_metadata"].get("review_status") == "pending"


@pytest.mark.anyio
async def test_export_draft_output_fails_with_clear_error(
    seeded_document_with_draft_output, reviewer_token
):
    """Task 5: Attempting to export an unapproved 'draft' output fails with clear error."""
    output_id = seeded_document_with_draft_output["output_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert "message" in detail or "error" in detail
        err_msg = str(detail)
        assert "draft" in err_msg
        assert "final" in err_msg or "requires explicit human reviewer approval" in err_msg


# ==============================================================================
# Task 2 & 4: Sentence & Section Editing with Diff Tracking
# ==============================================================================


@pytest.mark.anyio
async def test_reviewer_edits_sentence_with_diff_stored(
    seeded_document_with_draft_output, reviewer_token
):
    """Task 2 & 4: Reviewer edits sentence, before/after diff is generated and stored."""
    output_id = seeded_document_with_draft_output["output_id"]
    output = seeded_document_with_draft_output["deliverable"]
    target_sentence = output["content"]["blocks"][0]["sentences"][0]
    sent_id = target_sentence["sentence_id"]
    old_text = target_sentence["text"]
    new_text = "REVISED CLAIM: All computing assets must strictly enforce physical air-gapping."

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Edit sentence as reviewer
        edit_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/edit-sentence",
            json={
                "sentence_id": sent_id,
                "new_text": new_text,
                "notes": "Tightened military wording and defense compliance",
            },
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert edit_resp.status_code == 200
        updated_output = edit_resp.json()

        # Check sentence text is updated and marked as 'edited'
        updated_sentence = updated_output["content"]["blocks"][0]["sentences"][0]
        assert updated_sentence["text"] == new_text
        assert updated_sentence["review_status"] == "edited"
        assert updated_sentence["last_edited_by"] == "reviewer_bob"

        # Check history endpoint contains diff
        hist_resp = await client.get(
            f"/api/v1/review/outputs/{output_id}/history",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) >= 1
        last_edit = history[-1]
        assert last_edit["action"] == "edit_sentence"
        assert last_edit["actor"] == "reviewer_bob"
        assert last_edit["before_content"] == old_text
        assert last_edit["after_content"] == new_text
        assert last_edit["diff_summary"] is not None
        assert "-" in last_edit["diff_summary"]
        assert "+" in last_edit["diff_summary"]


@pytest.mark.anyio
async def test_reviewer_accept_and_reject_sentences(
    seeded_document_with_draft_output, reviewer_token
):
    """Task 2: Reviewer can individually accept and reject sentences."""
    output_id = seeded_document_with_draft_output["output_id"]
    output = seeded_document_with_draft_output["deliverable"]
    sent0 = output["content"]["blocks"][0]["sentences"][0]["sentence_id"]
    sent1 = output["content"]["blocks"][0]["sentences"][1]["sentence_id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Accept sent0
        res0 = await client.post(
            f"/api/v1/review/outputs/{output_id}/review-sentence",
            json={"sentence_id": sent0, "decision": "accept", "notes": "Citations checked"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert res0.status_code == 200
        assert res0.json()["content"]["blocks"][0]["sentences"][0]["review_status"] == "accepted"

        # Reject sent1
        res1 = await client.post(
            f"/api/v1/review/outputs/{output_id}/review-sentence",
            json={"sentence_id": sent1, "decision": "reject", "notes": "Requires re-grounding"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert res1.status_code == 200
        assert res1.json()["content"]["blocks"][0]["sentences"][1]["review_status"] == "rejected"


@pytest.mark.anyio
async def test_reviewer_review_section_bulk(
    seeded_document_with_draft_output, reviewer_token
):
    """Task 2: Reviewer can accept an entire section/block in bulk."""
    output_id = seeded_document_with_draft_output["output_id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sec_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/review-section",
            json={"block_index": 0, "decision": "accept", "notes": "Entire section verified"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert sec_resp.status_code == 200
        block0 = sec_resp.json()["content"]["blocks"][0]
        assert block0["review_status"] == "accepted"
        for s in block0["sentences"]:
            assert s["review_status"] == "accepted"


# ==============================================================================
# Task 3 & 5: Approval Transitions to 'final' and Unlocks Export
# ==============================================================================


@pytest.mark.anyio
async def test_approve_transitions_to_final_and_unlocks_export(
    seeded_document_with_draft_output, reviewer_token
):
    """Task 3 & 5: 'approve' transitions status to 'final' and unlocks export."""
    output_id = seeded_document_with_draft_output["output_id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Approve deliverable
        app_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/approve",
            json={"reviewer_notes": "All sections and citations verified. Ready for release."},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert app_resp.status_code == 200
        approved_data = app_resp.json()
        assert approved_data["status"] == "final"
        assert approved_data["format_metadata"]["export_locked"] is False

        # 2. Export now succeeds
        exp_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert exp_resp.status_code == 200
        exp_data = exp_resp.json()
        assert exp_data["output_id"] == output_id
        assert exp_data["export_format"] == "markdown"
        assert len(exp_data["checksum_sha256"]) == 64
        assert len(exp_data["exported_content"]) > 0


@pytest.mark.anyio
async def test_operator_blocked_from_approving_or_exporting(
    seeded_document_with_draft_output, operator_token
):
    """RBAC: Operator role is blocked from approving and exporting (HTTP 403)."""
    output_id = seeded_document_with_draft_output["output_id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Operator cannot approve
        app_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/approve",
            json={"reviewer_notes": "Illegal attempt"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert app_resp.status_code == 403

        # Operator cannot export
        exp_resp = await client.post(
            f"/api/v1/review/outputs/{output_id}/export",
            json={"export_format": "markdown"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert exp_resp.status_code == 403


# ==============================================================================
# Summary Metrics & Audit Hash Chain
# ==============================================================================


@pytest.mark.anyio
async def test_review_summary_and_audit_chain(
    seeded_document_with_draft_output, reviewer_token
):
    """Review metrics and cryptographic hash chain integrity across edit actions."""
    output_id = seeded_document_with_draft_output["output_id"]
    output = seeded_document_with_draft_output["deliverable"]
    sent0 = output["content"]["blocks"][0]["sentences"][0]["sentence_id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Edit sentence
        await client.post(
            f"/api/v1/review/outputs/{output_id}/edit-sentence",
            json={"sentence_id": sent0, "new_text": "Updated content."},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )

        # Get summary
        sum_resp = await client.get(
            f"/api/v1/review/outputs/{output_id}/summary",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert sum_resp.status_code == 200
        summary = sum_resp.json()
        assert summary["total_sentences"] > 0
        assert summary["edited_sentences"] == 1
        assert summary["can_export"] is False  # Still in draft
        assert summary["history_count"] >= 1

        # Check cryptographic chain
        chain_resp = await client.get(
            "/api/v1/audit/verify-chain",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert chain_resp.status_code == 200
        chain_data = chain_resp.json()
        assert chain_data["valid"] is True
