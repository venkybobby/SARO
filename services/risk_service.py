"""Risk aggregation service for board-level dashboard."""
from datetime import datetime, timedelta


def calculate_rag_status(risk_score: float) -> str:
    """Calculate RAG (Red/Amber/Green) status from risk score.

    Thresholds per spec:
    - GREEN: score < 30
    - AMBER: 30 <= score < 70
    - RED: score >= 70
    """
    if risk_score < 30:
        return "GREEN"
    elif risk_score < 70:
        return "AMBER"
    return "RED"


def compute_90_day_trend(audit_records: list[dict]) -> list[dict]:
    """Compute a 90-day risk score trend from audit records.

    Args:
        audit_records: List of dicts with 'created_at' (str ISO date) and 'risk_score' (float)

    Returns:
        List of {date: str, avg_score: float, count: int} sorted by date ascending
    """
    if not audit_records:
        return []

    cutoff = datetime.utcnow() - timedelta(days=90)
    daily: dict[str, list[float]] = {}

    for record in audit_records:
        created = record.get("created_at")
        score = record.get("risk_score")
        if not created or score is None:
            continue
        if isinstance(created, str):
            try:
                dt = datetime.fromisoformat(created.split("T")[0])
            except ValueError:
                continue
        else:
            dt = created

        if dt < cutoff:
            continue

        day_key = dt.strftime("%Y-%m-%d")
        daily.setdefault(day_key, []).append(float(score))

    trend = [
        {"date": day, "avg_score": round(sum(scores) / len(scores), 2), "count": len(scores)}
        for day, scores in sorted(daily.items())
    ]
    return trend


def aggregate_top_findings(findings: list[dict], n: int = 5) -> list[dict]:
    """Return the top N open findings by severity score."""
    open_findings = [f for f in findings if f.get("status", "open") == "open"]
    sorted_findings = sorted(open_findings, key=lambda x: x.get("severity", 0), reverse=True)
    return sorted_findings[:n]


def aggregate_vendor_risk(audit_records: list[dict]) -> list[dict]:
    """Aggregate audit data by AI vendor/model.

    Args:
        audit_records: List of dicts with 'source_model' and 'risk_score' fields

    Returns:
        List of {vendor: str, audit_count: int, avg_risk_score: float,
                  rag_status: str, is_new: bool} sorted by avg_risk_score desc
    """
    vendors: dict[str, list[float]] = {}
    seen_previously = set()  # In production this would come from DB

    for record in audit_records:
        vendor = record.get("source_model") or record.get("model_name") or "Unknown"
        score = record.get("risk_score")
        if score is None:
            continue
        vendors.setdefault(vendor, []).append(float(score))

    results = []
    for vendor, scores in vendors.items():
        avg = sum(scores) / len(scores)
        results.append({
            "vendor": vendor,
            "audit_count": len(scores),
            "avg_risk_score": round(avg, 2),
            "rag_status": calculate_rag_status(avg),
            "is_new": vendor not in seen_previously,
        })

    return sorted(results, key=lambda x: x["avg_risk_score"], reverse=True)


def calculate_remediation_pct(findings: list[dict]) -> float:
    """Return percentage of findings that have been remediated."""
    if not findings:
        return 0.0
    remediated = sum(1 for f in findings if f.get("status") == "remediated")
    return round(remediated / len(findings) * 100, 1)


def build_risk_summary(audit_records: list[dict], findings: list[dict]) -> dict:
    """Build the complete risk summary payload for the dashboard.

    Returns safe defaults when no data is available.
    """
    if not audit_records:
        return {
            "rag_status": "GREEN",
            "overall_risk_score": 0.0,
            "trend_90_days": [],
            "top_findings": [],
            "open_findings_count": 0,
            "critical_findings_count": 0,
            "remediation_pct": 0.0,
            "audit_count": 0,
            "vendor_breakdown": [],
            "generated_at": datetime.utcnow().isoformat(),
        }

    scores = [r.get("risk_score", 0) for r in audit_records if r.get("risk_score") is not None]
    overall = sum(scores) / len(scores) if scores else 0.0

    return {
        "rag_status": calculate_rag_status(overall),
        "overall_risk_score": round(overall, 2),
        "trend_90_days": compute_90_day_trend(audit_records),
        "top_findings": aggregate_top_findings(findings),
        # Uncapped count of open findings — the banner needs the real total, not the
        # 5-item top_findings slice (FND-022: "Open Risks" must mean open risks).
        "open_findings_count": sum(
            1 for f in findings if f.get("status", "open") == "open"
        ),
        # Open findings at the top severity rank — backs the "Critical Risks" card
        # so its value matches its label (severity >= 3 == fail/triggered).
        "critical_findings_count": sum(
            1 for f in findings
            if f.get("status", "open") == "open" and (f.get("severity") or 0) >= 3
        ),
        "remediation_pct": calculate_remediation_pct(findings),
        "audit_count": len(audit_records),
        "vendor_breakdown": aggregate_vendor_risk(audit_records),
        "generated_at": datetime.utcnow().isoformat(),
    }
