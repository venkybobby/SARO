"""STORY-312 — Hard-rule enforcement tests.

AC coverage (one negative test per rule):
- Pipeline rejects a PASS finding whose evidence is not LINKED.
- Each finding exposes facts + assessment that are not conflated.
- A severity reinterpretation that lowers severity sets scope_change_flag rather
  than silently applying.
"""

from __future__ import annotations

import pytest

from grc.hard_rules import (
    HardRuleViolation,
    enforce_hard_rules,
    guard_facts_assessment_separated,
    guard_no_silent_scope_softening,
    guard_no_unevidenced_pass,
    reinterpret_severity,
)

pytestmark = pytest.mark.unit


def _finding(**over) -> dict:
    base = {
        "id": "f1",
        "check": "groundedness",
        "disposition": "PASS",
        "risk": {"likelihood": 1, "impact": 2, "score": 2, "band": "LOW"},
        "evidence": {"status": "LINKED", "evidence_ids": ["ev-1"]},
        "remediation": None,
        "framework_mapping": [],
        "facts": "Claim X overlaps with retrieved context chunk 3.",
        "assessment": "No hallucination detected.",
        "scope_change_flag": False,
    }
    base.update(over)
    return base


# ── Rule 1: no PASS without linked evidence ──
def test_pass_without_linked_evidence_raises() -> None:
    bad = _finding(
        disposition="PASS", evidence={"status": "MISSING", "evidence_ids": []}
    )
    with pytest.raises(HardRuleViolation, match="LINKED"):
        guard_no_unevidenced_pass(bad)


def test_pass_with_linked_evidence_ok() -> None:
    guard_no_unevidenced_pass(_finding())  # must not raise


# ── Rule 2: facts vs assessment separated ──
def test_conflated_facts_and_assessment_raises() -> None:
    same = "The output is fine."
    with pytest.raises(HardRuleViolation, match="conflated"):
        guard_facts_assessment_separated(_finding(facts=same, assessment=same))


def test_missing_facts_or_assessment_raises() -> None:
    with pytest.raises(HardRuleViolation):
        guard_facts_assessment_separated(_finding(facts=""))
    with pytest.raises(HardRuleViolation):
        guard_facts_assessment_separated(_finding(assessment="   "))


# ── Rule 3: no silent scope softening ──
def test_silent_severity_downgrade_raises() -> None:
    bad = _finding(
        risk={"likelihood": 1, "impact": 1, "score": 1, "band": "LOW"},
        original_risk={"likelihood": 4, "impact": 4, "score": 16, "band": "HIGH"},
        scope_change_flag=False,  # downgrade applied silently
    )
    with pytest.raises(HardRuleViolation, match="scope_change_flag"):
        guard_no_silent_scope_softening(bad)


def test_flagged_severity_downgrade_ok() -> None:
    ok = _finding(
        risk={"likelihood": 1, "impact": 1, "score": 1, "band": "LOW"},
        original_risk={"likelihood": 4, "impact": 4, "score": 16, "band": "HIGH"},
        scope_change_flag=True,
    )
    guard_no_silent_scope_softening(ok)  # must not raise


def test_reinterpret_severity_sets_flag_on_downgrade() -> None:
    start = _finding(
        disposition="FAIL",
        risk={"likelihood": 4, "impact": 4, "score": 16, "band": "HIGH"},
    )
    softened = reinterpret_severity(
        start, new_likelihood=1, new_impact=2, reason="context narrowed to test data"
    )
    assert softened["scope_change_flag"] is True
    assert softened["scope_change_reason"]
    assert softened["original_risk"]["score"] == 16
    # And the result now survives the silent-softening guard.
    guard_no_silent_scope_softening(softened)


def test_enforce_hard_rules_over_result() -> None:
    good = {"findings": [_finding(), _finding(id="f2", disposition="PASS")]}
    enforce_hard_rules(good)  # clean → no raise

    bad = {"findings": [_finding(disposition="PASS", evidence={"status": "MISSING"})]}
    with pytest.raises(HardRuleViolation):
        enforce_hard_rules(bad)
