"""STORY-312 — Hard-rule enforcement.

The auditor's hard rules are enforced in the pipeline so convenient-but-false
conclusions are structurally impossible, not merely discouraged. These are
pipeline guards that run before a result is finalized; a guard failure **raises**
— it never warns-and-continues.

Rules:
1. No PASS without linked evidence (service-side complement to the contract rule).
2. Fact vs. inference separated — each finding records evidence-derived ``facts``
   distinctly from the auditor's ``assessment`` (the two must not be conflated).
3. No silent scope softening — a reinterpretation that lowers a finding's
   severity must set an explicit ``scope_change_flag``; it is never applied quietly.
"""

from __future__ import annotations

from typing import Any

from grc.scoring import PASS, RiskScore, band_for


class HardRuleViolation(ValueError):
    """Raised when a finding violates one of the auditor's hard rules."""


def guard_no_unevidenced_pass(finding: dict[str, Any]) -> None:
    """Rule 1: a PASS finding must have LINKED evidence."""
    if finding.get("disposition") == PASS:
        evidence = finding.get("evidence") or {}
        if evidence.get("status") != "LINKED":
            raise HardRuleViolation(
                f"finding {finding.get('id')!r}: PASS requires LINKED evidence, "
                f"got {evidence.get('status')!r}"
            )


def guard_facts_assessment_separated(finding: dict[str, Any]) -> None:
    """Rule 2: ``facts`` and ``assessment`` must both exist and be distinct."""
    facts = (finding.get("facts") or "").strip()
    assessment = (finding.get("assessment") or "").strip()
    if not facts or not assessment:
        raise HardRuleViolation(
            f"finding {finding.get('id')!r}: facts and assessment must both be present"
        )
    if facts == assessment:
        raise HardRuleViolation(
            f"finding {finding.get('id')!r}: facts and assessment are conflated"
        )


def guard_no_silent_scope_softening(finding: dict[str, Any]) -> None:
    """Rule 3: a severity downgrade must carry an explicit ``scope_change_flag``.

    A finding that records an ``original_risk`` with a higher score than its
    current risk, without ``scope_change_flag`` set, is a silent softening.
    """
    original = finding.get("original_risk")
    if not original:
        return
    current_score = (finding.get("risk") or {}).get("score")
    if current_score is None:
        return
    if original.get("score", 0) > current_score and not finding.get(
        "scope_change_flag"
    ):
        raise HardRuleViolation(
            f"finding {finding.get('id')!r}: severity lowered from "
            f"{original.get('score')} to {current_score} without scope_change_flag"
        )


_GUARDS = (
    guard_no_unevidenced_pass,
    guard_facts_assessment_separated,
    guard_no_silent_scope_softening,
)


def enforce_hard_rules(result: dict[str, Any]) -> dict[str, Any]:
    """Run every hard-rule guard over every finding; raise on the first violation."""
    for finding in result.get("findings", []):
        for guard in _GUARDS:
            guard(finding)
    return result


def reinterpret_severity(
    finding: dict[str, Any],
    *,
    new_likelihood: int,
    new_impact: int,
    reason: str,
    policy=None,
) -> dict[str, Any]:
    """Safely re-score a finding, flagging the change when it lowers severity.

    This is the *only* sanctioned way to downgrade a finding: it preserves the
    original risk and sets ``scope_change_flag`` + ``scope_change_reason`` so the
    reinterpretation is explicit, satisfying rule 3.
    """
    new_score = new_likelihood * new_impact
    new_risk = RiskScore(
        likelihood=new_likelihood,
        impact=new_impact,
        score=new_score,
        band=band_for(new_score, policy),
    )
    updated = dict(finding)
    original = finding.get("risk") or {}
    if original.get("score", new_score) > new_score:
        updated["original_risk"] = original
        updated["scope_change_flag"] = True
        updated["scope_change_reason"] = reason
    updated["risk"] = new_risk.model_dump()
    return updated
