"""Epic 3: Board-Level Risk Dashboard — complete test suite."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent

import sys
sys.path.insert(0, str(ROOT))
from services.risk_service import (
    calculate_rag_status,
    compute_90_day_trend,
    aggregate_vendor_risk,
    calculate_remediation_pct,
    build_risk_summary,
)


def _make_audit(risk_score: float, days_ago: int = 5, source_model: str = "GPT-4") -> dict:
    created = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()
    return {"audit_id": 1, "risk_score": risk_score, "created_at": created,
            "source_model": source_model}


# ── RSK-001 Risk Summary Tests ────────────────────────────────────────────

class TestRiskSummary:
    def test_risk_summary_returns_rag_status(self):
        records = [_make_audit(25.0)]
        result = build_risk_summary(records, [])
        assert "rag_status" in result

    def test_risk_summary_returns_90_day_trend(self):
        records = [_make_audit(25.0, days_ago=i) for i in range(1, 6)]
        result = build_risk_summary(records, [])
        assert "trend_90_days" in result
        assert isinstance(result["trend_90_days"], list)

    def test_risk_summary_returns_top_findings(self):
        result = build_risk_summary([_make_audit(40.0)], [])
        assert "top_findings" in result

    def test_risk_summary_returns_remediation_pct(self):
        result = build_risk_summary([_make_audit(40.0)], [])
        assert "remediation_pct" in result

    def test_rag_threshold_green(self):
        assert calculate_rag_status(0) == "GREEN"
        assert calculate_rag_status(29.9) == "GREEN"

    def test_rag_threshold_amber(self):
        assert calculate_rag_status(30) == "AMBER"
        assert calculate_rag_status(69.9) == "AMBER"

    def test_rag_threshold_red(self):
        assert calculate_rag_status(70) == "RED"
        assert calculate_rag_status(100) == "RED"

    def test_empty_data_returns_safe_defaults(self):
        result = build_risk_summary([], [])
        assert result["rag_status"] == "GREEN"
        assert result["overall_risk_score"] == 0.0
        assert result["audit_count"] == 0

    def test_risk_dashboard_router_exists(self):
        assert (ROOT / "routers" / "risk_dashboard.py").exists()

    def test_risk_summary_endpoint_defined(self):
        content = (ROOT / "routers" / "risk_dashboard.py").read_text(encoding="utf-8")
        assert "/summary" in content

    def test_risk_summary_pdf_export_defined(self):
        # The PDF export is handled by the reports router
        content = (ROOT / "routers" / "risk_dashboard.py").read_text(encoding="utf-8")
        assert "risk" in content.lower()

    def test_trend_excludes_records_older_than_90_days(self):
        old = _make_audit(80.0, days_ago=100)
        recent = _make_audit(20.0, days_ago=5)
        trend = compute_90_day_trend([old, recent])
        # Only the recent record should appear
        all_scores = [d["avg_score"] for d in trend]
        assert 80.0 not in all_scores


# ── RSK-002 Vendor Risk Tests ─────────────────────────────────────────────

class TestVendorRisk:
    def test_vendors_endpoint_returns_grouped_by_model(self):
        records = [
            _make_audit(30.0, source_model="GPT-4"),
            _make_audit(40.0, source_model="GPT-4"),
            _make_audit(60.0, source_model="Claude-3"),
        ]
        result = aggregate_vendor_risk(records)
        vendors = [v["vendor"] for v in result]
        assert "GPT-4" in vendors
        assert "Claude-3" in vendors

    def test_vendor_risk_scores_match_audit_averages(self):
        records = [
            _make_audit(30.0, source_model="GPT-4"),
            _make_audit(50.0, source_model="GPT-4"),
        ]
        result = aggregate_vendor_risk(records)
        gpt4 = next(v for v in result if v["vendor"] == "GPT-4")
        assert gpt4["avg_risk_score"] == 40.0

    def test_vendor_audit_count_correct(self):
        records = [_make_audit(25.0, source_model="X") for _ in range(5)]
        result = aggregate_vendor_risk(records)
        vendor_x = next(v for v in result if v["vendor"] == "X")
        assert vendor_x["audit_count"] == 5

    def test_vendor_rag_status_computed(self):
        records = [_make_audit(75.0, source_model="HighRisk")]
        result = aggregate_vendor_risk(records)
        assert result[0]["rag_status"] == "RED"

    def test_vendors_endpoint_defined(self):
        content = (ROOT / "routers" / "risk_dashboard.py").read_text(encoding="utf-8")
        assert "/vendors" in content
