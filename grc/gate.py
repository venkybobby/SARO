"""STORY-326 — Lifecycle gate engine.

Aggregates a system's findings into a single ``gate_recommendation`` and enforces
the non-negotiable blocking rules (OPEN-DEC-1):

* any **Critical FAIL** → ``NO_GO`` (also enforced by the contract, STORY-328);
* **≥ N High FAILs** → ``NO_GO``; exactly **1** High FAIL → ``GO_WITH_CONDITIONS``;
* any **open governance gap** (STORY-302) → cannot be ``GO``.

``N`` (the High-FAIL threshold) is read from config (STORY-331), never hard-coded.
This is the authority the orchestrator delegates to; if it ever disagreed with
the contract's Critical-FAIL⇒NO_GO rule, that would be a defect — the contract is
the single source of truth.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from grc.policy import GRCPolicy, get_active_policy
from grc.scoring import FAIL

GO = "GO"
GO_WITH_CONDITIONS = "GO_WITH_CONDITIONS"
NO_GO = "NO_GO"

# Dispositions that prevent an unconditional GO.
_NON_CLEAN = ("FAIL", "CONDITIONAL", "EVIDENCE_GAP")


class GateDecision(BaseModel):
    recommendation: str
    rationale: str
    blocking_reasons: list[str] = []


def decide(
    findings: list[dict[str, Any]],
    *,
    has_open_gaps: bool = False,
    policy: GRCPolicy | None = None,
) -> GateDecision:
    """Aggregate findings into a gate recommendation."""
    pol = policy or get_active_policy()
    n = pol.gate_high_fail_threshold

    fails = [f for f in findings if f.get("disposition") == FAIL]
    critical_fails = [
        f for f in fails if (f.get("risk") or {}).get("band") == "CRITICAL"
    ]
    high_fails = [f for f in fails if (f.get("risk") or {}).get("band") == "HIGH"]

    blocking: list[str] = []
    if critical_fails:
        blocking.append(f"{len(critical_fails)} Critical FAIL(s)")
    if len(high_fails) >= n:
        blocking.append(f"{len(high_fails)} High FAIL(s) ≥ threshold N={n}")

    if blocking:
        return GateDecision(
            recommendation=NO_GO,
            rationale="Blocking conditions present: " + "; ".join(blocking),
            blocking_reasons=blocking,
        )

    # Not blocked outright. Any remaining non-clean finding (incl. a sub-threshold
    # High FAIL) or an open governance gap means GO_WITH_CONDITIONS, never GO.
    conditions: list[str] = []
    if has_open_gaps:
        conditions.append("open governance gap(s) — cannot GO")
    non_clean = [f for f in findings if f.get("disposition") in _NON_CLEAN]
    if non_clean:
        conditions.append(f"{len(non_clean)} finding(s) require conditions/remediation")

    if conditions:
        return GateDecision(
            recommendation=GO_WITH_CONDITIONS,
            rationale="Proceed with conditions: " + "; ".join(conditions),
        )

    return GateDecision(
        recommendation=GO,
        rationale="No blocking findings and no open governance gaps.",
    )
