"""STORY-310 — Risk scoring & disposition tests.

AC coverage:
- Score computed correctly; band assigned from config thresholds (not hard-coded).
- Exactly one disposition per finding (enum-validated).
- CONDITIONAL or FAIL without a remediation is rejected.
- Band boundaries covered (6/7 and 19/20 edges).
"""

from __future__ import annotations

import copy

import pytest

from grc.policy import _DEFAULT_POLICY, load_policy
from grc.scoring import (
    ScoringError,
    band_for,
    compute_score,
    score_risk,
    validate_disposition,
)

pytestmark = pytest.mark.unit


def test_score_is_likelihood_times_impact() -> None:
    assert compute_score(4, 5) == 20
    assert compute_score(1, 1) == 1
    assert compute_score(5, 5) == 25


@pytest.mark.parametrize("bad", [(0, 3), (3, 6), (6, 1), (-1, 2)])
def test_out_of_scale_inputs_rejected(bad) -> None:
    with pytest.raises(ScoringError):
        compute_score(*bad)


@pytest.mark.parametrize(
    "score,band",
    [
        (1, "LOW"),
        (6, "LOW"),
        (7, "MODERATE"),
        (12, "MODERATE"),
        (13, "HIGH"),
        (19, "HIGH"),
        (20, "CRITICAL"),
        (25, "CRITICAL"),
    ],
)
def test_band_boundaries(score, band) -> None:
    assert band_for(score) == band


def test_band_comes_from_config_not_hardcoded() -> None:
    doc = copy.deepcopy(_DEFAULT_POLICY)
    # Move the LOW/MODERATE boundary so 6 becomes MODERATE.
    for b in doc["band_thresholds"]:
        if b["band"] == "LOW":
            b["max"] = 5
        elif b["band"] == "MODERATE":
            b["min"] = 6
    policy = load_policy(doc)
    assert band_for(6, policy) == "MODERATE"


def test_score_risk_full_object() -> None:
    r = score_risk(4, 5)
    assert r.score == 20
    assert r.band == "CRITICAL"
    assert r.likelihood == 4 and r.impact == 5


def test_disposition_must_be_known() -> None:
    with pytest.raises(ScoringError):
        validate_disposition("MAYBE", None)


def test_pass_needs_no_remediation() -> None:
    validate_disposition("PASS", None)  # must not raise


@pytest.mark.parametrize("disp", ["CONDITIONAL", "FAIL"])
def test_conditional_fail_require_remediation(disp) -> None:
    with pytest.raises(ScoringError, match="remediation"):
        validate_disposition(disp, None)
    with pytest.raises(ScoringError):
        validate_disposition(disp, "   ")
    validate_disposition(disp, "Add a grounding citation.")  # ok
