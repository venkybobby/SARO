"""STORY-360 — Vertex AI observation adapter.

The distinguishing test in this file is
``test_phi_payload_present_in_source_never_reaches_the_record``. Azure's logs
contain no payload, so INV-2 held there by luck of the schema. Vertex Data
Access logs genuinely *can* contain the prompt and the completion, so INV-2 has
to be proven under the hostile case: payload present in the source, absent from
everything SARO produces.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from adapters.contract import FieldAvailability, NormalizedInvocationRecord  # noqa: E402
from adapters.export_source import OutOfScopeKey  # noqa: E402
from adapters.vertex_ai.parse import parse_record  # noqa: E402
from adapters.vertex_ai.records import (  # noqa: E402
    VERTEX_AI_ADAPTER_ID,
    VertexAdapterConfig,
    VertexRecordError,
    VertexServiceSkipped,
)
from adapters.vertex_ai.source import for_tenant  # noqa: E402
from rule_packs.observation.evaluate import evaluate_record, evaluate_records  # noqa: E402
from rule_packs.observation.loader import load_pack  # noqa: E402

pytestmark = pytest.mark.unit

_TENANT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-00000000000a")
_TENANT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-00000000000b")
_CONFIG = VertexAdapterConfig(tenant_id=_TENANT_A, container="gcs-logs", prefix="tenant-a")

_PACK_ROOT = ROOT / "rule_packs" / "observation"
OBS_PACK = _PACK_ROOT / "rp_obs_complete" / "1.0.0" / "pack.yaml"
TOOL_PACK = _PACK_ROOT / "rp_tool_scope" / "1.0.0" / "pack.yaml"
CORPUS = ROOT / "tests" / "fixtures" / "vertex" / "corpus.ndjson"

_PHI_MARKER = "SYNTHETIC-PHI"


def _raw(**over):
    base = {
        "insertId": "entry-1",
        "logName": "projects/p/logs/cloudaudit.googleapis.com%2Fdata_access",
        "timestamp": "2026-07-01T10:15:30.123456789Z",
        "severity": "INFO",
        "resource": {
            "type": "aiplatform.googleapis.com/PublisherModel",
            "labels": {"project_id": "p", "location": "us-central1"},
        },
        "protoPayload": {
            "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
            "serviceName": "aiplatform.googleapis.com",
            "methodName": "google.cloud.aiplatform.v1.PredictionService.GenerateContent",
            "resourceName": "projects/p/locations/us-central1/publishers/google/models/gemini-1.5-pro",
            "status": {},
        },
    }
    payload = over.pop("protoPayload", None)
    resource = over.pop("resource", None)
    base.update(over)
    if payload is not None:
        base["protoPayload"] = payload
    if resource is not None:
        base["resource"] = resource
    return base


def _parse(raw=None, config=_CONFIG, cursor="obj:L1"):
    return parse_record(raw or _raw(), config=config, cursor=cursor)


def _corpus_records(tenant=_TENANT_A):
    cfg = VertexAdapterConfig(tenant_id=tenant, container="gcs-logs", prefix="")
    out = []
    for i, line in enumerate(CORPUS.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            out.append(parse_record(line, config=cfg, cursor=f"corpus:L{i}"))
        except VertexRecordError:
            continue
    return out


# ── INV-2 under the hostile case — the reason this adapter differs ──────────


def test_phi_payload_present_in_source_never_reaches_the_record():
    """Vertex Data Access logs can carry the prompt and completion. Prove refusal."""
    raw = _raw()
    raw["protoPayload"]["request"] = {
        "contents": [{"role": "user", "parts": [{"text": f"{_PHI_MARKER} MRN 000-11-2222"}]}]
    }
    raw["protoPayload"]["response"] = {
        "candidates": [{"content": {"parts": [{"text": f"{_PHI_MARKER} diagnosis text"}]}}]
    }

    rec = _parse(raw)
    serialized = rec.model_dump_json()
    assert _PHI_MARKER not in serialized, "payload content leaked into the normalized record"

    # Key-level check, not substring: "request" legitimately appears inside
    # "request_id", so a naive `in` test would fail on a correct record.
    def _keys(node) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {k for v in node.values() for k in _keys(v)}
        if isinstance(node, list):
            return {k for item in node for k in _keys(item)}
        return set()

    leaked = _keys(json.loads(serialized)) & {"request", "response", "contents", "candidates"}
    assert not leaked, f"payload key(s) {sorted(leaked)} leaked into the record"


def test_phi_never_reaches_rule_findings_either():
    """Findings are what get exported as evidence — they must be clean too."""
    raw = _raw()
    raw["protoPayload"]["request"] = {"contents": [{"parts": [{"text": f"{_PHI_MARKER} secret"}]}]}
    raw["protoPayload"]["status"] = {"code": 7}
    rec = _parse(raw)
    for finding in evaluate_records([rec], [load_pack(OBS_PACK), load_pack(TOOL_PACK)]):
        assert _PHI_MARKER not in str(finding.to_evidence())


def test_corpus_contains_phi_bearing_entries_so_the_guard_is_not_vacuous():
    """If the corpus had no payloads, the INV-2 tests would prove nothing."""
    text = CORPUS.read_text(encoding="utf-8")
    assert _PHI_MARKER in text, "corpus must exercise the payload-present case"


def test_no_parsed_corpus_record_carries_any_payload_content():
    for rec in _corpus_records():
        assert _PHI_MARKER not in rec.model_dump_json()


# ── INV-1: the endpoint literal is a discriminator, not a call target ──────


def test_adapter_imports_no_gcp_sdk():
    """Backs the guard's endpoint-literal exemption with evidence.

    `aiplatform.googleapis.com` appears in records.py as a log `serviceName`
    discriminator. That exemption is only defensible while the adapter imports
    no provider SDK and makes no outbound call — asserted here, and referenced
    by name from grc/guards/external_model.ENDPOINT_LITERAL_EXEMPTIONS.
    """
    forbidden = (
        "google.generativeai",
        "google.cloud.aiplatform",
        "vertexai",
        "googleapiclient",
        "httpx",
        "requests",
        "urllib.request",
        "aiohttp",
    )
    for module in ("records", "parse", "source"):
        src = (ROOT / "adapters" / "vertex_ai" / f"{module}.py").read_text(encoding="utf-8")
        for name in forbidden:
            assert f"import {name}" not in src, f"{module}.py imports {name}"
            assert f"from {name}" not in src, f"{module}.py imports from {name}"


def test_guard_exemption_is_narrow_and_documented():
    from grc.guards.external_model import ENDPOINT_LITERAL_EXEMPTIONS

    key = ("adapters/vertex_ai/records.py", "aiplatform.googleapis.com")
    assert key in ENDPOINT_LITERAL_EXEMPTIONS
    assert len(ENDPOINT_LITERAL_EXEMPTIONS[key]) > 80, "exemption needs a real reason"
    # It must not have quietly grown into a blanket file exemption.
    from grc.guards.external_model import DEFAULT_ALLOWLIST

    assert "adapters/vertex_ai/records.py" not in DEFAULT_ALLOWLIST


def test_guard_still_catches_a_real_sdk_import_in_the_exempted_file(tmp_path):
    """The exemption must not blind the file to the control that actually matters."""
    from grc.guards.external_model import scan_paths

    target = tmp_path / "adapters" / "vertex_ai"
    target.mkdir(parents=True)
    (target / "records.py").write_text(
        'SUPPORTED_SERVICE = "aiplatform.googleapis.com"\nimport openai\n',
        encoding="utf-8",
    )
    violations = scan_paths([target], repo_root=tmp_path)
    kinds = {v.kind for v in violations}
    assert "import" in kinds, "SDK import in the exempted file must still be caught"
    assert "endpoint" not in kinds, "the discriminator literal should stay exempt"


# ── AC-1: parsing ───────────────────────────────────────────────────────────


def test_parses_vertex_entry_into_normalized_contract():
    rec = _parse()
    assert isinstance(rec, NormalizedInvocationRecord)
    assert rec.request_id == "entry-1"
    assert rec.operation == "PredictionService.GenerateContent"
    assert rec.region == "us-central1"
    assert rec.model_id == "gemini-1.5-pro"
    assert rec.provenance.adapter_id == VERTEX_AI_ADAPTER_ID


def test_nanosecond_timestamp_parses():
    """Cloud Logging emits 9 fractional digits; Python accepts at most 6."""
    rec = _parse()
    assert rec.timestamp.tzinfo is not None
    assert (rec.timestamp.hour, rec.timestamp.minute, rec.timestamp.second) == (10, 15, 30)
    assert rec.timestamp.microsecond == 123456


def test_rpc_status_code_maps_to_named_error():
    raw = _raw()
    raw["protoPayload"]["status"] = {"code": 7, "message": "denied"}
    assert _parse(raw).error_code == "PERMISSION_DENIED"


def test_status_code_zero_is_success_not_an_error():
    raw = _raw()
    raw["protoPayload"]["status"] = {"code": 0}
    assert _parse(raw).error_code is None


def test_unknown_rpc_code_still_surfaces_rather_than_vanishing():
    raw = _raw()
    raw["protoPayload"]["status"] = {"code": 99}
    assert _parse(raw).error_code == "RPC_99"


# ── AC-3: honest degradation ────────────────────────────────────────────────


def test_endpoint_deployment_yields_missing_model_not_an_endpoint_id():
    """An endpoint id is not a model id — passing it off would break allowlists."""
    raw = _raw()
    raw["protoPayload"]["resourceName"] = "projects/p/locations/us-central1/endpoints/123456"
    rec = _parse(raw)
    assert rec.model_id == ""
    assert rec.availability("model_id") is FieldAvailability.MISSING
    assert "123456" not in rec.model_id


def test_token_counts_and_stop_reason_are_structurally_unavailable():
    rec = _parse()
    for field in ("input_token_count", "output_token_count", "stop_reason", "truncated"):
        assert rec.availability(field) is FieldAvailability.UNAVAILABLE, field


def test_missing_region_is_marked_missing():
    raw = _raw()
    raw["resource"]["labels"].pop("location")
    assert _parse(raw).availability("region") is FieldAvailability.MISSING


def test_no_field_is_ever_silently_none():
    raw = _raw()
    raw["resource"]["labels"].pop("location")
    raw["protoPayload"]["resourceName"] = "projects/p/locations/l/endpoints/9"
    rec = _parse(raw)
    for field in ("input_token_count", "output_token_count", "region", "model_id"):
        if getattr(rec, field, None) in (None, ""):
            assert rec.availability(field) is not FieldAvailability.PRESENT, field


# ── Malformed / other services ──────────────────────────────────────────────


def test_entry_without_insert_id_is_rejected():
    raw = _raw()
    raw.pop("insertId")
    with pytest.raises(VertexRecordError):
        _parse(raw)


def test_entry_without_method_name_is_rejected():
    raw = _raw()
    raw["protoPayload"].pop("methodName")
    with pytest.raises(VertexRecordError):
        _parse(raw)


def test_other_gcp_service_is_skipped_not_misparsed():
    raw = _raw()
    raw["protoPayload"]["serviceName"] = "storage.googleapis.com"
    with pytest.raises(VertexServiceSkipped):
        _parse(raw)


def test_invalid_json_is_rejected():
    with pytest.raises(VertexRecordError):
        parse_record("{nope", config=_CONFIG, cursor="c")


# ── AC-6 / INV-3 ────────────────────────────────────────────────────────────


def test_project_id_in_log_cannot_override_tenant_binding():
    raw = _raw()
    raw["resource"]["labels"]["project_id"] = str(_TENANT_B)
    raw["protoPayload"]["authenticationInfo"] = {"principalEmail": f"{_TENANT_B}@evil.test"}
    assert _parse(raw).tenant_id == _TENANT_A


def test_two_tenants_read_only_their_own_export(tmp_path):
    for name, insert in (("tenant-a", "a-1"), ("tenant-b", "b-1")):
        d = tmp_path / "gcs-logs" / name
        d.mkdir(parents=True)
        (d / "log.json").write_text(json.dumps(_raw(insertId=insert)), encoding="utf-8")

    a = for_tenant(_TENANT_A, "gcs-logs", prefix="tenant-a", root=tmp_path).read_all()
    b = for_tenant(_TENANT_B, "gcs-logs", prefix="tenant-b", root=tmp_path).read_all()
    assert [r.request_id for r in a] == ["a-1"]
    assert [r.request_id for r in b] == ["b-1"]
    assert {r.tenant_id for r in a} == {_TENANT_A}


def test_reader_rejects_traversal_and_prefix_confusion(tmp_path):
    (tmp_path / "gcs-logs" / "tenant-1").mkdir(parents=True)
    (tmp_path / "gcs-logs" / "tenant-10").mkdir(parents=True)
    (tmp_path / "gcs-logs" / "tenant-10" / "x.json").write_text(
        json.dumps(_raw()), encoding="utf-8"
    )
    reader = for_tenant(_TENANT_A, "gcs-logs", prefix="tenant-1", root=tmp_path)
    assert reader.list_objects() == []
    with pytest.raises(OutOfScopeKey):
        reader.read_object("tenant-10/x.json")
    with pytest.raises(OutOfScopeKey):
        reader.read_object("tenant-1/../tenant-10/x.json")


def test_corrupt_line_skipped_by_default_raises_in_strict(tmp_path):
    d = tmp_path / "gcs-logs" / "t"
    d.mkdir(parents=True)
    (d / "a.ndjson").write_text(json.dumps(_raw(insertId="ok")) + "\n{broken\n", encoding="utf-8")
    reader = for_tenant(_TENANT_A, "gcs-logs", prefix="t", root=tmp_path)
    assert [r.request_id for r in reader.read_all()] == ["ok"]
    with pytest.raises(VertexRecordError):
        reader.read_all(strict=True)


# ── AC-4: the corpus ────────────────────────────────────────────────────────


def test_corpus_meets_the_fifty_record_bar():
    lines = CORPUS.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 50, f"corpus has {len(lines)} records, AC-4 requires >=50"


def test_corpus_regenerates_byte_identically():
    sys.path.insert(0, str(ROOT / "scripts"))
    from vertex_corpus_builder import generate_corpus, render

    assert render(generate_corpus()) == CORPUS.read_text(encoding="utf-8")


# ── AC-5: both packs evaluate the corpus ────────────────────────────────────


def test_obs_complete_evaluates_corpus_and_finds_planted_scenarios():
    records = _corpus_records()
    assert len(records) >= 50
    fired = {f.rule_id for f in evaluate_records(records, [load_pack(OBS_PACK)])}
    assert "OBS-ERROR-INVOCATION-1" in fired
    assert "OBS-TOKEN-COUNTS-1" in fired


def test_all_vertex_token_findings_are_info_because_the_gap_is_structural():
    """Vertex audit logs never report usage — that is the provider's limit, and
    grading it LOW would blame the customer for Google's schema."""
    pack = load_pack(OBS_PACK)
    findings = [
        f
        for r in _corpus_records()
        for f in evaluate_record(r, pack)
        if f.rule_id == "OBS-TOKEN-COUNTS-1"
    ]
    assert findings
    assert all(f.severity == "INFO" for f in findings)


def test_tool_scope_detects_planted_violation_on_enriched_entries():
    pack = load_pack(TOOL_PACK).with_allowed_tools(["lookup_care_pathway"])
    findings = evaluate_records(_corpus_records(), [pack])
    fired = {f.rule_id for f in findings}
    assert "TOOL-SCOPE-VIOLATION-1" in fired
    assert "TOOL-SCOPE-OFFERED-1" in fired
    violation = [f for f in findings if f.rule_id == "TOOL-SCOPE-VIOLATION-1"][0]
    assert violation.detail["invoked_out_of_scope"] == ["purge_audit_log"]


def test_standard_audit_entries_yield_no_tool_findings_because_data_is_absent():
    """Same honesty constraint as Azure: silence is a gap, not a clean result."""
    rec = _parse()
    pack = load_pack(TOOL_PACK).with_allowed_tools(["lookup_care_pathway"])
    assert evaluate_record(rec, pack) == []
    assert rec.availability("tools") is FieldAvailability.UNAVAILABLE
