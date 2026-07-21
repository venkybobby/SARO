#!/usr/bin/env python3
"""Deterministic synthetic Azure OpenAI log corpus (STORY-359 AC-4).

Mirrors the Bedrock corpus's scenario coverage so the cross-adapter conformance
suite (STORY-361) compares like with like. Determinism is a hard requirement,
not a convenience: the corpus underwrites attestations and the confusion-matrix
harness (STORY-378), both of which are meaningless if the inputs drift between
runs. Everything derives from a fixed seed — no clock, no RNG state, no uuid4.

Synthetic by construction: no field carries prompt or completion content, so the
corpus cannot leak PHI even in principle (INV-2).

Usage:
    python scripts/azure_corpus_builder.py            # write the fixture
    python scripts/azure_corpus_builder.py --check    # verify it is up to date
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "azure" / "corpus.ndjson"

SEED = "STORY-359-azure-corpus-v1"
BASE_TIME = datetime(2026, 7, 1, 9, 0, 0, tzinfo=timezone.utc)
SUBSCRIPTION = "00000000-0000-0000-0000-0000000000a1"
RESOURCE_GROUP = "rg-clinical-ai"
ACCOUNT = "summitcare-aoai"

_MODELS = [
    ("gpt-4o", "2024-05-13", "prod-chat"),
    ("gpt-4o-mini", "2024-07-18", "prod-triage"),
    ("gpt-35-turbo", "0125", "legacy-intake"),
]
_OPERATIONS = ["ChatCompletions_Create", "Completions_Create", "Embeddings_Create"]
_LOCATIONS = ["eastus", "westeurope"]


def _det(*parts: Any) -> int:
    """Stable integer from a seed and parts — replaces any RNG."""
    digest = hashlib.sha256((SEED + "|" + "|".join(str(p) for p in parts)).encode())
    return int.from_bytes(digest.digest()[:8], "big")


def _det_guid(*parts: Any) -> str:
    hx = hashlib.sha256(
        (SEED + "|guid|" + "|".join(str(p) for p in parts)).encode()
    ).hexdigest()
    return f"{hx[0:8]}-{hx[8:12]}-{hx[12:16]}-{hx[16:20]}-{hx[20:32]}"


def _resource_id() -> str:
    return (
        f"/SUBSCRIPTIONS/{SUBSCRIPTION.upper()}/RESOURCEGROUPS/{RESOURCE_GROUP.upper()}"
        f"/PROVIDERS/MICROSOFT.COGNITIVESERVICES/ACCOUNTS/{ACCOUNT.upper()}"
    )


def _iso(dt: datetime) -> str:
    """Azure's 7-fractional-digit ISO form — the parser must handle it."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:06d}0" + "Z"


def _base_record(i: int, *, with_usage: bool = True) -> dict[str, Any]:
    model, version, deployment = _MODELS[_det(i, "model") % len(_MODELS)]
    operation = _OPERATIONS[_det(i, "op") % len(_OPERATIONS)]
    location = _LOCATIONS[_det(i, "loc") % len(_LOCATIONS)]
    ts = BASE_TIME + timedelta(seconds=_det(i, "ts") % 3600, microseconds=i * 137)

    props: dict[str, Any] = {
        "apiName": "Azure OpenAI API",
        "modelDeploymentName": deployment,
        "modelName": model,
        "modelVersion": version,
        "streamType": "Non-streaming",
        "objectId": _det_guid(i, "object"),
    }
    if with_usage:
        props["promptTokens"] = 50 + _det(i, "pt") % 400
        props["completionTokens"] = 10 + _det(i, "ct") % 200

    return {
        "time": _iso(ts),
        "resourceId": _resource_id(),
        "category": "RequestResponse",
        "operationName": operation,
        "durationMs": 100 + _det(i, "dur") % 2000,
        "resultSignature": "200",
        "resultType": "Success",
        "correlationId": _det_guid(i, "corr"),
        "location": location,
        "properties": props,
    }


def generate_corpus() -> list[dict[str, Any]]:
    """52 records covering the shared conformance scenarios.

    Scenario mix mirrors the Bedrock corpus: mostly happy path, with planted
    edge cases so a rule that fires on nothing is visibly broken rather than
    silently vacuous.
    """
    records: list[dict[str, Any]] = []

    # 1. Happy path — 34 records with full usage data.
    for i in range(34):
        records.append(_base_record(i))

    # 2. No usage fields — the common Azure configuration. Token counts must
    #    come back UNAVAILABLE (schema gap), not MISSING.
    for i in range(34, 40):
        records.append(_base_record(i, with_usage=False))

    # 3. Missing model identity — data-quality gap (MISSING, not UNAVAILABLE).
    for i in range(40, 43):
        rec = _base_record(i)
        rec["properties"].pop("modelName")
        rec["properties"].pop("modelVersion")
        rec["properties"].pop("modelDeploymentName")
        records.append(rec)

    # 4. Missing region.
    for i in range(43, 45):
        rec = _base_record(i)
        rec.pop("location")
        records.append(rec)

    # 5. Error invocations — RP-OBS-COMPLETE OBS-ERROR-INVOCATION-1.
    for i, (sig, rtype) in enumerate(
        [("429", "Failure"), ("500", "Failure"), ("400", "ClientError")], start=45
    ):
        rec = _base_record(i)
        rec["resultSignature"] = sig
        rec["resultType"] = rtype
        records.append(rec)

    # 6. Enriched exports carrying tool data — in-scope tool use.
    for i in range(48, 50):
        rec = _base_record(i)
        rec["properties"]["tools"] = [{"name": "search_care_guidelines"}]
        rec["properties"]["toolCalls"] = [{"name": "search_care_guidelines"}]
        records.append(rec)

    # 7. Tool-scope violation — an invoked tool outside any sane declared scope.
    rec = _base_record(50)
    rec["properties"]["tools"] = [
        {"name": "search_care_guidelines"},
        {"name": "delete_patient_record"},
    ]
    rec["properties"]["toolCalls"] = [{"name": "delete_patient_record"}]
    records.append(rec)

    # 8. Out-of-scope tool OFFERED but not invoked — capability without use.
    rec = _base_record(51)
    rec["properties"]["tools"] = [
        {"name": "search_care_guidelines"},
        {"name": "export_full_phi_dataset"},
    ]
    rec["properties"]["toolCalls"] = [{"name": "search_care_guidelines"}]
    records.append(rec)

    # 9. A non-RequestResponse record — must be skipped, not misparsed.
    audit = _base_record(52)
    audit["category"] = "Audit"
    records.append(audit)

    # 10. A malformed record — parser must reject rather than half-populate.
    broken = _base_record(53)
    broken.pop("correlationId")
    records.append(broken)

    return records


def render(records: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=True) for r in records) + "\n"


def main(argv: list[str]) -> int:
    content = render(generate_corpus())
    if "--check" in argv:
        if not FIXTURE.exists():
            print(f"FAIL: {FIXTURE} missing — run scripts/azure_corpus_builder.py")
            return 1
        current = FIXTURE.read_text(encoding="utf-8")
        if current != content:
            print("FAIL: Azure corpus fixture is stale or the builder is non-deterministic")
            return 1
        print(f"azure corpus OK: {len(current.splitlines())} records, byte-identical")
        return 0

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(content, encoding="utf-8")
    print(f"wrote {FIXTURE} ({len(content.splitlines())} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
