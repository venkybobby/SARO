"""STORY-359 — Azure OpenAI observation adapter.

The tests that matter most here are the ones about ABSENCE. Azure's diagnostic
schema carries less than Bedrock's invocation logs, and the failure mode this
adapter must not have is letting "we observed nothing" read as "nothing was
wrong". So: unavailable-vs-missing is pinned, and RP-TOOL-SCOPE's silence on
standard Azure records is asserted to be a coverage gap rather than a clean bill.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from adapters.azure_openai.parse import parse_record  # noqa: E402
from adapters.azure_openai.records import (  # noqa: E402
    AZURE_OPENAI_ADAPTER_ID,
    AzureAdapterConfig,
    AzureCategorySkipped,
    AzureRecordError,
)
from adapters.azure_openai.source import OutOfScopeKey, for_tenant  # noqa: E402
from adapters.contract import FieldAvailability, NormalizedInvocationRecord  # noqa: E402
from rule_packs.observation.evaluate import evaluate_record, evaluate_records  # noqa: E402
from rule_packs.observation.loader import load_pack  # noqa: E402

pytestmark = pytest.mark.unit

_TENANT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_TENANT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
_CONFIG = AzureAdapterConfig(tenant_id=_TENANT_A, container="logs", prefix="tenant-a")

_PACK_ROOT = ROOT / "rule_packs" / "observation"
OBS_PACK = _PACK_ROOT / "rp_obs_complete" / "1.0.0" / "pack.yaml"
TOOL_PACK = _PACK_ROOT / "rp_tool_scope" / "1.0.0" / "pack.yaml"
CORPUS = ROOT / "tests" / "fixtures" / "azure" / "corpus.ndjson"


def _raw(**over):
    base = {
        "time": "2026-07-01T09:15:30.1234567Z",
        "resourceId": "/SUBSCRIPTIONS/X/RESOURCEGROUPS/RG/PROVIDERS/MICROSOFT.COGNITIVESERVICES/ACCOUNTS/A",
        "category": "RequestResponse",
        "operationName": "ChatCompletions_Create",
        "durationMs": 812,
        "resultSignature": "200",
        "resultType": "Success",
        "correlationId": "corr-1",
        "location": "eastus",
        "properties": {
            "modelDeploymentName": "prod-chat",
            "modelName": "gpt-4o",
            "modelVersion": "2024-05-13",
            "promptTokens": 120,
            "completionTokens": 45,
        },
    }
    props = over.pop("properties", None)
    base.update(over)
    if props is not None:
        base["properties"] = props
    return base


def _parse(raw=None, config=_CONFIG, cursor="obj:L1"):
    return parse_record(raw or _raw(), config=config, cursor=cursor)


def _corpus_records(tenant=_TENANT_A):
    cfg = AzureAdapterConfig(tenant_id=tenant, container="logs", prefix="")
    out = []
    for i, line in enumerate(CORPUS.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            out.append(parse_record(line, config=cfg, cursor=f"corpus:L{i}"))
        except AzureRecordError:
            continue
    return out


# ── AC-1: parsing into the normalized contract ──────────────────────────────


def test_parses_azure_record_into_normalized_contract():
    rec = _parse()
    assert isinstance(rec, NormalizedInvocationRecord)
    assert rec.request_id == "corr-1"
    assert rec.operation == "ChatCompletions_Create"
    assert rec.region == "eastus"
    assert rec.input_token_count == 120
    assert rec.output_token_count == 45
    assert rec.provenance.adapter_id == AZURE_OPENAI_ADAPTER_ID


def test_azure_seven_digit_fractional_timestamp_parses():
    """Azure emits 7 fractional digits; Python's isoformat accepts at most 6."""
    rec = _parse()
    assert rec.timestamp.year == 2026 and rec.timestamp.tzinfo is not None
    assert rec.timestamp.hour == 9 and rec.timestamp.minute == 15


