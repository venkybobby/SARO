"""FND-020: /risk/summary hardcoded ``findings=[]`` — finding metrics always zero.

``get_risk_summary`` called ``build_risk_summary(records, findings=[])``, so
``top_findings`` was always ``[]`` and ``remediation_pct`` always ``0.0`` no matter
how many failing traces existed. The dashboard's "Open Risks"/"Overdue"/critical
counts were therefore structurally zero (and contradicted the hardcoded KPI cards).

Fix: ``_get_finding_records`` pulls real failing traces and feeds them to
``build_risk_summary``; the summary also exposes an uncapped ``open_findings_count``.
"""
from __future__ import annotations

import inspect

import pytest

from routers import risk_dashboard
from services.risk_service import build_risk_summary

pytestmark = pytest.mark.regression


def _audit(score=40.0):
    return {"audit_id": 1, "risk_score": score, "created_at": "2026-06-10", "source_model": "X"}


# ── build_risk_summary now reflects real findings ────────────────────────────

def test_open_findings_count_is_uncapped_and_real():
    findings = [{"status": "open", "severity": i} for i in range(8)]
    result = build_risk_summary([_audit()], findings)
    # top_findings is capped at 5; open_findings_count must be the true total.
    assert len(result["top_findings"]) == 5
    assert result["open_findings_count"] == 8


def test_critical_findings_count_is_top_severity_open_only():
    findings = [
        {"status": "open", "severity": 3},        # critical, open  -> counts
        {"status": "open", "severity": 3},        # critical, open  -> counts
        {"status": "open", "severity": 1},        # low, open       -> no
        {"status": "remediated", "severity": 3},  # critical, fixed -> no
    ]
    result = build_risk_summary([_audit()], findings)
    assert result["critical_findings_count"] == 2
    assert result["open_findings_count"] == 3


def test_remediation_pct_reflects_findings():
    findings = [
        {"status": "remediated", "severity": 3},
        {"status": "open", "severity": 2},
    ]
    result = build_risk_summary([_audit()], findings)
    assert result["remediation_pct"] == 50.0


def test_empty_findings_still_safe():
    result = build_risk_summary([_audit()], [])
    assert result["open_findings_count"] == 0
    assert result["remediation_pct"] == 0.0
    assert result["top_findings"] == []


# ── the route no longer hardcodes findings=[] ────────────────────────────────

def test_risk_summary_route_wires_real_findings():
    src = inspect.getsource(risk_dashboard.get_risk_summary)
    assert "findings=[]" not in src, (
        "get_risk_summary still hardcodes findings=[] (FND-020)"
    )
    assert "_get_finding_records" in src, (
        "get_risk_summary must source findings via _get_finding_records (FND-020)"
    )


def test_finding_records_helper_maps_trace_status():
    # _get_finding_records returns [] for no audits without touching the DB.
    assert risk_dashboard._get_finding_records(db=None, audit_ids=[]) == []
