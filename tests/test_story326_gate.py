"""STORY-326 — Lifecycle gate engine tests.

AC coverage:
- A single Critical FAIL yields NO_GO regardless of other PASSes.
- Two High FAILs yield NO_GO; one High FAIL yields GO_WITH_CONDITIONS.
- A system with an open governance gap cannot be GO.
- The High-FAIL threshold (N) is read from config (STORY-331), not hard-coded.
"""

from __future__ import annotations

import copy

import pytest

from grc.gate import GO, GO_WITH_CONDITIONS, NO_GO, decide
from grc.policy import _DEFAULT_POLICY, load_policy

pytestmark = pytest.mark.unit


def _f(disposition, band, fid="f") -> dict:
    score = {"LOW": 2, "MODERATE": 9, "HIGH": 16, "CRITICAL": 25}[band]
    return {
        "id": fid,
        "disposition": disposition,
        "risk": {"likelihood": 1, "impact": 1, "score": score, "band": band},
    }


def test_all_pass_is_go() -> None:
    findings = [_f("PASS", "LOW"), _f("PASS", "LOW", "f2")]
    assert decide(findings).recommendation == GO


def test_single_critical_fail_is_no_go() -> None:
    findings = [_f("PASS", "LOW"), _f("FAIL", "CRITICAL", "c")]
    d = decide(findings)
    assert d.recommendation == NO_GO
    assert d.blocking_reasons


def test_one_high_fail_is_go_with_conditions() -> None:
    findings = [_f("FAIL", "HIGH", "h1"), _f("PASS", "LOW")]
    assert decide(findings).recommendation == GO_WITH_CONDITIONS


def test_two_high_fails_is_no_go() -> None:
    findings = [_f("FAIL", "HIGH", "h1"), _f("FAIL", "HIGH", "h2")]
    assert decide(findings).recommendation == NO_GO


def test_open_governance_gap_cannot_be_go() -> None:
    findings = [_f("PASS", "LOW")]
    d = decide(findings, has_open_gaps=True)
    assert d.recommendation == GO_WITH_CONDITIONS  # not GO


def test_conditional_finding_is_go_with_conditions() -> None:
    findings = [_f("CONDITIONAL", "MODERATE", "m")]
    assert decide(findings).recommendation == GO_WITH_CONDITIONS


def test_threshold_is_config_driven() -> None:
    # Raise N to 3 → two High FAILs is no longer NO_GO.
    doc = copy.deepcopy(_DEFAULT_POLICY)
    doc["gate_high_fail_threshold"] = 3
    policy = load_policy(doc)
    findings = [_f("FAIL", "HIGH", "h1"), _f("FAIL", "HIGH", "h2")]
    assert decide(findings, policy=policy).recommendation == GO_WITH_CONDITIONS
    findings3 = findings + [_f("FAIL", "HIGH", "h3")]
    assert decide(findings3, policy=policy).recommendation == NO_GO


def test_critical_beats_everything() -> None:
    findings = [_f("PASS", "LOW")] * 3 + [_f("FAIL", "CRITICAL", "c")]
    assert decide(findings).recommendation == NO_GO