def test_model_identity_prefers_model_name_over_deployment_alias():
    """A deployment alias says nothing about which model served the traffic."""
    assert _parse().model_id == "gpt-4o:2024-05-13"


def test_falls_back_to_deployment_name_when_model_name_absent():
    raw = _raw(properties={"modelDeploymentName": "prod-chat"})
    assert _parse(raw).model_id == "prod-chat"


def test_record_hash_is_stable_and_content_free():
    a, b = _parse(), _parse()
    assert a.provenance.record_hash == b.provenance.record_hash
    assert len(a.provenance.record_hash) == 64


def test_error_result_populates_error_code():
    raw = _raw(resultSignature="429", resultType="Failure")
    assert _parse(raw).error_code == "429"


def test_non_2xx_signature_is_an_error_even_when_result_type_says_success():
    raw = _raw(resultSignature="404", resultType="Success")
    assert _parse(raw).error_code == "404"


# ── AC-3: graceful degradation, explicitly classified ───────────────────────


def test_absent_usage_is_unavailable_not_missing():
    """No usage fields at all = Azure schema gap, not a data-quality problem."""
    raw = _raw(properties={"modelName": "gpt-4o"})
    rec = _parse(raw)
    assert rec.input_token_count is None
    assert rec.availability("input_token_count") is FieldAvailability.UNAVAILABLE


def test_partial_usage_is_missing_not_unavailable():
    """If Azure reported one usage field, the other's absence is data quality."""
    raw = _raw(properties={"modelName": "gpt-4o", "promptTokens": 10})
    rec = _parse(raw)
    assert rec.availability("output_token_count") is FieldAvailability.MISSING


def test_stop_reason_and_truncation_are_structurally_unavailable():
    """truncated=False must mean 'not observed', never 'confirmed not truncated'."""
    rec = _parse()
    assert rec.availability("stop_reason") is FieldAvailability.UNAVAILABLE
    assert rec.availability("truncated") is FieldAvailability.UNAVAILABLE
    assert rec.truncated is False


def test_missing_model_identity_is_marked_missing():
    raw = _raw(properties={"promptTokens": 1, "completionTokens": 1})
    rec = _parse(raw)
    assert rec.availability("model_id") is FieldAvailability.MISSING


def test_missing_region_is_marked_missing():
    raw = _raw()
    raw.pop("location")
    assert _parse(raw).availability("region") is FieldAvailability.MISSING


def test_no_field_is_ever_silently_none():
    """Every absent normalized field must carry an availability explanation."""
    raw = _raw(properties={})
    raw.pop("location")
    rec = _parse(raw)
    for field in ("input_token_count", "output_token_count", "region", "model_id"):
        if getattr(rec, field, None) in (None, ""):
            assert rec.availability(field) is not FieldAvailability.PRESENT, (
                f"{field} is absent but reports PRESENT — silent null"
            )


# ── Malformed / wrong-category handling ─────────────────────────────────────


def test_malformed_record_is_rejected_not_half_populated():
    raw = _raw()
    raw.pop("correlationId")
    with pytest.raises(AzureRecordError):
        _parse(raw)


def test_invalid_json_string_is_rejected():
    with pytest.raises(AzureRecordError):
        parse_record("{not json", config=_CONFIG, cursor="c")


def test_other_diagnostic_category_is_skipped_not_misparsed():
    raw = _raw(category="Audit")
    with pytest.raises(AzureCategorySkipped):
        _parse(raw)


# ── AC-6 / INV-3: tenancy comes from config, never from the log ─────────────


def test_record_claiming_another_tenant_cannot_override_binding():
    """The hostile case: Azure records legitimately contain tenant-shaped GUIDs."""
    raw = _raw()
    raw["properties"]["tenantId"] = str(_TENANT_B)
    raw["tenantId"] = str(_TENANT_B)
    raw["resourceId"] = f"/SUBSCRIPTIONS/{_TENANT_B}/RESOURCEGROUPS/EVIL/..."
    rec = _parse(raw)
    assert rec.tenant_id == _TENANT_A, "log content must never set SARO tenancy"


