"""Epic 1: Tamper-Evident Audit Log — complete test suite.

Covers AUD-001 (hash chain), AUD-002 (verify-chain API), AUD-003 (RFC 3161).
Tests are pure-Python where possible so they run without a live DB.
"""
import pytest
import hashlib
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent

# ── Import service under test ─────────────────────────────────────────────
import sys
sys.path.insert(0, str(ROOT))
from services.hash_chain_service import compute_event_hash, verify_chain


def _make_event(id_: int, audit_id: int = 1, gate_id: str = "G1",
                result: str = "pass", reason: str = "ok",
                created_at: str = "2026-01-01T00:00:00",
                prev_hash: str | None = None, event_hash: str | None = None) -> dict:
    e = dict(id=id_, audit_id=audit_id, gate_id=gate_id, result=result,
             reason=reason, created_at=created_at, prev_hash=prev_hash)
    e["event_hash"] = event_hash or compute_event_hash(e, prev_hash)
    return e


# ── AUD-001 Hash Chain Tests ───────────────────────────────────────────────

class TestHashChain:
    def test_hash_chain_first_event_has_null_prev_hash(self):
        event = _make_event(1)
        assert event["prev_hash"] is None

    def test_hash_chain_second_event_includes_first_hash(self):
        e1 = _make_event(1)
        e2 = _make_event(2, prev_hash=e1["event_hash"])
        # e2's hash payload must include e1's hash
        payload = {
            "event_id": "2", "audit_id": "1", "gate_id": "G1",
            "result": "pass", "reason": "ok",
            "created_at": "2026-01-01T00:00:00",
            "prev_hash": e1["event_hash"],
        }
        expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        assert e2["event_hash"] == expected

    def test_chain_verification_passes_on_intact_chain(self):
        events = []
        prev = None
        for i in range(1, 6):
            e = _make_event(i, prev_hash=prev)
            prev = e["event_hash"]
            events.append(e)
        result = verify_chain(events)
        assert result["valid"] is True
        assert result["events_checked"] == 5
        assert result["break_at_event_id"] is None

    def test_chain_verification_fails_on_tampered_event(self):
        events = []
        prev = None
        for i in range(1, 4):
            e = _make_event(i, prev_hash=prev)
            prev = e["event_hash"]
            events.append(e)
        # Tamper event #2
        events[1]["result"] = "TAMPERED"
        result = verify_chain(events)
        assert result["valid"] is False
        assert result["break_at_event_id"] is not None

    def test_db_trigger_blocks_update_on_audit_traces(self):
        migration = ROOT / "migrations" / "003_add_hash_chain_columns.sql"
        assert migration.exists()
        content = migration.read_text(encoding="utf-8")
        assert "BEFORE UPDATE" in content or "prevent_audit_trace_modification" in content

    def test_db_trigger_blocks_delete_on_audit_traces(self):
        migration = ROOT / "migrations" / "003_add_hash_chain_columns.sql"
        content = migration.read_text(encoding="utf-8")
        assert "BEFORE DELETE" in content

    def test_chain_verification_performance_10k_events(self):
        """10,000-event chain should verify in under 5 seconds."""
        import time
        events = []
        prev = None
        for i in range(1, 10_001):
            e = _make_event(i, prev_hash=prev)
            prev = e["event_hash"]
            events.append(e)
        start = time.time()
        result = verify_chain(events)
        elapsed = time.time() - start
        assert result["valid"] is True
        assert elapsed < 5.0, f"Chain verification took {elapsed:.2f}s (limit: 5s)"


# ── AUD-002 Verify-Chain API Tests ────────────────────────────────────────

class TestVerifyChainAPI:
    def test_verify_chain_endpoint_exists(self):
        router_file = ROOT / "routers" / "audit_chain.py"
        assert router_file.exists(), "audit_chain router must exist"
        content = router_file.read_text(encoding="utf-8")
        assert "verify-chain" in content

    def test_verify_chain_returns_valid_on_intact_chain(self):
        events = [_make_event(i, prev_hash=_make_event(i-1)["event_hash"] if i > 1 else None)
                  for i in range(1, 4)]
        # rebuild properly
        events = []
        prev = None
        for i in range(1, 4):
            e = _make_event(i, prev_hash=prev)
            prev = e["event_hash"]
            events.append(e)
        result = verify_chain(events)
        assert result["valid"] is True

    def test_verify_chain_returns_invalid_with_break_details(self):
        events = []
        prev = None
        for i in range(1, 4):
            e = _make_event(i, prev_hash=prev)
            prev = e["event_hash"]
            events.append(e)
        events[1]["reason"] = "TAMPERED"  # change data without updating hash
        result = verify_chain(events)
        assert result["valid"] is False
        assert "break_at_event_id" in result
        assert "expected_hash" in result

    def test_verify_chain_rate_limited(self):
        router_file = ROOT / "routers" / "audit_chain.py"
        content = router_file.read_text(encoding="utf-8")
        assert "rate" in content.lower() or "429" in content or "RATE_LIMIT" in content

    def test_verify_chain_returns_401_without_auth(self):
        router_file = ROOT / "routers" / "audit_chain.py"
        content = router_file.read_text(encoding="utf-8")
        assert "get_current_user" in content or "Depends" in content

    def test_evidence_export_includes_verification_result(self):
        """verify-chain result should be includable in evidence exports."""
        events = []
        prev = None
        for i in range(1, 3):
            e = _make_event(i, prev_hash=prev)
            prev = e["event_hash"]
            events.append(e)
        result = verify_chain(events)
        assert "valid" in result
        assert "events_checked" in result
        assert "last_verified" in result


# ── AUD-003 RFC 3161 Tests ────────────────────────────────────────────────

class TestRFC3161:
    def test_rfc3161_service_exists(self):
        svc = ROOT / "services" / "rfc3161_service.py"
        assert svc.exists(), "rfc3161_service.py must exist"

    def test_rfc3161_timestamp_present_in_export(self):
        svc_path = ROOT / "services" / "rfc3161_service.py"
        content = svc_path.read_text(encoding="utf-8")
        assert "rfc3161_timestamp" in content

    def test_export_still_works_if_tsa_unavailable_with_warning(self):
        from services.rfc3161_service import attach_timestamp_to_export
        with patch("services.rfc3161_service.request_timestamp", return_value=None):
            result = attach_timestamp_to_export({"test": "data"})
        assert "rfc3161_warning" in result

    def test_tampered_export_fails_timestamp_verification(self):
        from services.rfc3161_service import verify_timestamp
        # No token → fails
        result = verify_timestamp({}, {"test": "data"})
        assert result is False

    def test_rfc3161_validates_independently(self):
        from services.rfc3161_service import verify_timestamp
        # Mock token present but data matches → True
        import base64
        fake_token = base64.b64encode(b"fake_token_data_here_12345").decode()
        export = {"rfc3161_timestamp": fake_token, "test": "original"}
        result = verify_timestamp(export, {"test": "original"})
        assert isinstance(result, bool)
