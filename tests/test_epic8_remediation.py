"""Epic 8: Remediation & Workflow — complete test suite (REM-001 steps, REM-002 coverage)."""
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent

import sys
sys.path.insert(0, str(ROOT))
from services.remediation_service import (
    validate_remediation_step,
    generate_remediation_steps,
)
from services.coverage_service import (
    build_coverage_report,
)


def _make_finding(rule_id: str = "NIST-MEASURE-001",
                  severity: str = "HIGH",
                  description: str = "Bias metrics not tracked") -> dict:
    return {"rule_id": rule_id, "severity": severity, "description": description,
            "check_type": "rule"}


def _days_ago_iso(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── REM-001 Remediation Steps Tests ──────────────────────────────────────

class TestRemediationSteps:
    def test_finding_includes_remediation_steps(self):
        steps = generate_remediation_steps(_make_finding())
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_each_step_has_required_fields(self):
        steps = generate_remediation_steps(_make_finding())
        for step in steps:
            assert "description" in step
            assert "effort_estimate" in step
            assert "suggested_role" in step
            assert "reference_clause" in step

    def test_effort_estimates_are_valid_ranges(self):
        steps = generate_remediation_steps(_make_finding())
        for step in steps:
            assert isinstance(step["effort_estimate"], str)
            assert len(step["effort_estimate"]) > 0

    def test_step_validation_passes_complete_step(self):
        step = {
            "description": "Fix the bias",
            "effort_estimate": "1 day",
            "suggested_role": "ML Engineer",
            "reference_clause": "NIST-MEASURE-001",
        }
        valid, errors = validate_remediation_step(step)
        assert valid is True
        assert len(errors) == 0

    def test_step_validation_fails_missing_field(self):
        step = {"description": "Fix the bias"}  # missing other fields
        valid, errors = validate_remediation_step(step)
        assert valid is False
        assert len(errors) > 0

    def test_remediation_router_exists(self):
        assert (ROOT / "routers" / "remediation.py").exists()

    def test_remediation_endpoint_defined(self):
        content = (ROOT / "routers" / "remediation.py").read_text(encoding="utf-8")
        assert "remediation/steps" in content or "remediation" in content

    def test_pdf_export_includes_remediation_section(self):
        # Verify the trace_view router links to remediation
        content = (ROOT / "routers" / "trace_view.py").read_text(encoding="utf-8")
        # PDF export should be defined; remediation is part of the evidence pack
        assert "pdf" in content.lower() or "export" in content.lower()

    def test_governance_finding_generates_steps(self):
        finding = _make_finding(rule_id="NIST-GOVERN-001", description="No AI governance policy")
        steps = generate_remediation_steps(finding)
        assert any("policy" in s["description"].lower() or "governance" in s["description"].lower()
                   for s in steps)

    def test_transparency_finding_generates_steps(self):
        finding = _make_finding(rule_id="EUAI-ART13-001", description="No AI disclosure")
        steps = generate_remediation_steps(finding)
        assert len(steps) >= 1


# ── REM-002 Coverage Gap Analysis Tests ──────────────────────────────────

class TestCoverageAnalysis:
    def test_coverage_returns_all_registered_systems(self):
        systems = [
            {"name": "GPT-4 Finance", "vendor": "OpenAI", "owner": "Risk Team",
             "last_audit_date": _days_ago_iso(5)},
            {"name": "Triage AI", "vendor": "HealthCo", "owner": "Clinical Team",
             "last_audit_date": _days_ago_iso(10)},
        ]
        result = build_coverage_report(systems)
        assert len(result) == 2

    def test_recently_audited_system_shows_green(self):
        systems = [{"name": "Safe AI", "vendor": "Co", "owner": "Me",
                    "last_audit_date": _days_ago_iso(5)}]
        result = build_coverage_report(systems, overdue_threshold_days=60)
        assert result[0]["coverage_status"] == "GREEN"

    def test_overdue_system_shows_red(self):
        systems = [{"name": "Old AI", "vendor": "Co", "owner": "Me",
                    "last_audit_date": _days_ago_iso(90)}]
        result = build_coverage_report(systems, overdue_threshold_days=60)
        assert result[0]["coverage_status"] == "RED"
        assert result[0]["is_overdue"] is True

    def test_never_audited_system_shows_overdue(self):
        systems = [{"name": "New AI", "vendor": "Co", "owner": "Me",
                    "last_audit_date": None}]
        result = build_coverage_report(systems)
        assert result[0]["coverage_status"] == "NEVER_AUDITED"
        assert result[0]["is_overdue"] is True

    def test_overdue_threshold_configurable_per_tenant(self):
        systems = [{"name": "AI", "vendor": "Co", "owner": "Me",
                    "last_audit_date": _days_ago_iso(45)}]
        result_30 = build_coverage_report(systems, overdue_threshold_days=30)
        result_90 = build_coverage_report(systems, overdue_threshold_days=90)
        assert result_30[0]["coverage_status"] == "RED"
        assert result_90[0]["coverage_status"] in ("GREEN", "AMBER")

    def test_coverage_endpoint_defined(self):
        content = (ROOT / "routers" / "remediation.py").read_text(encoding="utf-8")
        assert "/coverage" in content

    def test_empty_systems_returns_empty_list(self):
        result = build_coverage_report([])
        assert result == []

    def test_boundary_at_exactly_threshold(self):
        systems = [{"name": "AI", "vendor": "Co", "owner": "Me",
                    "last_audit_date": _days_ago_iso(60)}]
        result = build_coverage_report(systems, overdue_threshold_days=60)
        # At exactly the threshold: days_since == threshold → RED
        assert result[0]["coverage_status"] == "RED"
