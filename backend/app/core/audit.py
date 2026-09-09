"""Append-only cryptographic audit logger with tamper-evident SHA-256 hash chaining."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def normalize_timestamp_str(ts: Any) -> str:
    """Normalize datetime or string to a canonical UTC ISO string representation."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC).isoformat()
    if isinstance(ts, str):
        # Handle SQLite space separator
        clean = ts.replace(" ", "T")
        if not clean.endswith("Z") and "+" not in clean:
            clean += "+00:00"
        return clean
    return str(ts)


def compute_chain_hash(
    prev_hash: str,
    actor: str,
    action: str,
    doc_id: str | None,
    output_id: str | None,
    timestamp_iso: str,
    source_hash: str | None,
    details: dict[str, Any],
) -> str:
    """Compute deterministic SHA-256 hash linking this audit row to the previous entry."""
    canonical_details = json.dumps(details, sort_keys=True)
    canonical_ts = normalize_timestamp_str(timestamp_iso)
    payload = (
        f"{prev_hash}|{actor}|{action}|{doc_id or ''}|{output_id or ''}|"
        f"{canonical_ts}|{source_hash or ''}|{canonical_details}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def record_audit_event(
    session: AsyncSession,
    actor: str,
    action: str,
    doc_id: uuid.UUID | None = None,
    output_id: uuid.UUID | None = None,
    source_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Append a cryptographically chained entry to the audit log table."""
    details = dict(details or {})
    now_dt = datetime.now(UTC)
    canonical_ts = normalize_timestamp_str(now_dt)

    # Retrieve previous audit log entry to form the hash chain
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
    result = await session.execute(stmt)
    last_entry = result.scalar_one_or_none()

    prev_hash = str(last_entry.hash) if last_entry else GENESIS_HASH

    doc_id_str = str(doc_id) if doc_id else None
    output_id_str = str(output_id) if output_id else None

    # Embed canonical timestamp in details for dialect invariance
    details["_ts"] = canonical_ts

    current_hash = compute_chain_hash(
        prev_hash=prev_hash,
        actor=actor,
        action=action,
        doc_id=doc_id_str,
        output_id=output_id_str,
        timestamp_iso=canonical_ts,
        source_hash=source_hash,
        details=details,
    )

    audit_entry = AuditLog(
        actor=actor,
        action=action,
        doc_id=doc_id,
        output_id=output_id,
        timestamp=now_dt,
        source_hash=source_hash,
        details=details,
        prev_hash=prev_hash,
        hash=current_hash,
    )

    session.add(audit_entry)
    await session.flush()
    return audit_entry


record_audit_log = record_audit_event


async def verify_audit_integrity(session: AsyncSession) -> dict[str, Any]:
    """Verify entire audit log table against the cryptographic hash chain."""
    stmt = select(AuditLog).order_by(AuditLog.id.asc())
    result = await session.execute(stmt)
    entries = result.scalars().all()

    total_count = len(entries)
    if total_count == 0:
        return {"valid": True, "total_records": 0, "status": "Empty audit log"}

    expected_prev = GENESIS_HASH
    for idx, row in enumerate(entries):
        # Genesis row check
        if idx == 0 and row.actor == "system_bootstrap":
            expected_prev = str(row.hash)
            continue

        row_prev_hash = str(row.prev_hash)
        if row_prev_hash != expected_prev:
            return {
                "valid": False,
                "total_records": total_count,
                "error": f"Chain broken at record id {row.id}: prev_hash mismatch",
                "record_id": int(row.id),  # type: ignore[arg-type]
            }

        row_details: dict[str, Any] = dict(row.details) if isinstance(row.details, dict) else {}
        canonical_ts = row_details.get("_ts") or normalize_timestamp_str(row.timestamp)

        recalculated = compute_chain_hash(
            prev_hash=row_prev_hash,
            actor=str(row.actor),
            action=str(row.action),
            doc_id=str(row.doc_id) if row.doc_id else None,
            output_id=str(row.output_id) if row.output_id else None,
            timestamp_iso=canonical_ts,
            source_hash=str(row.source_hash) if row.source_hash else None,
            details=row_details,
        )

        if str(row.hash) != recalculated:
            return {
                "valid": False,
                "total_records": total_count,
                "error": f"Tampered record at id {row.id}: hash mismatch",
                "record_id": int(row.id),  # type: ignore[arg-type]
            }

        expected_prev = str(row.hash)

    return {
        "valid": True,
        "total_records": total_count,
        "latest_hash": expected_prev,
        "status": "All records cryptographically verified",
    }
