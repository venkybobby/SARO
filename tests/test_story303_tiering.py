"""STORY-303 — Risk tiering engine tests.

AC coverage:
- Classifier returns all three fields for any complete entry.
- Thresholds/rules come from config — no hard-coded tier boundaries.
- A metadata change that alters inputs re-tiers and logs the rationale.
- Sample systems classify to expected tiers (e.g. healthcare triage agent -> HIGH).
"""

from __future__ import annotations

import copy

import pytest

from grc.policy import _DEFAULT_POLICY, load_policy
from grc.tiering import apply_tiering, classify

pytestmark = pytest.mark.unit


class _Entry:
    """Minimal mutable stand-in for an ORM registry row."""

    def __init__(self, **kw):
        self.domain = kw.get("domain")
        self.interacts_with_humans = kw.get("interacts_with_humans")
        self.makes_autonomous_decisions = kw.get("makes_autonomous_decisions")
        self.affects_individuals = kw.get("affects_individuals")
        self.purpose = kw.get("purpose")
        self.deployment_status = kw.get("deployment_status")
        self.internal_tier = None
        self.eu_ai_act_category = None
        self.nist_impact_level = None
        self.tiering_rationale = None
        self.tiered_at = None


def test_classifier_returns_all_three_fields() -> None:
    r = classify({"domain": "marketing"})
    assert r.internal_tier in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert r.eu_ai_act_category
    assert r.nist_impact_level
    assert r.rationale


@pytest.mark.parametrize(
    "profile,expected_tier,expected_eu",
    [
        ({"domain": "healthcare"}, "HIGH", "HIGH"),
        ({"domain": "clinical"}, "HIGH", "HIGH"),
        (
            {"makes_autonomous_decisions": True, "affects_individuals": True},
            "HIGH",
            "HIGH",
        ),
        ({"interacts_with_humans": True}, "MODERATE", "LIMITED"),
        ({"domain": "internal-analytics"}, "LOW", "MINIMAL"),
    ],
)
def test_sample_profiles_classify_as_expected(
    profile, expected_tier, expected_eu
) -> None:
    r = classify(profile)
    assert r.internal_tier == expected_tier
    assert r.eu_ai_act_category == expected_eu


def test_rules_are_config_driven_not_hardcoded() -> None:
    """Editing the config changes the classification — proves no hard-coding."""
    doc = copy.deepcopy(_DEFAULT_POLICY)
    # Flip the healthcare rule to classify as LOW/MINIMAL.
    for rule in doc["tiering_rules"]:
        if rule["when"].get("domain", {}).get("in", [None])[0] == "healthcare":
            rule["internal_tier"] = "LOW"
            rule["eu_ai_act_category"] = "MINIMAL"
            rule["nist_impact_level"] = "LOW"
    policy = load_policy(doc)
    r = classify({"domain": "healthcare"}, policy=policy)
    assert r.internal_tier == "LOW"


def test_apply_tiering_writes_fields_and_timestamp() -> None:
    e = _Entry(domain="healthcare")
    result = apply_tiering(e)
    assert e.internal_tier == "HIGH" == result.internal_tier
    assert e.eu_ai_act_category == "HIGH"
    assert e.tiering_rationale
    assert e.tiered_at is not None


def test_metadata_change_retiers_and_logs_rationale() -> None:
    e = _Entry(domain="internal-analytics")
    apply_tiering(e)
    assert e.internal_tier == "LOW"
    first_rationale = e.tiering_rationale

    # A relevant metadata change must re-tier with a new rationale.
    e.domain = "healthcare"
    apply_tiering(e)
    assert e.internal_tier == "HIGH"
    assert e.tiering_rationale != first_rationale
