"""PREREQ-RP — genesis observation rule-packs RP-OBS-COMPLETE + RP-TOOL-SCOPE.

Covers loader validation (a bad pack must refuse to load, never partially load),
evaluator semantics, determinism, and the INV-2/INV-3 properties the packs rely
on: findings carry no message content, and tenant tool policy never mutates
shared pack state.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from adapters.contract import (  # noqa: E402
    FieldAvailability,
    NormalizedInvocationRecord,
    SourceProvenance,
    ToolInvocation,
)
from rule_packs.observation.evaluate import evaluate_record, evaluate_records  # noqa: E402
from rule_packs.observation.loader import (  # noqa: E402
    ObservationPackLoadError,
    load_genesis_packs,
    load_pack,
)

pytestmark = pytest.mark.unit

_TENANT = uuid.uuid4()
_PACK_ROOT = ROOT / "rule_packs" / "observation"
OBS = _PACK_ROOT / "rp_obs_complete" / "1.0.0" / "pack.yaml"
TOOL = _PACK_ROOT / "rp_tool_scope" / "1.0.0" / "pack.yaml"


def _record(**over) -> NormalizedInvocationRecord:
    base: dict = dict(
        provenance=SourceProvenance(adapter_id="test-adapter", cursor="c1"),
        tenant_id=_TENANT,
        request_id="req-1",
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        operation="Converse",
        region="us-east-1",
        timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
        input_token_count=10,
        output_token_count=20,
    )
    base.update(over)
    return NormalizedInvocationRecord(**base)


def _ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


# ── Loader ───────────────────────────────────────────────────────────────────


def test_genesis_packs_load_with_expected_refs():
    packs = load_genesis_packs()
    assert "RP-OBS-COMPLETE@1.0.0" in packs
    assert "RP-TOOL-SCOPE@1.0.0" in packs


def test_pack_hash_is_deterministic_and_version_scoped():
    a, b = load_pack(OBS), load_pack(OBS)
    assert a.content_hash == b.content_hash and len(a.content_hash) == 64
    assert a.content_hash != load_pack(TOOL).content_hash


def test_unknown_check_refuses_to_load(tmp_path):
    """A rule that would never run must fail loudly — silent skip fakes coverage."""
    bad = tmp_path / "pack.yaml"
    bad.write_text(
        "name: X\nversion: '1.0.0'\ntitle: t\ndomain_trigger: d\nobligation: o\n"
        "rules:\n  - rule_id: R1\n    title: t\n    severity: HIGH\n    check: nope\n",
        encoding="utf-8",
    )
    with pytest.raises(ObservationPackLoadError) as exc:
        load_pack(bad)
    assert "unknown check" in str(exc.value)


def test_required_fields_check_without_fields_refuses_to_load(tmp_path):
    bad = tmp_path / "pack.yaml"
    bad.write_text(
        "name: X\nversion: '1.0.0'\ntitle: t\ndomain_trigger: d\nobligation: o\n"
        "rules:\n  - rule_id: R1\n    title: t\n    severity: HIGH\n    check: required_fields\n",
        encoding="utf-8",
    )
    with pytest.raises(ObservationPackLoadError):
        load_pack(bad)


def test_duplicate_rule_ids_refuse_to_load(tmp_path):
    bad = tmp_path / "pack.yaml"
    bad.write_text(
        "name: X\nversion: '1.0.0'\ntitle: t\ndomain_trigger: d\nobligation: o\n"
        "rules:\n"
        "  - rule_id: R1\n    title: t\n    severity: HIGH\n    check: error_present\n"
        "  - rule_id: R1\n    title: t2\n    severity: LOW\n    check: error_present\n",
        encoding="utf-8",
    )
    with pytest.raises(ObservationPackLoadError):
        load_pack(bad)


# ── RP-OBS-COMPLETE ──────────────────────────────────────────────────────────


def test_complete_record_produces_no_findings():
    assert evaluate_record(_record(), load_pack(OBS)) == []


def test_absent_token_counts_fire_the_token_rule():
    rec = _record(input_token_count=None, output_token_count=None)
    findings = evaluate_record(rec, load_pack(OBS))
    token_finding = [f for f in findings if f.rule_id == "OBS-TOKEN-COUNTS-1"][0]
    assert set(token_finding.detail["absent_fields"]) == {
        "input_token_count",
        "output_token_count",
    }


def test_required_identity_field_absence_fires_high():
    """`region` is optional; the identity rule guards the un-defaultable fields.

    A record cannot be constructed without request_id/model_id/timestamp (the
    contract requires them), which is itself the first line of defence — this
    asserts the rule is wired to those fields so a future optional-ising of any
    of them cannot pass unnoticed."""
    pack = load_pack(OBS)
    identity_rule = [r for r in pack.rules if r.rule_id == "OBS-REQUIRED-FIELDS-1"][0]
    assert set(identity_rule.required_fields) == {
        "request_id",
        "model_id",
        "timestamp",
        "operation",
    }
    assert identity_rule.severity == "HIGH"


def test_structurally_unavailable_fields_are_graded_lower_than_missing():
    """A provider that cannot emit token counts is a coverage limit, not a defect."""
    pack = load_pack(OBS)
    unavailable = _record(
        input_token_count=None,
        output_token_count=None,
        field_availability=NormalizedInvocationRecord.mark_unavailable(
            "input_token_count", "output_token_count"
        ),
    )
    missing = _record(
        input_token_count=None,
        output_token_count=None,
        field_availability=NormalizedInvocationRecord.mark_missing(
            "input_token_count", "output_token_count"
        ),
    )
    sev_unavailable = [f for f in evaluate_record(unavailable, pack) if f.rule_id == "OBS-TOKEN-COUNTS-1"][0]
    sev_missing = [f for f in evaluate_record(missing, pack) if f.rule_id == "OBS-TOKEN-COUNTS-1"][0]
    assert sev_unavailable.severity == "INFO"
    assert sev_missing.severity == "LOW"


def test_mixed_absence_keeps_full_severity():
    """One structural gap must not mask a real data-quality gap beside it."""
    pack = load_pack(OBS)
    rec = _record(
        input_token_count=None,
        output_token_count=None,
        field_availability={
            "input_token_count": FieldAvailability.UNAVAILABLE,
            "output_token_count": FieldAvailability.MISSING,
        },
    )
    f = [x for x in evaluate_record(rec, pack) if x.rule_id == "OBS-TOKEN-COUNTS-1"][0]
    assert f.severity == "LOW", "downgrade applied despite a genuine missing field"


def test_truncated_output_flags_incomplete_observation():
    findings = evaluate_record(_record(truncated=True, stop_reason="max_tokens"), load_pack(OBS))
    assert "OBS-TRUNCATED-OUTPUT-1" in _ids(findings)


def test_error_code_flags_failed_invocation():
    findings = evaluate_record(_record(error_code="ThrottlingException"), load_pack(OBS))
    assert "OBS-ERROR-INVOCATION-1" in _ids(findings)


# ── RP-TOOL-SCOPE ────────────────────────────────────────────────────────────


def test_invoked_tool_outside_scope_fires_high():
    pack = load_pack(TOOL).with_allowed_tools(["search_kb"])
    rec = _record(tools=(ToolInvocation(name="delete_patient", offered=True, invoked=True),))
    findings = evaluate_record(rec, pack)
    violation = [f for f in findings if f.rule_id == "TOOL-SCOPE-VIOLATION-1"][0]
    assert violation.severity == "HIGH"
    assert violation.detail["invoked_out_of_scope"] == ["delete_patient"]


def test_in_scope_tool_use_is_clean():
    pack = load_pack(TOOL).with_allowed_tools(["search_kb"])
    rec = _record(tools=(ToolInvocation(name="search_kb", offered=True, invoked=True),))
    assert evaluate_record(rec, pack) == []


def test_offered_but_not_invoked_out_of_scope_tool_fires_medium():
    pack = load_pack(TOOL).with_allowed_tools(["search_kb"])
    rec = _record(tools=(ToolInvocation(name="wire_transfer", offered=True, invoked=False),))
    f = [x for x in evaluate_record(rec, pack) if x.rule_id == "TOOL-SCOPE-OFFERED-1"][0]
    assert f.severity == "MEDIUM"


def test_invoked_violation_is_not_double_counted_as_offered():
    """Same tool must not fire both rules — it would double-count in the matrix."""
    pack = load_pack(TOOL).with_allowed_tools(["search_kb"])
    rec = _record(tools=(ToolInvocation(name="wire_transfer", offered=True, invoked=True),))
    ids = _ids(evaluate_record(rec, pack))
    assert "TOOL-SCOPE-VIOLATION-1" in ids
    assert "TOOL-SCOPE-OFFERED-1" not in ids


def test_absent_tool_policy_is_visible_not_silent_pass():
    pack = load_pack(TOOL)  # no allowed_tools declared
    rec = _record(tools=(ToolInvocation(name="anything", offered=True, invoked=True),))
    ids = _ids(evaluate_record(rec, pack))
    assert ids == {"TOOL-POLICY-ABSENT-1"}, "unconfigured policy must not pass silently"


def test_no_tools_and_no_policy_is_not_a_finding():
    assert evaluate_record(_record(), load_pack(TOOL)) == []


def test_tenant_policy_does_not_mutate_shared_pack_inv3():
    base = load_pack(TOOL)
    bound = base.with_allowed_tools(["only_mine"])
    assert base.allowed_tools == ()
    assert bound.allowed_tools == ("only_mine",)
    assert bound.content_hash == base.content_hash, "tenant input must not change the pack hash"


# ── Cross-cutting ────────────────────────────────────────────────────────────


def test_evaluation_is_deterministic():
    packs = list(load_genesis_packs().values())
    rec = _record(truncated=True, error_code="X", tools=(ToolInvocation(name="t", invoked=True),))
    first = [f.to_evidence() for f in evaluate_records([rec], packs)]
    second = [f.to_evidence() for f in evaluate_records([rec], packs)]
    assert first == second


def test_findings_carry_pack_ref_and_hash_for_attestation():
    pack = load_pack(OBS)
    f = evaluate_record(_record(truncated=True), pack)[0]
    assert f.pack_ref == "RP-OBS-COMPLETE@1.0.0"
    assert f.pack_hash == pack.content_hash


def test_findings_contain_no_message_content_inv2():
    """Detail may carry field names, tool names, codes — never body text."""
    packs = list(load_genesis_packs().values())
    rec = _record(
        truncated=True,
        error_code="ThrottlingException",
        input_token_count=None,
        output_token_count=None,
        tools=(ToolInvocation(name="search_kb", offered=True, invoked=True),),
    )
    for f in evaluate_records([rec], packs):
        blob = str(f.to_evidence()).lower()
        for banned in ("prompt", "completion", "raw_output", "message_text"):
            assert banned not in blob, f"finding leaked {banned!r}: {f.detail}"
