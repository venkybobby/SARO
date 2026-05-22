"""
CF-02: Rule Pack Loader test suite
Known-positive and known-negative fixture tests for all 4 framework packs.
CI fails if any fixture assertion fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from rule_packs.loader import (
    RulePackLoadError,
    load_all_packs,
    load_pack,
    validate_pack,
)

PACK_DIR = ROOT / "rule_packs"


# ── Loader unit tests ─────────────────────────────────────────────────────────


def test_load_all_packs_returns_four():
    packs = load_all_packs(PACK_DIR)
    assert len(packs) == 4, f"Expected 4 packs, got {len(packs)}"


def test_all_packs_have_required_fields():
    packs = load_all_packs(PACK_DIR)
    for pack in packs:
        assert pack.name, f"Pack at {pack.path!r} missing name"
        assert pack.version, f"Pack at {pack.path!r} missing version"
        assert pack.rules, f"Pack {pack.name!r} has no rules"
        for rule in pack.rules:
            assert rule.rule_id, f"Rule missing rule_id in {pack.name!r}"
            assert rule.title, f"Rule {rule.rule_id!r} missing title"
            assert rule.domain_trigger, f"Rule {rule.rule_id!r} missing domain_trigger"
            assert rule.obligation, f"Rule {rule.rule_id!r} missing obligation"


def test_malformed_pack_raises_rule_pack_load_error(tmp_path):
    bad_yaml = tmp_path / "rules.yaml"
    bad_yaml.write_text("name: bad-pack\nversion: 1.0.0\nrules:\n  - title: missing_rule_id\n")
    with pytest.raises(RulePackLoadError) as exc_info:
        pack = load_pack(bad_yaml)
        validate_pack(pack)
    assert "rule_id" in str(exc_info.value)


def test_missing_pack_name_raises_error(tmp_path):
    bad_yaml = tmp_path / "rules.yaml"
    bad_yaml.write_text("version: 1.0.0\nrules: []\n")
    with pytest.raises(RulePackLoadError) as exc_info:
        load_pack(bad_yaml)
    assert "name" in str(exc_info.value)


def test_pack_ref_format():
    packs = load_all_packs(PACK_DIR)
    for pack in packs:
        assert "@" in pack.pack_ref
        name, version = pack.pack_ref.split("@")
        assert name == pack.name
        assert version == pack.version


# ── Known-positive / known-negative fixture tests ─────────────────────────────


def _engine_triggers_rule(rule_id: str, text: str) -> bool:
    """Run the SARO engine on a single-sample batch and check if rule_id appears."""
    from unittest.mock import MagicMock

    from engine import SARoEngine
    from schemas import AuditConfigIn, BatchIn, SampleIn

    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []
    mock_db.rollback.return_value = None

    eng = SARoEngine.__new__(SARoEngine)
    eng._mit_risks = []
    eng._incidents = []
    eng._eu_rules = []
    eng._nist_controls = []
    eng._aigp = []
    eng._gov_rules = []
    eng._tfidf_vectorizer = None
    eng._incident_matrix = None
    from rule_packs.loader import build_domain_trigger_map, load_all_packs
    eng._rule_packs = load_all_packs(PACK_DIR)
    eng._compliance_triggers = build_domain_trigger_map(eng._rule_packs)

    sample = SampleIn(sample_id="test_0", text=text)
    cfg = AuditConfigIn.model_construct(
        min_samples=1,
        confidence_threshold=0.95,
        incident_top_k=0,
        frameworks=["EU AI Act", "NIST AI RMF", "AIGP", "ISO 42001"],
    )
    batch = BatchIn.model_construct(
        batch_id=None,
        dataset_name="fixture_test",
        samples=[sample],
        config=cfg,
    )

    # Only need Gate 3 + Gate 4 for rule trigger testing
    flags, _ = eng._gate3_risk_classification(batch)
    eng._applied_rule_packs = {}
    applied_rules, _ = eng._gate4_compliance_mapping(flags)
    triggered_ids = {r.rule_id for r in applied_rules}
    return rule_id in triggered_ids


@pytest.mark.parametrize("pack_name,expected_pack_size", [
    ("eu-ai-act", 5),
    ("nist-ai-rmf", 5),
    ("aigp", 3),
    ("iso-42001", 4),
])
def test_pack_rule_counts(pack_name: str, expected_pack_size: int):
    packs = load_all_packs(PACK_DIR)
    pack = next(p for p in packs if p.name == pack_name)
    assert len(pack.rules) == expected_pack_size, (
        f"{pack_name} expected {expected_pack_size} rules, got {len(pack.rules)}"
    )


def test_all_positive_fixtures_trigger_rules():
    """Every rule with a positive fixture must trigger the engine."""
    packs = load_all_packs(PACK_DIR)
    failures = []
    for pack in packs:
        for rule in pack.rules:
            if not rule.fixture or not rule.fixture.positive_text:
                continue
            triggered = _engine_triggers_rule(rule.rule_id, rule.fixture.positive_text)
            if not triggered:
                failures.append(f"{pack.pack_ref}::{rule.rule_id} — positive fixture did not trigger")
    assert not failures, "Known-positive fixture failures:\n" + "\n".join(failures)


def test_all_negative_fixtures_do_not_trigger_rules():
    """Every rule with a negative fixture must NOT trigger the engine."""
    packs = load_all_packs(PACK_DIR)
    failures = []
    for pack in packs:
        for rule in pack.rules:
            if not rule.fixture or not rule.fixture.negative_text:
                continue
            triggered = _engine_triggers_rule(rule.rule_id, rule.fixture.negative_text)
            if triggered:
                failures.append(f"{pack.pack_ref}::{rule.rule_id} — negative fixture triggered unexpectedly")
    assert not failures, "Known-negative fixture failures:\n" + "\n".join(failures)


def test_audit_trace_includes_rule_pack_version():
    """Gate 4 traces must include rule_pack version metadata in detail_json."""

    from engine import SARoEngine
    from schemas import AuditConfigIn, BatchIn, SampleIn

    eng = SARoEngine.__new__(SARoEngine)
    eng._mit_risks = []
    eng._incidents = []
    eng._eu_rules = []
    eng._nist_controls = []
    eng._aigp = []
    eng._gov_rules = []
    eng._tfidf_vectorizer = None
    eng._incident_matrix = None
    eng._traces = []
    from rule_packs.loader import build_domain_trigger_map, load_all_packs
    eng._rule_packs = load_all_packs(PACK_DIR)
    eng._compliance_triggers = build_domain_trigger_map(eng._rule_packs)

    sample = SampleIn(sample_id="t0", text="patient SSN 123-45-6789 exposed in AI output")
    cfg = AuditConfigIn.model_construct(min_samples=1, confidence_threshold=0.95, incident_top_k=0, frameworks=[])
    batch = BatchIn.model_construct(batch_id=None, dataset_name="test", samples=[sample], config=cfg)

    flags, _ = eng._gate3_risk_classification(batch)
    eng._applied_rule_packs = {}
    applied_rules, gate4 = eng._gate4_compliance_mapping(flags)
    eng._record_gate4_rule_traces(applied_rules, gate4)

    compliance_traces = [t for t in eng._traces if t["check_type"] == "compliance_rule"]
    assert compliance_traces, "No compliance traces recorded"
    for trace in compliance_traces:
        assert "rule_pack" in (trace.get("detail_json") or {}), (
            f"rule_pack missing from detail_json in trace: {trace['check_name']}"
        )
