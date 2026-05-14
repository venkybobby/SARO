"""TRACE pipeline service — maps AuditTrace DB records to the 6-step visual timeline."""
from datetime import datetime
from typing import Optional

TRACE_STEPS = ["Ingest", "Classify", "Match", "Score", "Explain", "Remediate"]

GATE_TO_STEP = {
    "gate_1": "Ingest",
    "gate_2": "Classify",
    "gate_3": "Match",
    "gate_4": "Score",
    "ingest": "Ingest",
    "classify": "Classify",
    "match": "Match",
    "score": "Score",
    "explain": "Explain",
    "remediate": "Remediate",
}


def build_trace_timeline(audit_traces: list[dict], executive_mode: bool = False) -> dict:
    """Build a 6-step TRACE timeline from raw audit trace records.

    Args:
        audit_traces: List of AuditTrace dicts from DB
        executive_mode: If True, hide technical details and show business summaries

    Returns:
        Dict with 'steps' (list of 6 step objects) and 'summary'
    """
    # Initialize all 6 steps
    steps = {name: {
        "step": name,
        "status": "pending",
        "processing_time_ms": 0,
        "rules_fired": [],
        "confidence": None,
        "detail": "",
        "executive_summary": "",
    } for name in TRACE_STEPS}

    for trace in audit_traces:
        gate_id = (trace.get("gate_id") or "").lower()
        step_name = GATE_TO_STEP.get(gate_id)
        if not step_name:
            # Try gate_name
            gate_name = (trace.get("gate_name") or "").lower()
            for key in GATE_TO_STEP:
                if key in gate_name:
                    step_name = GATE_TO_STEP[key]
                    break
        if not step_name:
            step_name = "Score"  # default

        step = steps[step_name]
        step["status"] = "pass" if trace.get("result") == "pass" else "fail"
        if trace.get("gate_id"):
            step["rules_fired"].append(trace["gate_id"])
        if trace.get("reason"):
            step["detail"] += trace["reason"] + " "
        step["executive_summary"] = _executive_summary(step_name, trace.get("result"))
        step["confidence"] = trace.get("confidence", 0.85)

    result_steps = list(steps.values())
    for s in result_steps:
        s["detail"] = s["detail"].strip()
        if executive_mode:
            s.pop("rules_fired", None)
            s.pop("detail", None)

    return {
        "steps": result_steps,
        "step_count": len(result_steps),
        "executive_mode": executive_mode,
        "generated_at": datetime.now().isoformat(),
    }


def _executive_summary(step_name: str, result: Optional[str]) -> str:
    status = "completed successfully" if result == "pass" else "identified issues"
    summaries = {
        "Ingest": f"Data ingestion {status}.",
        "Classify": f"Risk classification {status}.",
        "Match": f"Rule matching {status}.",
        "Score": f"Risk scoring {status}.",
        "Explain": f"Findings explanation {status}.",
        "Remediate": f"Remediation recommendations {status}.",
    }
    return summaries.get(step_name, f"{step_name} {status}.")
