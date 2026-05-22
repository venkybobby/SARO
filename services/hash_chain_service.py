"""SHA-256 hash-chained audit log service.

Each AuditTrace event carries a SHA-256 hash that includes the previous
event's hash, creating a tamper-evident chain.  An attacker who modifies
any historical record will break every subsequent hash, making tampering
detectable by verify_chain().
"""
import hashlib
import json
from datetime import datetime
from typing import Optional


def compute_event_hash(event_data: dict, prev_hash: Optional[str]) -> str:
    """Compute SHA-256 hash for an audit event.

    The hash includes: event_id, audit_id, gate_id, result, reason, created_at, prev_hash.
    """
    payload = {
        "event_id": str(event_data.get("id", "")),
        "audit_id": str(event_data.get("audit_id", "")),
        "gate_id": str(event_data.get("gate_id", "")),
        "result": str(event_data.get("result", "")),
        "reason": str(event_data.get("reason", "")),
        "created_at": str(event_data.get("created_at", "")),
        "prev_hash": prev_hash or "GENESIS",
    }
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_chain(events: list[dict]) -> dict:
    """Verify the integrity of the audit hash chain.

    Returns:
        {
            "valid": bool,
            "events_checked": int,
            "last_verified": str,  # ISO timestamp
            "break_at_event_id": int | None,
            "expected_hash": str | None,
            "actual_hash": str | None,
        }
    """
    if not events:
        return {
            "valid": True,
            "events_checked": 0,
            "last_verified": datetime.utcnow().isoformat(),
            "break_at_event_id": None,
            "expected_hash": None,
            "actual_hash": None,
        }

    prev_hash = None
    for event in events:
        expected = compute_event_hash(event, prev_hash)
        actual = event.get("event_hash")
        if expected != actual:
            return {
                "valid": False,
                "events_checked": events.index(event),
                "last_verified": datetime.utcnow().isoformat(),
                "break_at_event_id": event.get("id"),
                "expected_hash": expected,
                "actual_hash": actual,
            }
        prev_hash = actual

    return {
        "valid": True,
        "events_checked": len(events),
        "last_verified": datetime.utcnow().isoformat(),
        "break_at_event_id": None,
        "expected_hash": None,
        "actual_hash": None,
    }
