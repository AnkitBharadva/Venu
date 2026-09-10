"""Output Encryption at Rest Service for Phase 5.

Guarantees that all generated deliverables, briefings, advisories, and export artifacts
are encrypted using authenticated AES-256-GCM before writing to storage.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.security import compute_sha256, read_decrypted_file, save_encrypted_file

logger = logging.getLogger("app.services.security.output_encryption")


def _get_output_storage_dir() -> Path:
    """Resolve storage directory with fallback for local Windows enclave execution."""
    settings = get_settings()
    target_dir = Path(settings.OUTPUT_STORAGE_PATH)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir
    except (OSError, PermissionError):
        fallback = Path("./storage/encrypted_outputs").resolve()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def save_encrypted_output(
    output_id: uuid.UUID,
    doc_id: uuid.UUID,
    deliverable_type: str,
    status: str,
    content: dict[str, Any],
    citations: list[dict[str, Any]],
    format_metadata: dict[str, Any],
    reviewer_id: str | None = None,
    reviewer_notes: str | None = None,
) -> str:
    """Serialize deliverable output payload to JSON and encrypt at rest with AES-256-GCM.

    Returns the absolute path to the encrypted .enc file on disk.
    """
    storage_dir = _get_output_storage_dir()
    target_file = storage_dir / f"{output_id}.enc"

    payload = {
        "output_id": str(output_id),
        "doc_id": str(doc_id),
        "deliverable_type": deliverable_type,
        "status": status,
        "content": content,
        "citations": citations,
        "format_metadata": format_metadata,
        "reviewer_id": reviewer_id,
        "reviewer_notes": reviewer_notes,
    }

    raw_bytes = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    saved_path = save_encrypted_file(raw_bytes, target_file)
    logger.info("Deliverable %s encrypted and stored at rest: %s", output_id, saved_path)
    return saved_path


def read_decrypted_output(source_path: str | Path) -> dict[str, Any]:
    """Read an AES-256-GCM encrypted deliverable and deserialize the decrypted JSON."""
    decrypted_bytes = read_decrypted_file(source_path)
    return json.loads(decrypted_bytes.decode("utf-8"))


def verify_output_encryption(
    output_id: uuid.UUID,
    encrypted_file_path: str | Path,
) -> dict[str, Any]:
    """Verify that an output file exists, is encrypted at rest, and decrypts cleanly."""
    path = Path(encrypted_file_path)
    if not path.exists():
        return {
            "verified": False,
            "error": f"Encrypted output file does not exist at {path}",
            "output_id": str(output_id),
        }

    raw_encrypted_bytes = path.read_bytes()
    if len(raw_encrypted_bytes) < 28:
        return {
            "verified": False,
            "error": "Encrypted file payload is too short or invalid.",
            "output_id": str(output_id),
        }

    try:
        decrypted_payload = read_decrypted_output(path)
        decrypted_id = decrypted_payload.get("output_id")
        if decrypted_id != str(output_id):
            return {
                "verified": False,
                "error": f"Output ID mismatch: expected {output_id}, found {decrypted_id}",
                "output_id": str(output_id),
            }

        return {
            "verified": True,
            "encrypted_at_rest": True,
            "algorithm": "AES-256-GCM",
            "file_path": str(path.resolve()),
            "file_size_bytes": len(raw_encrypted_bytes),
            "ciphertext_sha256": compute_sha256(raw_encrypted_bytes),
            "output_id": str(output_id),
            "deliverable_type": decrypted_payload.get("deliverable_type"),
            "status": decrypted_payload.get("status"),
        }
    except Exception as exc:
        return {
            "verified": False,
            "error": f"Decryption failed (tampered ciphertext or corrupted nonce/tag): {exc}",
            "output_id": str(output_id),
        }
