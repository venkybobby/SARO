"""
AI Insights derivation — pure, deterministic, read-only.

Insights are computed from data SARO already holds (Audit + ScanReport +
AuditTrace); no external AI model is ever called (SARO non-negotiable #1).
Approved language only: insights are evidence with remediation *guidance* —
human validation is always required (COMPLIANCE_CLAIMS_MATRIX.md).
"""

from __future__ import annotations

from typing import Any

# Mirrors routers/risks.py severity bands (risk score is 0–1 or 0–100).
_SEV_THRESHOLDS = [(70, "critical"), (50, "high"), (30, "medium"), (0, "low")]

# Result values that make a trace count as a finding worth surfacing.
FLAGGED_RESULTS = frozenset({"fail", "warn", "flagged", "triggered"})

# Order in which flagged traces are picked as the insight's headline finding.
_RESULT_PRIORITY = {"fail": 0, "triggered": 1, "flagged": 2, "warn": 3}

# Frameworks SARO maps evidence to (reference only — never conformance claims).
KNOWN_FRAMEWORKS = ("NIST AI RMF", "EU AI Act", "ISO 42001", "AIGP")

# Risk score (0–100) at or above which an audit yields an insight even
# without flagged traces.
INSIGHT_SCORE_FLOOR = 30


def score_to_pct(score: float | None) -> int | None:
    if score is None:
        return None
    return round(score * 100) if score <= 1 else round(score)


def score_to_severity(score: float | None) -> str:
    pct = score_to_pct(score)
    if pct is None:
        return "medium"
    for threshold, label in _SEV_THRESHOLDS:
        if pct >= threshold:
            return label
    return "low"


def insight_id_for_audit(audit_id: Any) -> str:
    return f"INS-{str(audit_id)[:8].upper()}"


def risk_id_for_audit(audit_id: Any) -> str:
    return f"R-{str(audit_id)[:6].upper()}"


def detect_framework(traces: list[dict]) -> tuple[str | None, str | None]:
    """Return (framework, section_hint) from compliance_rule traces, if any."""
    for trace in traces:
        if trace.get("check_type") != "compliance_rule":
            continue
        haystack = f"{trace.get('gate_name', '')} {trace.get('check_name', '')}"
        for fw in KNOWN_FRAMEWORKS:
            if fw.lower() in haystack.lower():
                return fw, trace.get("check_name") or None
    return None, None


def _headline_trace(flagged: list[dict]) -> dict | None:
    if not flagged:
        return None
    return min(flagged, key=lambda t: _RESULT_PRIORITY.get(t.get("result", ""), 9))


def build_insight(
    audit: dict,
    report: dict | None,
    traces: list[dict],
    action_status: str | None,
) -> dict | None:
    """
    Derive a single insight dict for an audit, or None when the audit does
    not warrant one (no report, no confidence context, or nothing flagged).

    Compliance NFR (STORY-001): an insight is never emitted without a
    confidence score — guidance must always carry its uncertainty context.
    """
    if report is None:
        return None
    confidence = report.get("confidence_score")
    if confidence is None:
        return None

    flagged = [t for t in traces if t.get("result") in FLAGGED_RESULTS]
    pct = score_to_pct(report.get("overall_risk_score"))
    if not flagged and (pct is None or pct < INSIGHT_SCORE_FLOOR):
        return None

    dataset = audit.get("dataset_name") or f"Scan {str(audit['id'])[:8]}"
    top = _headline_trace(flagged)
    if top is not None:
        title = f"{top.get('gate_name', 'Finding')} flagged in {dataset}"
        reason = (
            top.get("reason") or f"{top.get('check_name', 'A check')} did not pass."
        )
    else:
        title = f"Elevated risk score in {dataset}"
        reason = "The overall risk score for this scan is elevated."
    description = (
        f"{reason} SARO scored this output at {pct if pct is not None else '—'}/100."
    )

    framework, framework_section = detect_framework(traces)
    remediation = next(
        (t.get("remediation_hint") for t in flagged if t.get("remediation_hint")), None
    )

    return {
        "id": insight_id_for_audit(audit["id"]),
        "risk_id": risk_id_for_audit(audit["id"]),
        "title": title,
        "description": description,
        "confidence": confidence,
        "basis": f"{len(flagged)} flagged check(s) across scan '{dataset}'",
        "severity": score_to_severity(report.get("overall_risk_score")),
        "framework": framework,
        "framework_section": framework_section,
        "remediation_guidance": remediation,
        "status": action_status or "active",
        "human_review_required": True,
        "_traceability": {
            "engine_version": report.get("engine_version"),
            "assessment_date": report.get("created_at"),
            "audit_id": str(audit["id"]),
        },
    }
