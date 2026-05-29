"""SHA-256 hash-chained audit log service.

Each AuditTrace event carries a SHA-256 hash that includes the previous
event's hash, creating a tamper-evident chain.  An attacker who modifies
any historical record will break every subsequent hash, making tampering
detectable by verify_chain().

Canonical payload (v1) — both _persist_traces() and _verify_chain_segment()
MUST use build_event_payload() to construct the dict passed to
compute_event_hash().  Having a single definition prevents silent drift
between the write path and the verify path.

Payload coverage (v1):
  Covered:   id, audit_id, gate_id, gate_name, check_type, check_name,
             result, reason, signal_text, remediation_hint, created_at
  NOT covered: detail_json, top_sample_ids (large JSON blobs, excluded for
             performance; see SARO-AUD-PAYLOAD-SCOPE in the backlog for v2)
  NOT covered: is_remediated, remediated_at, remediated_by_id (mutable
             workflow fields; remediation actions are tracked in a separate
             append-only remediation_events table — see Epic 10 backlog)
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

# Single authoritative sentinel for pre-migration rows.
# Import this constant everywhere instead of duplicating the string literal.
LEGACY_SENTINEL = "LEGACY_PRE_CHAIN"


def build_event_payload(event_data: dict) -> dict:
    """Build the canonical hash payload dict from an event data mapping.

    Used by both _persist_traces() (write path) and _verify_chain_segment()
    (verify path).  Any change to the fields hashed must be made here only.
    """
    return {
        "event_id":        str(event_data.get("id", "")),
        "audit_id":        str(event_data.get("audit_id", "")),
        "gate_id":         str(event_data.get("gate_id", "")),
        "gate_name":       str(event_data.get("gate_name", "")),
        "check_type":      str(event_data.get("check_type", "")),
        "check_name":      str(event_data.get("check_name", "")),
        "result":          str(event_data.get("result", "")),
        "reason":          str(event_data.get("reason") or ""),
        "signal_text":     str(event_data.get("signal_text") or ""),
        "remediation_hint": str(event_data.get("remediation_hint") or ""),
        "created_at":      str(event_data.get("created_at", "")),
    }


def compute_event_hash(event_data: dict, prev_hash: Optional[str]) -> str:
    """Compute SHA-256 hash for an audit event.

    Always call build_event_payload(event_data) before this function to
    ensure the canonical field set is complete and consistent.
    """
    payload = build_event_payload(event_data)
    payload["prev_hash"] = prev_hash or "GENESIS"
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_chain(events: list[dict]) -> dict:
    """Verify the integrity of the audit hash chain (used by unit tests).

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
            "last_verified": datetime.now(timezone.utc).isoformat(),
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
                "last_verified": datetime.now(timezone.utc).isoformat(),
                "break_at_event_id": event.get("id"),
                "expected_hash": expected,
                "actual_hash": actual,
            }
        prev_hash = actual

    return {
        "valid": True,
        "events_checked": len(events),
        "last_verified": datetime.now(timezone.utc).isoformat(),
        "break_at_event_id": None,
        "expected_hash": None,
        "actual_hash": None,
    }
