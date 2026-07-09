"""STORY-411 — envelope allowlist rule-pack loader.

Covers:
  AC-2.1  rule pack schema gains envelope_allowlist rule type: exact + optional
          prefix entries (exact-then-prefix, no regex)
  AC-2.2  loaded rule carries rule_id + version, so a finding can attribute both
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rule_packs.envelope_loader import (
    EnvelopeAllowlistLoadError,
    EnvelopeAllowlistRule,
    envelope_pack_hash,
    is_model_allowed,
    load_envelope_allowlist,
)

_REPO = Path(__file__).resolve().parents[1]
_PACK_PATH = _REPO / "rule_packs" / "envelope" / "1.0.0" / "envelope_allowlist.yaml"


@pytest.mark.unit
def test_loads_the_checked_in_demo_pack():
    rule = load_envelope_allowlist(_PACK_PATH)
    assert rule.rule_id == "ENV-MODEL-ALLOWLIST-1"
    assert rule.version == "1.0.0"
    assert rule.domain_trigger == "Governance & Compliance"
    assert "anthropic.claude-3-5-sonnet-20240620-v1:0" in rule.allowed_model_ids


@pytest.mark.unit
def test_exact_match_allowed():
    rule = EnvelopeAllowlistRule(
        rule_id="R1",
        title="t",
        domain_trigger="Governance & Compliance",
        obligation="o",
        version="1.0.0",
        allowed_model_ids=["anthropic.claude-3-5-sonnet-20240620-v1:0"],
        allowed_model_id_prefixes=[],
    )
    assert is_model_allowed(rule, "anthropic.claude-3-5-sonnet-20240620-v1:0") is True


@pytest.mark.unit
def test_off_allowlist_model_is_not_allowed():
    rule = EnvelopeAllowlistRule(
        rule_id="R1",
        title="t",
        domain_trigger="Governance & Compliance",
        obligation="o",
        version="1.0.0",
        allowed_model_ids=["anthropic.claude-3-5-sonnet-20240620-v1:0"],
        allowed_model_id_prefixes=[],
    )
    assert is_model_allowed(rule, "anthropic.claude-instant-v1") is False


@pytest.mark.unit
def test_prefix_match_checked_only_when_no_exact_match():
    rule = EnvelopeAllowlistRule(
        rule_id="R1",
        title="t",
        domain_trigger="Governance & Compliance",
        obligation="o",
        version="1.0.0",
        allowed_model_ids=[],
        allowed_model_id_prefixes=["anthropic.claude-3-"],
    )
    assert is_model_allowed(rule, "anthropic.claude-3-opus-20240229-v1:0") is True
    assert is_model_allowed(rule, "anthropic.claude-instant-v1") is False


@pytest.mark.unit
def test_empty_or_none_model_id_is_not_allowed():
    rule = EnvelopeAllowlistRule(
        rule_id="R1",
        title="t",
        domain_trigger="Governance & Compliance",
        obligation="o",
        version="1.0.0",
        allowed_model_ids=["anthropic.claude-3-5-sonnet-20240620-v1:0"],
        allowed_model_id_prefixes=[],
    )
    assert is_model_allowed(rule, "") is False
    assert is_model_allowed(rule, None) is False


@pytest.mark.unit
def test_malformed_pack_raises_load_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.dump({"name": "x", "version": "1.0.0"}), encoding="utf-8")
    with pytest.raises(EnvelopeAllowlistLoadError):
        load_envelope_allowlist(bad)


@pytest.mark.unit
def test_hash_is_deterministic_and_changes_with_content():
    rule_a = load_envelope_allowlist(_PACK_PATH)
    rule_b = load_envelope_allowlist(_PACK_PATH)
    assert envelope_pack_hash(rule_a) == envelope_pack_hash(rule_b)

    mutated = EnvelopeAllowlistRule(
        rule_id=rule_a.rule_id,
        title=rule_a.title,
        domain_trigger=rule_a.domain_trigger,
        obligation=rule_a.obligation,
        version=rule_a.version,
        allowed_model_ids=[*rule_a.allowed_model_ids, "extra-model"],
        allowed_model_id_prefixes=rule_a.allowed_model_id_prefixes,
    )
    assert envelope_pack_hash(mutated) != envelope_pack_hash(rule_a)
