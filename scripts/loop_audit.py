#!/usr/bin/env python3
"""Loop readiness audit for SARO.

Loop-engineering's design checklist warns against running L3 before L1 quality
(anti-pattern #4): a loop should only sit at a maturity its evidence supports. This
scores each loop in loops/registry.yaml against the checklist dimensions, derives
the highest maturity its evidence JUSTIFIES, and flags any loop whose DECLARED
maturity exceeds it ("over-provisioned").

Evidence is read from the registry, loops/limits.yaml (cost/kill-switch coverage),
and the workflow files (observability = does the loop record a run?). No network.

Usage:
    python scripts/loop_audit.py            # print the readiness report (exit 0)
    python scripts/loop_audit.py --json     # machine-readable
    python scripts/loop_audit.py --strict   # exit 1 if any loop is over-provisioned
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "loops" / "registry.yaml"
LIMITS = ROOT / "loops" / "limits.yaml"
WORKFLOWS = ROOT / ".github" / "workflows"

RANK = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}
WORKFLOW_TRIGGERS = {"schedule", "pull_request", "push", "event"}

# Phrases that evidence an independent maker/checker separation.
_REVIEW_MARKERS = ("reviewer", "security-auditor", "independent", "human review",
                   "human merge", "human merges", "pr review", "gate")


def _has_review(loop: dict) -> bool:
    text = f"{loop.get('verification', '')} {loop.get('escalation', '')}".lower()
    return any(m in text for m in _REVIEW_MARKERS)


def audit_loop(loop: dict, limits_loops: dict, runlog_wired: set[str]) -> dict:
    """Score one loop's checklist dimensions and the maturity it qualifies for."""
    is_workflow = loop.get("trigger") in WORKFLOW_TRIGGERS
    dims: dict[str, bool | None] = {
        "purpose": bool(loop.get("description")) and bool(loop.get("category")),
        "scheduling": bool(loop.get("cadence")) and bool(loop.get("trigger")),
        "implementation": bool(loop.get("implementation")),
        "human_handoff": bool(loop.get("escalation")),
        "verification": bool(loop.get("verification")),
        "maker_checker": _has_review(loop),
    }
    if is_workflow:
        cfg = limits_loops.get(loop["id"])
        dims["cost_limits"] = cfg is not None and cfg.get("daily_run_cap") is not None
        dims["observability"] = loop["id"] in runlog_wired
    else:
        # Non-workflow loops (guard skills, manual) have no schedule/limits/CI run.
        dims["cost_limits"] = None
        dims["observability"] = None

    qualified = _qualified_level(dims)
    declared = loop.get("maturity", "L1")
    over = RANK.get(declared, 0) > RANK.get(qualified, 0)
    gaps = [d for d, v in dims.items() if v is False]
    # Score: satisfied / applicable dimensions.
    applicable = [v for v in dims.values() if v is not None]
    score = round(sum(1 for v in applicable if v) / len(applicable), 2) if applicable else 0.0
    return {
        "id": loop["id"],
        "declared": declared,
        "max_maturity": loop.get("max_maturity"),
        "qualified": qualified,
        "over_provisioned": over,
        "score": score,
        "dimensions": dims,
        "gaps": gaps,
    }


def _ok(value: bool | None) -> bool:
    """True dimensions and not-applicable (None) dimensions both 'pass'."""
    return value is True or value is None


def _qualified_level(dims: dict[str, bool | None]) -> str:
    """Highest maturity the evidence supports.

    L1 needs the basics (purpose, scheduling, implementation, human handoff).
    L2 adds verification and a cost/kill-switch limit.
    L3 adds an independent maker/checker and observability.
    """
    base = all(dims[d] for d in ("purpose", "scheduling", "implementation", "human_handoff"))
    if not base:
        return "L0"
    if not (dims["verification"] and _ok(dims["cost_limits"])):
        return "L1"
    if not (dims["maker_checker"] and _ok(dims["observability"])):
        return "L2"
    return "L3"


def runlog_wired_ids(limits_loops: dict, workflows_dir: Path = WORKFLOWS) -> set[str]:
    """Loop ids whose workflow file records runs via loop_runlog.py."""
    wired: set[str] = set()
    for loop_id, cfg in (limits_loops or {}).items():
        wf = cfg.get("workflow")
        if not wf:
            continue
        path = workflows_dir / wf
        if path.exists() and "loop_runlog.py" in path.read_text():
            wired.add(loop_id)
    return wired


def run_audit(registry: dict, limits: dict, workflows_dir: Path = WORKFLOWS) -> list[dict]:
    limits_loops = limits.get("loops") or {}
    wired = runlog_wired_ids(limits_loops, workflows_dir)
    return [audit_loop(loop, limits_loops, wired) for loop in registry["loops"]]


def _format_report(results: list[dict]) -> str:
    lines = ["Loop readiness audit", "=" * 60]
    for r in results:
        flag = "  ⚠ OVER-PROVISIONED" if r["over_provisioned"] else ""
        lines.append(
            f"{r['id']:<22} declared={r['declared']} "
            f"qualified={r['qualified']} score={r['score']:.2f}{flag}"
        )
        if r["gaps"]:
            lines.append(f"{'':<22} gaps: {', '.join(r['gaps'])}")
    over = [r["id"] for r in results if r["over_provisioned"]]
    lines.append("=" * 60)
    lines.append(f"{len(results)} loops · {len(over)} over-provisioned"
                 + (f": {', '.join(over)}" if over else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit loop readiness vs declared maturity.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 if any loop is over-provisioned.")
    args = parser.parse_args(argv)

    registry = yaml.safe_load(REGISTRY.read_text())
    limits = yaml.safe_load(LIMITS.read_text())
    results = run_audit(registry, limits)

    if args.json:
        print(json.dumps({"loops": results}, indent=2))
    else:
        print(_format_report(results))

    over = [r for r in results if r["over_provisioned"]]
    if args.strict and over:
        print(f"\nstrict: {len(over)} loop(s) declared above their audited readiness.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