def test_reader_refuses_keys_outside_tenant_prefix(tmp_path):
    (tmp_path / "logs" / "tenant-a").mkdir(parents=True)
    (tmp_path / "logs" / "tenant-b").mkdir(parents=True)
    (tmp_path / "logs" / "tenant-b" / "x.json").write_text(json.dumps(_raw()), encoding="utf-8")

    reader = for_tenant(_TENANT_A, "logs", prefix="tenant-a", root=tmp_path)
    with pytest.raises(OutOfScopeKey):
        reader.read_object("tenant-b/x.json")


def test_reader_rejects_path_traversal(tmp_path):
    (tmp_path / "logs" / "tenant-a").mkdir(parents=True)
    reader = for_tenant(_TENANT_A, "logs", prefix="tenant-a", root=tmp_path)
    with pytest.raises(OutOfScopeKey):
        reader.read_object("tenant-a/../tenant-b/x.json")


def test_prefix_confusion_does_not_leak_across_tenants(tmp_path):
    """`tenant-1` must not read `tenant-10` — plain startswith would allow it."""
    (tmp_path / "logs" / "tenant-1").mkdir(parents=True)
    (tmp_path / "logs" / "tenant-10").mkdir(parents=True)
    (tmp_path / "logs" / "tenant-10" / "x.json").write_text(json.dumps(_raw()), encoding="utf-8")

    reader = for_tenant(_TENANT_A, "logs", prefix="tenant-1", root=tmp_path)
    assert reader.list_objects() == []
    with pytest.raises(OutOfScopeKey):
        reader.read_object("tenant-10/x.json")


def test_two_tenants_read_only_their_own_export(tmp_path):
    for name, corr in (("tenant-a", "a-1"), ("tenant-b", "b-1")):
        d = tmp_path / "logs" / name
        d.mkdir(parents=True)
        (d / "log.json").write_text(json.dumps(_raw(correlationId=corr)), encoding="utf-8")

    a = for_tenant(_TENANT_A, "logs", prefix="tenant-a", root=tmp_path).read_all()
    b = for_tenant(_TENANT_B, "logs", prefix="tenant-b", root=tmp_path).read_all()

    assert [r.request_id for r in a] == ["a-1"]
    assert [r.request_id for r in b] == ["b-1"]
    assert {r.tenant_id for r in a} == {_TENANT_A}
    assert {r.tenant_id for r in b} == {_TENANT_B}


# ── Reader formats ──────────────────────────────────────────────────────────


def test_reader_handles_ndjson_array_and_records_wrapper(tmp_path):
    d = tmp_path / "logs" / "t"
    d.mkdir(parents=True)
    (d / "a.ndjson").write_text(
        json.dumps(_raw(correlationId="n1")) + "\n" + json.dumps(_raw(correlationId="n2")),
        encoding="utf-8",
    )
    (d / "b.json").write_text(json.dumps([_raw(correlationId="arr")]), encoding="utf-8")
    (d / "c.json").write_text(
        json.dumps({"records": [_raw(correlationId="wrapped")]}), encoding="utf-8"
    )
    ids = {r.request_id for r in for_tenant(_TENANT_A, "logs", prefix="t", root=tmp_path).read_all()}
    assert ids == {"n1", "n2", "arr", "wrapped"}


def test_corrupt_line_is_skipped_by_default_but_raises_in_strict_mode(tmp_path):
    d = tmp_path / "logs" / "t"
    d.mkdir(parents=True)
    (d / "a.ndjson").write_text(
        json.dumps(_raw(correlationId="ok")) + "\n{broken\n", encoding="utf-8"
    )
    reader = for_tenant(_TENANT_A, "logs", prefix="t", root=tmp_path)
    assert [r.request_id for r in reader.read_all()] == ["ok"]
    with pytest.raises(AzureRecordError):
        reader.read_all(strict=True)


