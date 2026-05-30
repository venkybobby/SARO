"""
Frontend-facing dashboard aggregation endpoints.

GET /api/v1/compliance_matrix  — framework coverage heatmap for RegCoverage component
GET /api/v1/risk_dashboard     — vendor risk scores for EngineScores component
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Audit, AuditMetadata, AuditTrace, ScanReport

router = APIRouter(prefix="/api/v1", tags=["fe-dashboard"])

# Map gate_name substrings → frameworks covered by that gate
_GATE_FRAMEWORK_MAP: dict[str, list[str]] = {
    "Data Quality":       ["ISO 42001"],
    "Fairness":           ["NIST AI RMF 1.0", "EU AI Act"],
    "Risk Classification": ["NIST AI RMF 1.0", "ISO 42001"],
    "Compliance Mapping": ["EU AI Act", "AIGP", "ISO 42001"],
}

_ALL_FRAMEWORKS = ["NIST AI RMF 1.0", "EU AI Act", "ISO 42001", "AIGP"]

_WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _window_cutoff(window: str) -> datetime:
    days = _WINDOW_DAYS.get(window, 7)
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


@router.get(
    "/compliance_matrix",
    summary="Framework coverage for RegCoverage heatmap",
    dependencies=[Depends(require_role("super_admin", "operator", "demo_viewer"))],
)
async def get_compliance_matrix(
    window: str = Query(default="7d", description="7d | 30d | 90d"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    # NOTE: the /compliance-matrix/coverage (hyphen) alias was removed to resolve
    # a route collision with compliance_matrix.py. The React frontend fetches
    # /api/v1/compliance_matrix (underscore) — saro.js has been updated accordingly.
    """
    Aggregate AuditTrace records into per-framework coverage percentages.
    Returns { frameworks: [{name, rules_triggered, rules_total, coverage_pct}], computed_at }.
    """
    tid = current_user.tenant_id
    cutoff = _window_cutoff(window)

    audit_ids = [
        row[0]
        for row in db.query(Audit.id)
        .filter(
            Audit.tenant_id == tid,
            Audit.status == "completed",
            Audit.created_at >= cutoff,
        )
        .all()
    ]

    if not audit_ids:
        empty_frameworks = [
            {"name": fw, "rules_triggered": 0, "rules_total": 0, "coverage_pct": 0.0}
            for fw in _ALL_FRAMEWORKS
        ]
        return {"frameworks": empty_frameworks, "computed_at": datetime.now(tz=timezone.utc).isoformat()}

    traces = (
        db.query(AuditTrace)
        .filter(AuditTrace.audit_id.in_(audit_ids))
        .all()
    )

    # Accumulate pass/total counts per framework
    fw_passed: dict[str, int] = {fw: 0 for fw in _ALL_FRAMEWORKS}
    fw_total:  dict[str, int] = {fw: 0 for fw in _ALL_FRAMEWORKS}

    for t in traces:
        gate = t.gate_name or ""
        for gate_substr, gate_frameworks in _GATE_FRAMEWORK_MAP.items():
            if gate_substr.lower() in gate.lower():
                for fw_name in gate_frameworks:
                    fw_total[fw_name] += 1
                    if t.result not in ("fail", "flagged", "triggered"):
                        fw_passed[fw_name] += 1

    result: list[dict[str, Any]] = []
    for fw_name in _ALL_FRAMEWORKS:
        total: int = fw_total[fw_name]
        passed: int = fw_passed[fw_name]
        pct = round(passed / total * 100, 1) if total else 0.0
        result.append({
            "name": fw_name,
            "rules_triggered": total - passed,
            "rules_total": max(total, 1),
            "coverage_pct": pct,
        })

    return {"frameworks": result, "computed_at": datetime.now(tz=timezone.utc).isoformat()}


@router.get(
    "/risk_dashboard",
    summary="Vendor risk scores for EngineScores panel",
    dependencies=[Depends(require_role("super_admin", "operator", "demo_viewer"))],
)
async def get_risk_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return per-vendor (source_model) avg risk scores plus summary stats.
    Returns { vendors: [{source_model, avg_risk_score}], summary: {avg_risk_score, max_risk_score} }.
    """
    tid = current_user.tenant_id

    rows = (
        db.query(AuditMetadata.source_model, ScanReport.overall_risk_score)
        .select_from(Audit)
        .join(ScanReport, ScanReport.audit_id == Audit.id, isouter=True)
        .join(AuditMetadata, AuditMetadata.audit_id == Audit.id, isouter=True)
        .filter(Audit.tenant_id == tid, Audit.status == "completed")
        .all()
    )

    # Group by source_model
    vendor_scores: dict[str, list[float]] = {}
    for source_model, score in rows:
        key = str(source_model) if source_model else "unknown"
        if score is not None:
            vendor_scores.setdefault(key, []).append(float(score))

    vendors: list[dict[str, Any]] = [
        {
            "source_model": model,
            "avg_risk_score": round(sum(scores) / len(scores), 4),
        }
        for model, scores in sorted(vendor_scores.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    ]

    all_scores: list[float] = [float(v["avg_risk_score"]) for v in vendors]
    summary: dict[str, Any] = {
        "avg_risk_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else None,
        "max_risk_score": max(all_scores) if all_scores else None,
        "vendor_count": len(vendors),
    }

    return {"vendors": vendors, "summary": summary}
