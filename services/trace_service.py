"""TRACE pipeline service — maps AuditTrace DB records to the 6-step visual timeline."""
from datetime import datetime
from typing import Optional

TRACE_STEPS = ["Ingest", "Classify", "Match", "Score", "Explain", "Remediate"]

# Integer gate_id values stored by the engine (1-4) → TRACE step name
_INT_GATE_TO_STEP: dict[int, str] = {
    1: "Ingest",    # Gate 1: Data Quality
    2: "Classify",  # Gate 2: Fairness
    3: "Match",     # Gate 3: Risk Classification (MIT Taxonomy)
    4: "Score",     # Gate 4: Compliance Mapping
}

# Substring patterns in gate_name → TRACE step name (all lowercase)
_GATE_NAME_PATTERNS: list[tuple[str, str]] = [
    ("data quality",      "Ingest"),
    ("gate 1",            "Ingest"),
    ("gate_1",            "Ingest"),
    ("fairness",          "Classify"),
    ("gate 2",            "Classify"),
    ("gate_2",            "Classify"),
    ("risk classif",      "Match"),
    ("mit taxonomy",      "Match"),
    ("gate 3",            "Match"),
    ("gate_3",            "Match"),
    ("compliance",        "Score"),
    ("nist",              "Score"),
    ("gate 4",            "Score"),
    ("gate_4",            "Score"),
    ("explain",           "Explain"),
    ("remediat",          "Remediate"),
]


def _resolve_step(gate_id, gate_name: str) -> str:
    """Map a gate_id (int or str) + gate_name to a TRACE step name."""
    # 1. Integer gate_id — primary key from the engine
    if isinstance(gate_id, int):
        return _INT_GATE_TO_STEP.get(gate_id, "Score")

    # 2. String that looks like an integer
    if gate_id is not None:
        try:
            return _INT_GATE_TO_STEP.get(int(gate_id), "Score")
        except (ValueError, TypeError):
            pass
        # Legacy string keys like "gate_1"
        key = str(gate_id).lower().strip()
        for pattern, step in _GATE_NAME_PATTERNS:
            if pattern in key:
                return step

    # 3. Fall back to gate_name substring matching
    name_lower = (gate_name or "").lower()
    for pattern, step in _GATE_NAME_PATTERNS:
        if pattern in name_lower:
            return step

    return "Score"  # safe default


def build_trace_timeline(audit_traces: list[dict], executive_mode: bool = False) -> dict:
    """Build a 6-step TRACE timeline from raw audit trace records."""
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
        gate_id = trace.get("gate_id")
        gate_name = trace.get("gate_name") or ""
        step_name = _resolve_step(gate_id, gate_name)

        step = steps[step_name]
        result = trace.get("result") or ""
        step["status"] = "pass" if result in ("pass", "passed", "ok") else (
            "warn" if result in ("warn", "warning") else (
                "fail" if result in ("fail", "failed", "flagged", "error") else "done"
            )
        )
        if gate_id is not None:
            step["rules_fired"].append(str(gate_id))
        if trace.get("check_name"):
            step["rules_fired"].append(trace["check_name"])
        if trace.get("reason"):
            step["detail"] += trace["reason"] + " "
        step["executive_summary"] = _executive_summary(step_name, result)
        if trace.get("confidence") is not None:
            step["confidence"] = trace["confidence"]
        elif step["confidence"] is None:
            step["confidence"] = 0.85

    result_steps = list(steps.values())
    for s in result_steps:
        s["detail"] = s["detail"].strip()
        # Deduplicate rules_fired
        seen: set = set()
        s["rules_fired"] = [r for r in s["rules_fired"] if not (r in seen or seen.add(r))]
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
