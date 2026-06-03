"""
Enterprise Dashboard & Enhanced Trace routes.

GET /api/v1/dashboard/kpis                  — KPI summary bar
GET /api/v1/dashboard/audits                — enhanced audit list (sortable, filterable)
GET /api/v1/dashboard/audits/{id}/trace     — full chain-of-thought trace (never truncated)
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Audit, AuditTrace, EnhancedTrace, ScanReport, User
from schemas import AuditDashboardItemOut, DashboardKPIOut, EnhancedTraceOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

_FAILED_RESULTS = {"fail", "warn", "flagged", "triggered"}


# ── Risk colour mapping ───────────────────────────────────────────────────────


def _risk_color(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 85:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


# ── Chain-of-Thought synthesis ────────────────────────────────────────────────


def _synthesize_cot(traces: list[AuditTrace]) -> dict[str, Any]:
    """Build chain-of-thought JSON from existing AuditTrace records."""
    by_gate: dict[int | None, list[AuditTrace]] = defaultdict(list)
    for t in traces:
        by_gate[t.gate_id].append(t)

    # Sort gate buckets: real gates (1-4) first, None-keyed summary rows last
    steps = []
    sorted_keys = sorted((k for k in by_gate if k is not None)) + \
                  ([None] if None in by_gate else [])
    for gate_id in sorted_keys:
        gate_traces = by_gate[gate_id]
        gate_name = gate_traces[0].gate_name

        # Gate-level result: worst of all checks
        gate_result = "pass"
        for t in gate_traces:
            if t.result in ("fail", "flagged", "triggered"):
                gate_result = "fail"
                break
            if t.result == "warn" and gate_result == "pass":
                gate_result = "warn"

        failed = sum(1 for t in gate_traces if t.result in _FAILED_RESULTS)
        passed = len(gate_traces) - failed

        steps.append({
            "step": gate_id,
            "gate": gate_name,
            "result": gate_result,
            "passed_count": passed,
            "failed_count": failed,
            "timestamp": gate_traces[0].created_at.isoformat() if gate_traces[0].created_at else None,
            "checks": [
                {
                    "id": str(t.id),
                    "type": t.check_type,
                    "name": t.check_name,
                    "result": t.result,
                    "reason": t.reason,
                    "detail": t.detail_json,
                    "remediation_hint": t.remediation_hint,
                    "is_remediated": t.is_remediated,
                }
                for t in gate_traces
            ],
        })

    return {
        "steps": steps,
        "total_checks": len(traces),
        "failed_checks": sum(1 for t in traces if t.result in _FAILED_RESULTS),
        "gate_count": len(steps),
    }


def _generate_executive_summary(report: ScanReport, traces: list[AuditTrace]) -> str:
    """Generate a human-readable executive summary from report scalars."""
    risk_score = report.overall_risk_score or 0.0
    mit_cov = report.mit_coverage_score or 0.0
    delta = report.fixed_delta or 0.0
    conf = report.confidence_score or 0.0

    risk_level = "HIGH" if risk_score < 50 else ("MODERATE" if risk_score < 85 else "LOW")
    delta_dir = "positive" if delta > 0 else "negative"
    delta_note = (
        "Similar historical incidents were largely resolved."
        if delta > 0
        else "Similar incidents remain unresolved — ongoing risk pattern."
    )

    failed_traces = [t for t in traces if t.result in _FAILED_RESULTS]
    remediated = sum(1 for t in failed_traces if t.is_remediated)
    pending = len(failed_traces) - remediated

    summary = (
        f"RISK ASSESSMENT: {risk_level} (Score {risk_score:.1f}/100)\n\n"
        f"This audit evaluated {len(traces)} checks across {len(set(t.gate_id for t in traces if t.gate_id is not None))} gates. "
        f"MIT AI Risk coverage stands at {mit_cov:.1f}% of assessed domains. "
        f"The fixed-delta is {delta:+.3f} ({delta_dir}): {delta_note} "
        f"Model confidence is {conf:.1%}.\n\n"
        f"FINDINGS: {len(failed_traces)} exceptions detected, "
        f"{remediated} remediated, {pending} pending resolution.\n\n"
    )

    # Gate outcomes (exclude None-keyed summary rows like Explain / Remediate)
    by_gate: dict[int | None, list[AuditTrace]] = defaultdict(list)
    for t in traces:
        by_gate[t.gate_id].append(t)

    summary += "GATE OUTCOMES:\n"
    for gate_id in sorted(k for k in by_gate if k is not None):
        gate_traces = by_gate[gate_id]
        gate_name = gate_traces[0].gate_name
        gate_failed = sum(1 for t in gate_traces if t.result in _FAILED_RESULTS)
        icon = "✓" if gate_failed == 0 else ("⚠" if gate_failed <= 2 else "✗")
        summary += f"  {icon} Gate {gate_id} — {gate_name}: {gate_failed} exception(s)\n"

    return summary


def _build_input_summary(report: ScanReport) -> dict[str, Any]:
    """Extract sample metadata from report_json (no raw text stored)."""
    rj = report.report_json or {}
    gates = rj.get("gates", [])
    gate1 = next((g for g in gates if g.get("gate_id") == 1), {})
    details = gate1.get("details", {})
    return {
        "note": "Raw samples are not persisted after audit completion (PII compliance).",
        "sample_count": rj.get("sample_count", 0),
        "dataset_name": rj.get("dataset_name"),
        "batch_id": rj.get("batch_id"),
        "quality_details": {
            "total_samples": details.get("total_samples"),
            "valid_samples": details.get("valid_samples"),
            "blank_samples": details.get("blank_samples"),
            "duplicate_rate": details.get("duplicate_rate"),
        },
    }


def _build_output_summary(report: ScanReport) -> dict[str, Any]:
    """Extract output/results summary from report_json."""
    rj = report.report_json or {}
    bayesian = rj.get("bayesian_scores", {})
    mit = rj.get("mit_coverage", {})
    return {
        "overall_risk_score": report.overall_risk_score,
        "confidence_score": report.confidence_score,
        "mit_coverage_score": report.mit_coverage_score,
        "fixed_delta": report.fixed_delta,
        "bayesian_overall": bayesian.get("overall"),
        "covered_domains": mit.get("covered_domains", []),
        "total_risks_flagged": mit.get("total_risks_flagged"),
        "remediations_count": len(rj.get("remediations", [])),
    }


# ── KPI Endpoint ──────────────────────────────────────────────────────────────


@router.get(
    "/kpis",
    response_model=DashboardKPIOut,
    dependencies=[Depends(require_role("super_admin", "operator", "demo_viewer"))],
    summary="KPI summary bar for the enterprise audit dashboard",
)
def get_dashboard_kpis(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardKPIOut:
    """
    Returns aggregated KPIs for the authenticated tenant plus a 30-day
    risk-score trend series for the trend chart.
    """
    tenant_id = current_user.tenant_id

    audits = db.query(Audit).filter(Audit.tenant_id == tenant_id).all()
    total = len(audits)
    completed = sum(1 for a in audits if a.status == "completed")
    failed = sum(1 for a in audits if a.status == "failed")

    # Aggregate report metrics for completed audits
    reports = (
        db.query(ScanReport)
        .join(Audit, ScanReport.audit_id == Audit.id)
        .filter(Audit.tenant_id == tenant_id, Audit.status == "completed")
        .all()
    )
    avg_risk = (
        sum(r.overall_risk_score for r in reports if r.overall_risk_score is not None)
        / max(len([r for r in reports if r.overall_risk_score is not None]), 1)
        if reports
        else None
    )
    avg_mit = (
        sum(r.mit_coverage_score for r in reports if r.mit_coverage_score is not None)
        / max(len([r for r in reports if r.mit_coverage_score is not None]), 1)
        if reports
        else None
    )

    # Pending remediations across all completed audits
    audit_ids = [a.id for a in audits if a.status == "completed"]
    pending_rem = 0
    if audit_ids:
        pending_rem = (
            db.query(AuditTrace)
            .filter(
                AuditTrace.audit_id.in_(audit_ids),
                AuditTrace.result.in_(list(_FAILED_RESULTS)),
                AuditTrace.is_remediated == False,  # noqa: E712
            )
            .count()
        )

    # 30-day risk score trend (one data point per day with a completed audit)
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
    trend_data: dict[str, list[float]] = defaultdict(list)
    for r in reports:
        audit = db.get(Audit, r.audit_id)
        if not audit or not audit.completed_at:
            continue
        if audit.completed_at < cutoff:
            continue
        day_key = audit.completed_at.strftime("%Y-%m-%d")
        if r.overall_risk_score is not None:
            trend_data[day_key].append(r.overall_risk_score)

    risk_trend = [
        {"date": d, "avg_risk_score": round(sum(scores) / len(scores), 2)}
        for d, scores in sorted(trend_data.items())
    ]

    return DashboardKPIOut(
        total_audits=total,
        completed_audits=completed,
        failed_audits=failed,
        avg_risk_score=round(avg_risk, 2) if avg_risk is not None else None,
        avg_mit_coverage=round(avg_mit, 2) if avg_mit is not None else None,
        pending_remediations=pending_rem,
        risk_trend=risk_trend,
    )


# ── Enhanced Audit List ───────────────────────────────────────────────────────


@router.get(
    "/audits",
    response_model=list[AuditDashboardItemOut],
    dependencies=[Depends(require_role("super_admin", "operator", "demo_viewer"))],
    summary="Enhanced audit list with risk colour, exception counts, remediation status",
)
def list_dashboard_audits(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: str | None = Query(default=None, description="Filter by status: completed|failed|pending|running"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditDashboardItemOut]:
    """
    Returns audits enriched with per-row metrics needed for the dashboard table:
    risk colour, exception count, remediation progress, confidence.
    """
    q = (
        db.query(Audit)
        .filter(Audit.tenant_id == current_user.tenant_id)
        .order_by(Audit.created_at.desc())
    )
    if status_filter:
        q = q.filter(Audit.status == status_filter)
    audits = q.offset(offset).limit(limit).all()

    items: list[AuditDashboardItemOut] = []
    for audit in audits:
        report = db.query(ScanReport).filter(ScanReport.audit_id == audit.id).first()

        risk_score = report.overall_risk_score if report else None
        mit_cov = report.mit_coverage_score if report else None
        confidence = report.confidence_score if report else None

        # Exception metrics from trace records
        all_traces = (
            db.query(AuditTrace).filter(AuditTrace.audit_id == audit.id).all()
            if audit.status == "completed"
            else []
        )
        exceptions = sum(1 for t in all_traces if t.result in _FAILED_RESULTS)
        remediated = sum(1 for t in all_traces if t.result in _FAILED_RESULTS and t.is_remediated)

        items.append(
            AuditDashboardItemOut(
                id=audit.id,
                dataset_name=audit.dataset_name,
                audit_type="AI Risk Audit",
                created_at=audit.created_at,
                completed_at=audit.completed_at,
                status=audit.status,
                overall_risk_score=risk_score,
                risk_color=_risk_color(risk_score),
                mit_coverage_score=mit_cov,
                exceptions_count=exceptions,
                remediated_count=remediated,
                remediation_required=(exceptions - remediated) > 0,
                confidence_score=confidence,
            )
        )
    return items


# ── Full Chain-of-Thought Trace ───────────────────────────────────────────────


@router.get(
    "/audits/{audit_id}/trace",
    response_model=EnhancedTraceOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Full, untruncated chain-of-thought trace for an audit",
)
def get_enhanced_trace(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EnhancedTraceOut:
    """
    Returns the complete chain-of-thought explainability trace for an audit.

    On first access the trace is synthesised from AuditTrace records and
    the ScanReport JSON, then persisted for sub-millisecond subsequent reads.
    Zero truncation — every check, every result, every remediation hint.
    """
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Audit is {audit.status} — trace available only for completed audits.",
        )

    # Return cached enhanced trace if it exists
    existing = db.query(EnhancedTrace).filter(EnhancedTrace.audit_id == audit_id).first()
    if existing:
        return EnhancedTraceOut.model_validate(existing)

    # Synthesise from AuditTrace + ScanReport (first access)
    traces = (
        db.query(AuditTrace)
        .filter(AuditTrace.audit_id == audit_id)
        .order_by(AuditTrace.gate_id, AuditTrace.created_at)
        .all()
    )
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Audit report not found")

    cot = _synthesize_cot(traces)
    exec_summary = _generate_executive_summary(report, traces)
    input_summary = _build_input_summary(report)
    output_summary = _build_output_summary(report)

    # Build a raw "prompt" summary representing what was submitted to the pipeline
    raw_prompt = (
        f"SARO 4-Gate Audit Pipeline\n"
        f"Dataset: {audit.dataset_name or 'unnamed'} | "
        f"Batch: {audit.batch_id or 'auto'} | "
        f"Samples: {audit.sample_count}\n\n"
        f"Gates executed:\n"
        + "\n".join(
            f"  Gate {s['step']}: {s['gate']} — {len(s['checks'])} checks"
            for s in cot["steps"]
        )
    )

    # Full structured response representing the pipeline output
    raw_response = json.dumps(
        {
            "audit_id": str(audit_id),
            "chain_of_thought": cot,
            "report_summary": output_summary,
        },
        indent=2,
        default=str,
    )

    enhanced = EnhancedTrace(
        audit_id=audit_id,
        confidence=report.confidence_score,
        model_version="saro-engine-1.0",
        executive_summary=exec_summary,
        chain_of_thought=cot,
        client_input_summary=input_summary,
        client_output_summary=output_summary,
        raw_prompt=raw_prompt,
        raw_response=raw_response,
    )
    db.add(enhanced)
    db.commit()
    db.refresh(enhanced)

    logger.info("Synthesised and cached EnhancedTrace for audit %s", audit_id)
    return EnhancedTraceOut.model_validate(enhanced)