# ── AC-4: the corpus ────────────────────────────────────────────────────────


def test_corpus_exists_and_meets_the_fifty_record_bar():
    lines = CORPUS.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 50, f"corpus has {len(lines)} records, AC-4 requires >=50"


def test_corpus_regenerates_byte_identically():
    """Determinism underwrites attestations and the STORY-378 harness."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from azure_corpus_builder import generate_corpus, render

    assert render(generate_corpus()) == CORPUS.read_text(encoding="utf-8")


def test_corpus_carries_no_message_content_inv2():
    banned = ("prompt", "completion", "message", "content", "text")
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        props = rec.get("properties", {})
        for key in props:
            k = key.lower()
            if k in ("prompttokens", "completiontokens"):
                continue  # counts, not content
            assert not any(b in k and k not in ("apiname",) for b in banned), (
                f"corpus record carries a content-shaped field {key!r}"
            )


# ── AC-5: both packs evaluate the corpus end to end ─────────────────────────


def test_obs_complete_evaluates_the_corpus_and_finds_planted_scenarios():
    records = _corpus_records()
    assert len(records) >= 50
    findings = evaluate_records(records, [load_pack(OBS_PACK)])
    fired = {f.rule_id for f in findings}
    assert "OBS-TOKEN-COUNTS-1" in fired, "no-usage records should fire the token rule"
    assert "OBS-ERROR-INVOCATION-1" in fired, "planted error records should fire"


def test_unavailable_usage_is_reported_at_info_not_low():
    """A provider gap must not read as a defect in the customer's system."""
    records = _corpus_records()
    pack = load_pack(OBS_PACK)
    token_findings = [
        f
        for r in records
        for f in evaluate_record(r, pack)
        if f.rule_id == "OBS-TOKEN-COUNTS-1"
    ]
    assert token_findings
    assert any(f.severity == "INFO" for f in token_findings), (
        "records whose usage is structurally unavailable should be graded INFO"
    )


def test_tool_scope_detects_the_planted_violation_on_enriched_records():
    records = _corpus_records()
    pack = load_pack(TOOL_PACK).with_allowed_tools(["search_care_guidelines"])
    findings = evaluate_records(records, [pack])
    fired = {f.rule_id for f in findings}
    assert "TOOL-SCOPE-VIOLATION-1" in fired
    assert "TOOL-SCOPE-OFFERED-1" in fired
    violation = [f for f in findings if f.rule_id == "TOOL-SCOPE-VIOLATION-1"][0]
    assert violation.detail["invoked_out_of_scope"] == ["delete_patient_record"]


def test_standard_azure_records_yield_no_tool_findings_because_data_is_absent():
    """The load-bearing honesty test.

    Standard Azure diagnostic records carry no tool data, so RP-TOOL-SCOPE says
    nothing about them. That silence is a COVERAGE GAP, not evidence of scope
    compliance — and the adapter must mark it as such so the capability matrix
    (STORY-362) and any report generated from these findings cannot imply
    otherwise.
    """
    raw = _raw()  # no tool fields — the standard schema
    rec = _parse(raw)
    pack = load_pack(TOOL_PACK).with_allowed_tools(["search_care_guidelines"])

    assert evaluate_record(rec, pack) == [], "no tool data means no tool findings"
    assert rec.availability("tools") is FieldAvailability.UNAVAILABLE, (
        "absent tool data MUST be marked UNAVAILABLE — otherwise zero findings "
        "is indistinguishable from a clean result"
    )


def test_enriched_export_with_empty_tool_list_is_an_observation_not_a_gap():
    """Present-but-empty differs from absent: here we really did observe no tools."""
    raw = _raw()
    raw["properties"]["tools"] = []
    raw["properties"]["toolCalls"] = []
    rec = _parse(raw)
    assert rec.availability("tools") is FieldAvailability.PRESENT
    assert rec.tools == ()
