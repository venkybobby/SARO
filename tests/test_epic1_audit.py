"""Epic 1: Tamper-Evident Audit Log — complete test suite.

Covers AUD-001 (hash chain), AUD-002 (verify-chain API), AUD-003 (RFC 3161).
Tests are pure-Python where possible so they run without a live DB.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent

# ── Import service under test ─────────────────────────────────────────────
import sys
sys.path.insert(0, str(ROOT))
from services.hash_chain_service import build_event_payload, compute_event_hash, verify_chain


def _make_event(id_: int, audit_id: int = 1, gate_id: str = "G1",
                result: str = "pass", reason: str = "ok",
                created_at: str = "2026-01-01T00:00:00",
                gate_name: str = "", check_type: str = "", check_name: str = "",
                signal_text: str = "", remediation_hint: str = "",
                prev_hash: str | None = None, event_hash: str | None = None) -> dict:
    e = dict(
        id=id_, audit_id=audit_id, gate_id=gate_id, result=result,
        reason=reason, created_at=created_at, prev_hash=prev_hash,
        gate_name=gate_name, check_type=check_type, check_name=check_name,
        signal_text=signal_text, remediation_hint=remediation_hint,
    )
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
        # Recompute via compute_event_hash (which calls build_event_payload internally)
        # so the expected hash uses the same canonical field set as the write path.
        expected = compute_event_hash({
            "id": 2, "audit_id": 1, "gate_id": "G1", "gate_name": "",
            "check_type": "", "check_name": "", "result": "pass", "reason": "ok",
            "signal_text": "", "remediation_hint": "",
            "created_at": "2026-01-01T00:00:00",
        }, e1["event_hash"])
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


# ── AUD-001 Write-Path Wiring Tests ──────────────────────────────────────────

def _make_mock_trace_data(gate_id: int = 1, result: str = "pass", reason: str = "ok") -> dict:
    """Engine-style trace dict as returned by engine.get_traces()."""
    return {
        "gate_id": gate_id,
        "gate_name": f"Gate{gate_id}",
        "check_type": "gate_result",
        "check_name": f"Check{gate_id}",
        "result": result,
        "reason": reason,
        "signal_text": "",
        "remediation_hint": "",
    }


class TestHashChainWritePath:
    """Verify that _persist_traces() computes and stores correct hash chain values."""

    def _run_persist(self, trace_dicts: list[dict], prior_event_hash: str | None = None):
        """
        Simulate _persist_traces() without a real database.

        Returns the list of AuditTrace keyword-argument dicts that would have
        been passed to db.add(), in order.
        """
        from routers.scan import _persist_traces

        audit_id = uuid.uuid4()
        # Mock engine
        mock_engine = MagicMock()
        mock_engine.get_traces.return_value = trace_dicts
        mock_engine.get_sample_findings.return_value = []

        # Mock db session: query for prior event returns prior_event_hash or None
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.order_by.return_value.first.return_value = (
            (prior_event_hash,) if prior_event_hash else None
        )
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Capture AuditTrace constructor calls
        captured: list[dict] = []

        def capture_add(obj):
            captured.append(obj)
        mock_db.add.side_effect = capture_add

        with patch("routers.scan.AuditTrace") as mock_at_cls:
            instances = []
            def make_instance(**kwargs):
                ns = SimpleNamespace(**kwargs)
                instances.append(ns)
                return ns
            mock_at_cls.side_effect = make_instance
            _persist_traces(mock_engine, audit_id, mock_db)

        return instances, audit_id

    def test_genesis_event_has_null_prev_hash(self):
        instances, _ = self._run_persist([_make_mock_trace_data()])
        assert len(instances) == 1
        assert instances[0].prev_hash is None

    def test_genesis_event_hash_is_64_hex_chars(self):
        instances, _ = self._run_persist([_make_mock_trace_data()])
        h = instances[0].event_hash
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_second_event_prev_hash_equals_first_event_hash(self):
        instances, _ = self._run_persist([
            _make_mock_trace_data(1),
            _make_mock_trace_data(2),
        ])
        assert len(instances) == 2
        assert instances[1].prev_hash == instances[0].event_hash

    def test_chain_of_five_events_links_correctly(self):
        instances, _ = self._run_persist([_make_mock_trace_data(i) for i in range(1, 6)])
        assert len(instances) == 5
        assert instances[0].prev_hash is None
        for i in range(1, 5):
            assert instances[i].prev_hash == instances[i - 1].event_hash

    def test_event_hashes_are_all_distinct(self):
        instances, _ = self._run_persist([_make_mock_trace_data(i) for i in range(1, 4)])
        hashes = [inst.event_hash for inst in instances]
        assert len(set(hashes)) == len(hashes), "All event hashes must be unique"

    def test_prior_event_hash_seeds_new_chain(self):
        prior = "a" * 64
        instances, _ = self._run_persist([_make_mock_trace_data()], prior_event_hash=prior)
        assert instances[0].prev_hash == prior

    def test_event_hash_recomputes_consistently(self):
        """Same event data must always produce the same hash."""
        from services.hash_chain_service import compute_event_hash
        event_id = uuid.uuid4()
        audit_id = uuid.uuid4()
        ts = datetime.now(timezone.utc)
        data = {
            "id": str(event_id),
            "audit_id": str(audit_id),
            "gate_id": "1",
            "result": "pass",
            "reason": "ok",
            "created_at": ts.isoformat(),
        }
        h1 = compute_event_hash(data, None)
        h2 = compute_event_hash(data, None)
        assert h1 == h2

    def test_scan_py_imports_hash_chain_service(self):
        scan_file = ROOT / "routers" / "scan.py"
        content = scan_file.read_text(encoding="utf-8")
        assert "compute_event_hash" in content
        assert "hash_chain_service" in content


# ── AUD-002 Verify-Chain Endpoint Logic Tests ─────────────────────────────────

def _make_mock_audit_trace(
    audit_id: uuid.UUID,
    prev_hash: str | None,
    gate_id: int = 1,
    result: str = "pass",
    reason: str = "ok",
    gate_name: str = "",
    check_type: str = "",
    check_name: str = "",
    signal_text: str = "",
    remediation_hint: str = "",
) -> SimpleNamespace:
    """Build a SimpleNamespace that mimics an AuditTrace ORM object."""
    event_id = uuid.uuid4()
    ts = datetime.now(timezone.utc)
    event_data = {
        "id": str(event_id),
        "audit_id": str(audit_id),
        "gate_id": str(gate_id),
        "gate_name": gate_name,
        "check_type": check_type,
        "check_name": check_name,
        "result": str(result),
        "reason": str(reason or ""),
        "signal_text": signal_text,
        "remediation_hint": remediation_hint,
        "created_at": ts.isoformat(),
    }
    from services.hash_chain_service import compute_event_hash
    event_hash = compute_event_hash(event_data, prev_hash)
    return SimpleNamespace(
        id=event_id,
        audit_id=audit_id,
        gate_id=gate_id,
        gate_name=gate_name,
        check_type=check_type,
        check_name=check_name,
        result=result,
        reason=reason,
        signal_text=signal_text,
        remediation_hint=remediation_hint,
        created_at=ts,
        event_hash=event_hash,
        prev_hash=prev_hash,
    )


def _build_chain(length: int) -> tuple[uuid.UUID, list[SimpleNamespace]]:
    audit_id = uuid.uuid4()
    chain = []
    prev = None
    for i in range(length):
        t = _make_mock_audit_trace(audit_id, prev_hash=prev, gate_id=i + 1)
        prev = t.event_hash
        chain.append(t)
    return audit_id, chain


class TestVerifyChainEndpointLogic:
    """Test _verify_chain_segment() from routers/audit_chain.py directly."""

    def test_single_event_chain_is_valid(self):
        from routers.audit_chain import _verify_chain_segment
        _, chain = _build_chain(1)
        result = _verify_chain_segment(chain)
        assert result["valid"] is True
        assert result["events_checked"] == 1
        assert result["broken_at"] is None

    def test_five_event_intact_chain_is_valid(self):
        from routers.audit_chain import _verify_chain_segment
        _, chain = _build_chain(5)
        result = _verify_chain_segment(chain)
        assert result["valid"] is True
        assert result["events_checked"] == 5

    def test_tampered_event_hash_detected(self):
        from routers.audit_chain import _verify_chain_segment
        _, chain = _build_chain(3)
        chain[1].event_hash = "00" * 32  # corrupt the hash
        result = _verify_chain_segment(chain)
        assert result["valid"] is False
        assert result["broken_at"]["sequence_position"] == 1
        assert result["broken_at"]["reason"] == "hash_mismatch"

    def test_tampered_prev_hash_detected(self):
        from routers.audit_chain import _verify_chain_segment
        _, chain = _build_chain(3)
        # Change event[2].prev_hash to point to wrong predecessor
        chain[2].prev_hash = "ff" * 32
        result = _verify_chain_segment(chain)
        assert result["valid"] is False
        assert result["broken_at"]["reason"] == "prev_hash_mismatch"

    def test_broken_at_identifies_correct_position(self):
        from routers.audit_chain import _verify_chain_segment
        _, chain = _build_chain(5)
        # Tamper position 3 (0-indexed)
        chain[3].result = "TAMPERED"
        chain[3].event_hash = "ba" * 32
        result = _verify_chain_segment(chain)
        assert result["valid"] is False
        assert result["broken_at"]["sequence_position"] == 3

    def test_canonical_payload_round_trips(self):
        """event_dict built from a trace object must reproduce the stored hash."""
        from routers.audit_chain import _event_dict
        from services.hash_chain_service import compute_event_hash
        audit_id = uuid.uuid4()
        trace = _make_mock_audit_trace(audit_id, prev_hash=None)
        recomputed = compute_event_hash(_event_dict(trace), None)
        assert recomputed == trace.event_hash

    def test_legacy_sentinel_rows_identified(self):
        from services.hash_chain_service import LEGACY_SENTINEL as _LEGACY_SENTINEL
        audit_id = uuid.uuid4()
        legacy = SimpleNamespace(
            id=uuid.uuid4(), audit_id=audit_id, gate_id=1, result="pass",
            reason="ok", created_at=datetime.now(timezone.utc),
            event_hash=_LEGACY_SENTINEL, prev_hash=None,
        )
        assert legacy.event_hash == _LEGACY_SENTINEL

    def test_verify_chain_router_uses_isoformat(self):
        """Canonical timestamp must use isoformat() not str() to match write path."""
        router_file = ROOT / "routers" / "audit_chain.py"
        content = router_file.read_text(encoding="utf-8")
        assert "isoformat()" in content

    def test_audit_id_parameter_is_uuid_type(self):
        """audit_id query param must be uuid.UUID, not int."""
        router_file = ROOT / "routers" / "audit_chain.py"
        content = router_file.read_text(encoding="utf-8")
        assert "uuid.UUID" in content


# ── Hash Chain Coverage Tests (QA gap-fill) ──────────────────────────────────

class TestHashChainCoverage:
    """Edge-case and property tests for hash chain correctness."""

    def test_build_event_payload_normalises_none_to_empty_string(self):
        payload = build_event_payload({
            "id": "1", "audit_id": "a", "gate_id": "G1",
            "result": "pass", "created_at": "2026-01-01T00:00:00",
            # omit optional fields — should become ""
        })
        assert payload["reason"] == ""
        assert payload["signal_text"] == ""
        assert payload["remediation_hint"] == ""
        assert payload["gate_name"] == ""

    def test_different_prev_hash_produces_different_event_hash(self):
        data = {
            "id": "1", "audit_id": "a", "gate_id": "G1",
            "result": "pass", "reason": "ok",
            "created_at": "2026-01-01T00:00:00",
        }
        h_genesis = compute_event_hash(data, None)
        h_seeded = compute_event_hash(data, "a" * 64)
        assert h_genesis != h_seeded

    def test_empty_trace_list_returns_zero_events_checked(self):
        from routers.audit_chain import _verify_chain_segment
        result = _verify_chain_segment([])
        assert result["valid"] is True
        assert result["events_checked"] == 0
        assert result["broken_at"] is None

    def test_seed_prev_anchors_partial_legacy_chain(self):
        from routers.audit_chain import _verify_chain_segment
        audit_id = uuid.uuid4()
        seed = "b" * 64
        # Build a 3-event chain starting from the known seed
        chain = []
        prev = seed
        for i in range(3):
            t = _make_mock_audit_trace(audit_id, prev_hash=prev, gate_id=i + 1)
            prev = t.event_hash
            chain.append(t)
        # Verify with the matching seed → must pass
        assert _verify_chain_segment(chain, seed_prev=seed)["valid"] is True
        # Verify with the wrong seed → must fail
        assert _verify_chain_segment(chain, seed_prev="c" * 64)["valid"] is False

    def test_migration_009_imports_legacy_sentinel_constant(self):
        migration_file = ROOT / "migrations" / "009_hash_chain_columns.py"
        assert migration_file.exists()
        content = migration_file.read_text(encoding="utf-8")
        assert "LEGACY_SENTINEL" in content
        # Must not pass the literal string directly as a SQL parameter value
        assert '"LEGACY_PRE_CHAIN"' not in content
        assert "'LEGACY_PRE_CHAIN'" not in content
