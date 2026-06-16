"""STORY-331 — Configurable policy layer tests.

AC coverage:
- Changing a band threshold in config changes a finding's band (no code change).
- Changing the High-FAIL threshold N changes the gate outcome accordingly.
- Config is versioned; the active version is recorded on results (stamping is
  exercised by the orchestrator tests; here we assert the version is exposed).
- Invalid config (overlapping band ranges / gaps) is rejected at load.
"""

from __future__ import annotations

import copy

import pytest

from grc.policy import (
    GRCPolicy,
    PolicyError,
    _DEFAULT_POLICY,
    get_active_policy,
    load_policy,
    reload_active_policy,
)

pytestmark = pytest.mark.unit


def _policy_doc() -> dict:
    return copy.deepcopy(_DEFAULT_POLICY)


def test_default_policy_loads_and_is_versioned() -> None:
    policy = load_policy()
    assert isinstance(policy, GRCPolicy)
    assert policy.version  # non-empty version string for traceability


def test_band_for_score_uses_default_edges() -> None:
    policy = load_policy()
    assert policy.band_for_score(6) == "LOW"
    assert policy.band_for_score(7) == "MODERATE"
    assert policy.band_for_score(19) == "HIGH"
    assert policy.band_for_score(20) == "CRITICAL"


def test_changing_band_threshold_changes_band_without_code_change() -> None:
    """AC: a config-only edit re-bands a score."""
    base = load_policy()
    assert base.band_for_score(7) == "MODERATE"

    doc = _policy_doc()
    # Widen LOW to swallow 7; shrink MODERATE to start at 8.
    for b in doc["band_thresholds"]:
        if b["band"] == "LOW":
            b["max"] = 7
        elif b["band"] == "MODERATE":
            b["min"] = 8
    edited = load_policy(doc)
    assert edited.band_for_score(7) == "LOW"  # changed by config alone


def test_changing_high_fail_threshold_is_read_from_config() -> None:
    """AC: the gate's High-FAIL N comes from config (consumed by STORY-326)."""
    doc = _policy_doc()
    doc["gate_high_fail_threshold"] = 3
    assert load_policy(doc).gate_high_fail_threshold == 3


def test_overlapping_band_ranges_rejected_at_load() -> None:
    doc = _policy_doc()
    # Make MODERATE overlap LOW.
    for b in doc["band_thresholds"]:
        if b["band"] == "MODERATE":
            b["min"] = 5
    with pytest.raises(PolicyError, match="overlap"):
        load_policy(doc)


def test_gap_in_band_coverage_rejected_at_load() -> None:
    doc = _policy_doc()
    for b in doc["band_thresholds"]:
        if b["band"] == "MODERATE":
            b["min"] = 8  # leaves 7 uncovered
    with pytest.raises(PolicyError, match="gap"):
        load_policy(doc)


def test_band_coverage_must_span_full_domain() -> None:
    doc = _policy_doc()
    doc["band_thresholds"] = [{"band": "LOW", "min": 1, "max": 24}]  # misses 25
    with pytest.raises(PolicyError, match="end at 25"):
        load_policy(doc)


def test_unknown_eu_category_rejected() -> None:
    doc = _policy_doc()
    doc["tiering_default"]["eu_ai_act_category"] = "BOGUS"
    with pytest.raises(PolicyError, match="eu_ai_act_category"):
        load_policy(doc)


def test_non_positive_gate_threshold_rejected() -> None:
    doc = _policy_doc()
    doc["gate_high_fail_threshold"] = 0
    with pytest.raises(PolicyError):
        load_policy(doc)


def test_signoff_roles_lookup() -> None:
    policy = load_policy()
    assert "compliance_lead" in policy.signoff_roles_for_tier("HIGH")
    assert policy.signoff_roles_for_tier("NONEXISTENT") == []


def test_reload_active_policy_picks_up_override(monkeypatch, tmp_path) -> None:
    """AC: changing the source takes effect without redeploying audit logic."""
    import json

    doc = _policy_doc()
    doc["version"] = "grc-policy-test-override"
    doc["gate_high_fail_threshold"] = 5
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    monkeypatch.setenv("SARO_GRC_POLICY_PATH", str(path))
    try:
        reloaded = reload_active_policy()
        assert reloaded.version == "grc-policy-test-override"
        assert reloaded.gate_high_fail_threshold == 5
        assert get_active_policy().gate_high_fail_threshold == 5
    finally:
        monkeypatch.delenv("SARO_GRC_POLICY_PATH", raising=False)
        reload_active_policy()  # restore default for other tests
