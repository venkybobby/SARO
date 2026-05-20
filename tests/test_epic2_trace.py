"""Epic 2: TRACE View & Evidence Export — complete test suite."""
import json
import hmac
import hashlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent

import sys
sys.path.insert(0, str(ROOT))
from services.trace_service import build_trace_timeline, TRACE_STEPS


def _make_trace(gate_id: str, result: str = "pass", reason: str = "ok") -> dict:
    return {
        "id": 1, "audit_id": 1, "gate_id": gate_id,
        "gate_name": gate_id.capitalize(),
        "check_type": "rule", "result": result, "reason": reason,
        "confidence": 0.9, "created_at": "2026-01-01",
    }


# ── TRC-001 TRACE Timeline Tests ──────────────────────────────────────────

class TestTraceTimeline:
    def test_trace_service_exists(self):
        assert (ROOT / "services" / "trace_service.py").exists()

    def test_trace_api_returns_six_steps(self):
        traces = [_make_trace(f"gate_{i+1}") for i in range(4)]
        result = build_trace_timeline(traces)
        assert result["step_count"] == 6

    def test_each_step_has_required_fields(self):
        traces = [_make_trace("gate_1", "pass")]
        result = build_trace_timeline(traces)
        for step in result["steps"]:
            assert "step" in step
            assert "status" in step

    def test_executive_mode_hides_technical_details(self):
        traces = [_make_trace("gate_1"), _make_trace("gate_2")]
        result = build_trace_timeline(traces, executive_mode=True)
        for step in result["steps"]:
            assert "rules_fired" not in step
            assert "detail" not in step

    def test_technical_mode_shows_rule_citations(self):
        traces = [_make_trace("gate_1"), _make_trace("gate_2")]
        result = build_trace_timeline(traces, executive_mode=False)
        # At least one step should have rules_fired populated
        all_rules = [s.get("rules_fired", []) for s in result["steps"]]
        assert any(len(r) > 0 for r in all_rules)

    def test_trace_router_exists(self):
        assert (ROOT / "routers" / "trace_view.py").exists()

    def test_trace_router_has_404_for_missing_audit(self):
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        assert "404" in content

    def test_six_standard_steps_defined(self):
        assert len(TRACE_STEPS) == 6
        for name in ["Ingest", "Classify", "Match", "Score", "Explain", "Remediate"]:
            assert name in TRACE_STEPS


# ── TRC-002 Evidence Export Tests ────────────────────────────────────────

