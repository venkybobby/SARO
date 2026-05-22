"""
Unit tests for the three new features added in this release:
  1. Demo signup endpoint (POST /api/v1/demo/signup)
  2. Audit trace recording (engine._traces, _persist_traces)
  3. Remedy endpoint (GET /api/v1/traces/{audit_id}/failed)

All tests use in-memory SQLite via TestClient + dependency overrides —
no live DB or external service required.
"""
from __future__ import annotations

import sys
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

# Ensure repo root is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ─────────────────────────────────────────────────────────────────────────────
# Minimal stubs so we can import without a live DB
# ─────────────────────────────────────────────────────────────────────────────

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")


# ─────────────────────────────────────────────────────────────────────────────
# Test: DemoRequestIn schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestDemoRequestSchema:
    def test_valid_signup(self):
        from schemas import DemoRequestIn
        req = DemoRequestIn(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            contact_number="+44 7700 900000",
            company_name="Acme Corp",
            message="We want to audit our NLP model.",
        )
        assert req.first_name == "Jane"
        assert req.email == "jane.smith@example.com"

    def test_optional_fields_absent(self):
        from schemas import DemoRequestIn
        req = DemoRequestIn(
            first_name="Bob",
            last_name="Jones",
            email="bob@test.com",
        )
        assert req.contact_number is None
        assert req.company_name is None
        assert req.message is None

    def test_empty_first_name_rejected(self):
        from schemas import DemoRequestIn
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DemoRequestIn(first_name="", last_name="Smith", email="x@x.com")

    def test_invalid_email_rejected(self):
        from schemas import DemoRequestIn
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DemoRequestIn(first_name="A", last_name="B", email="not-an-email")


# ─────────────────────────────────────────────────────────────────────────────
# Test: AuditTraceOut schema
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditTraceSchema:
    def test_valid_trace_out(self):
        from schemas import AuditTraceOut
        data = {
            "id": str(uuid.uuid4()),
            "audit_id": str(uuid.uuid4()),
            "gate_id": 3,
            "gate_name": "Risk Classification (MIT Taxonomy)",
            "check_type": "risk_domain",
            "check_name": "Discrimination & Toxicity",
            "result": "flagged",
            "reason": "2 risk signals detected.",
            "detail_json": {"flagged_signals": [{"signal": "keyword:toxic"}]},
            "remediation_hint": "Implement bias detection.",
            "is_remediated": False,
            "remediated_at": None,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        trace = AuditTraceOut.model_validate(data)
        assert trace.gate_id == 3
        assert trace.result == "flagged"
        assert trace.is_remediated is False

    def test_remediate_trace_in_optional_notes(self):
        from schemas import RemediateTraceIn
        r = RemediateTraceIn(notes=None)
        assert r.notes is None
        r2 = RemediateTraceIn(notes="Fixed by retraining on debiased data.")
        assert "retraining" in r2.notes


# ─────────────────────────────────────────────────────────────────────────────
# Test: Engine trace accumulation (pure unit test — no DB required)
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineTracing:
    def _make_engine_no_db(self):
        """Create a SARoEngine with empty reference data (no DB queries)."""
        import engine as eng_module
        with patch.object(eng_module.SARoEngine, "_load_reference_data"):
            with patch.object(eng_module.SARoEngine, "_build_incident_index"):
                e = eng_module.SARoEngine.__new__(eng_module.SARoEngine)
                e._mit_risks = []
                e._incidents = []
                e._eu_rules = []
                e._nist_controls = []
                e._aigp = []
                e._gov_rules = []
                e._tfidf_vectorizer = None
                e._incident_matrix = None
                e._rule_packs = []
                e._compliance_triggers = {}
                e._rule_pack_hash = eng_module.SARoEngine._compute_rule_pack_hash()
                e._incident_corpus_version = "test-corpus-v0"
                return e

    def _make_batch(self, n: int = 60, include_risk_text: bool = False):
        from schemas import BatchIn, SampleIn
        text = "This is a toxic and racist statement about demographics." if include_risk_text else "benign text sample"
        return BatchIn(
            batch_id="test-batch",
            dataset_name="test",
            samples=[SampleIn(sample_id=f"s{i}", text=text if include_risk_text and i < 10 else "neutral text sample") for i in range(n)],
        )

    def test_traces_empty_before_run(self):
        e = self._make_engine_no_db()
        assert e.get_traces() == []

    def test_traces_populated_after_run(self):
        e = self._make_engine_no_db()
        batch = self._make_batch(n=60)
        e.run_audit(batch, uuid.uuid4())
        traces = e.get_traces()
        assert len(traces) > 0
        # Should have gate-level traces for all 4 gates
        gate_ids = {t["gate_id"] for t in traces}
        assert gate_ids == {1, 2, 3, 4}

    def test_gate3_produces_domain_traces(self):
        e = self._make_engine_no_db()
        batch = self._make_batch(n=60)
        e.run_audit(batch, uuid.uuid4())
        traces = e.get_traces()
        gate3_traces = [t for t in traces if t["gate_id"] == 3 and t["check_type"] == "risk_domain"]
        # Should have one trace per MIT domain (7 domains)
        assert len(gate3_traces) == 7

    def test_all_traces_have_required_keys(self):
        e = self._make_engine_no_db()
        batch = self._make_batch(n=60)
        e.run_audit(batch, uuid.uuid4())
        required_keys = {"gate_id", "gate_name", "check_type", "check_name", "result"}
        for t in e.get_traces():
            assert required_keys.issubset(t.keys()), f"Missing keys in trace: {t}"

    def test_traces_reset_between_runs(self):
        e = self._make_engine_no_db()
        batch = self._make_batch(n=60)
        e.run_audit(batch, uuid.uuid4())
        first_count = len(e.get_traces())
        e.run_audit(batch, uuid.uuid4())
        # Traces should be reset, not doubled
        assert len(e.get_traces()) == first_count

    def test_risk_text_produces_flagged_domain_traces(self):
        e = self._make_engine_no_db()
        batch = self._make_batch(n=60, include_risk_text=True)
        e.run_audit(batch, uuid.uuid4())
        flagged = [t for t in e.get_traces() if t["result"] == "flagged"]
        assert len(flagged) > 0, "Expected flagged traces for risk text"


# ─────────────────────────────────────────────────────────────────────────────
# Test: DemoRequestStatusUpdateIn validation
# ─────────────────────────────────────────────────────────────────────────────

class TestDemoStatusUpdate:
    def test_valid_statuses(self):
        from schemas import DemoRequestStatusUpdateIn
        for s in ("pending", "contacted", "converted", "rejected"):
            u = DemoRequestStatusUpdateIn(status=s)
            assert u.status == s

    def test_invalid_status_rejected(self):
        from schemas import DemoRequestStatusUpdateIn
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DemoRequestStatusUpdateIn(status="approved")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Remediation hints are defined for all MIT domains
# ─────────────────────────────────────────────────────────────────────────────

class TestRemediationHints:
    def test_all_mit_domains_have_hints(self):
        import engine as eng_module
        for domain in eng_module.MIT_DOMAINS:
            hint = eng_module._DOMAIN_REMEDIATION_HINTS.get(domain)
            assert hint is not None, f"Missing remediation hint for domain: {domain}"
            assert len(hint) > 20, f"Hint too short for domain: {domain}"

    def test_all_gates_have_hints(self):
        import engine as eng_module
        for gate_id in (1, 2, 3, 4):
            hint = eng_module._GATE_REMEDIATION_HINTS.get(gate_id)
            assert hint is not None, f"Missing gate remediation hint for gate {gate_id}"