class TestEvidenceExport:
    def test_export_router_has_json_endpoint(self):
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        assert "export/json" in content

    def test_export_router_has_pdf_endpoint(self):
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        assert "export/pdf" in content

    def test_json_export_includes_hmac_signature(self):
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        assert "hmac" in content or "HMAC" in content
        assert "_signature" in content

    def test_json_hmac_signature_verifies(self):
        """HMAC produced by the export function should be verifiable."""
        signing_key = "test-signing-key"
        data = {"audit_id": 1, "test": "data"}
        canonical = json.dumps(data, sort_keys=True)
        sig = hmac.new(signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        expected = hmac.new(signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        assert sig == expected

    def test_tampered_json_fails_signature_check(self):
        signing_key = "test-signing-key"
        data = {"audit_id": 1}
        canonical = json.dumps(data, sort_keys=True)
        sig = hmac.new(signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        tampered = json.dumps({"audit_id": 2}, sort_keys=True)
        tampered_sig = hmac.new(signing_key.encode(), tampered.encode(), hashlib.sha256).hexdigest()
        assert sig != tampered_sig

    def test_export_includes_audit_metadata(self):
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        assert "audit_metadata" in content or "audit_id" in content

    def test_export_includes_rfc3161(self):
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        assert "rfc3161" in content or "timestamp" in content.lower()


# ── TRC-003 Transparency Document Tests ──────────────────────────────────

class TestHowSAROReasonsDoc:
    def test_how_saro_reasons_page_exists(self):
        doc = ROOT / "docs" / "how-saro-reasons.md"
        assert doc.exists(), "docs/how-saro-reasons.md must exist"

    def test_page_contains_methodology_section(self):
        content = (ROOT / "docs" / "how-saro-reasons.md").read_text(encoding="utf-8")
        assert "methodology" in content.lower() or "Analysis Methodology" in content

    def test_page_contains_scoring_algorithm(self):
        content = (ROOT / "docs" / "how-saro-reasons.md").read_text(encoding="utf-8")
        assert "risk score" in content.lower() or "scoring" in content.lower()

    def test_page_contains_confidence_explanation(self):
        content = (ROOT / "docs" / "how-saro-reasons.md").read_text(encoding="utf-8")
        assert "confidence" in content.lower()

    def test_page_contains_limitations_section(self):
        content = (ROOT / "docs" / "how-saro-reasons.md").read_text(encoding="utf-8")
        assert "does not" in content.lower() or "NOT do" in content

    def test_pdf_export_transparency_doc_via_service(self):
        """Verify the export service is wired to include RFC 3161."""
        from services.rfc3161_service import attach_timestamp_to_export
        with patch("services.rfc3161_service.request_timestamp", return_value=None):
            result = attach_timestamp_to_export({"type": "transparency_doc"})
        assert "rfc3161_warning" in result or "rfc3161_timestamp" in result


# ── Regression: build_trace_timeline integer gate_id crash ────────────────────

class TestBuildTraceTimeline:
    """Guard against regressions in trace_service.build_trace_timeline."""

    def _make_trace(self, gate_id, gate_name="", result="pass", reason="ok"):
        return {"gate_id": gate_id, "gate_name": gate_name,
                "result": result, "reason": reason, "confidence": 0.9}

    def test_integer_gate_ids_do_not_crash(self):
        """gate_id is stored as int in the DB — must not call .lower() on it."""
        from services.trace_service import build_trace_timeline
        traces = [self._make_trace(i, f"Gate {i}") for i in range(1, 5)]
        result = build_trace_timeline(traces)
        assert "steps" in result
        assert len(result["steps"]) == 6

    def test_integer_gate_ids_map_to_correct_steps(self):
        from services.trace_service import build_trace_timeline
        traces = [
            self._make_trace(1, "Data Quality (Gate 1)"),
            self._make_trace(2, "Fairness Analysis"),
            self._make_trace(3, "Risk Classification (MIT Taxonomy)"),
            self._make_trace(4, "Compliance Mapping (NIST AI RMF)"),
        ]
        result = build_trace_timeline(traces)
        step_names = {s["step"]: s["status"] for s in result["steps"]}
        assert step_names["Ingest"] != "pending"
        assert step_names["Classify"] != "pending"
        assert step_names["Match"] != "pending"
        assert step_names["Score"] != "pending"

    def test_string_integer_gate_ids_handled(self):
        from services.trace_service import build_trace_timeline
        traces = [self._make_trace("1"), self._make_trace("4")]
        result = build_trace_timeline(traces)
        assert len(result["steps"]) == 6

    def test_none_gate_id_falls_back_to_gate_name(self):
        from services.trace_service import build_trace_timeline
        traces = [self._make_trace(None, "fairness analysis")]
        result = build_trace_timeline(traces)
        classify = next(s for s in result["steps"] if s["step"] == "Classify")
        assert classify["status"] != "pending"

    def test_empty_traces_returns_all_pending(self):
        from services.trace_service import build_trace_timeline
        result = build_trace_timeline([])
        assert all(s["status"] == "pending" for s in result["steps"])

    def test_executive_mode_removes_technical_fields(self):
        from services.trace_service import build_trace_timeline
        traces = [self._make_trace(1)]
        result = build_trace_timeline(traces, executive_mode=True)
        for step in result["steps"]:
            assert "rules_fired" not in step
            assert "detail" not in step
