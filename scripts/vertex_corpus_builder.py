#!/usr/bin/env python3
"""Deterministic synthetic Vertex AI log corpus (STORY-360 AC-4).

Mirrors the Bedrock and Azure corpora's scenario coverage so the cross-adapter
conformance suite (STORY-361) compares like with like. Fully seed-derived: no
clock, no RNG, no uuid4 — the corpus underwrites attestations and the
confusion-matrix harness (STORY-378), which are meaningless if inputs drift.

Some records deliberately carry `protoPayload.request` / `.response` containing
PHI-shaped text. That is not an oversight: real Vertex Data Access logs can
contain exactly that, and the corpus must exercise the adapter's refusal to read
them. The strings are obvious synthetic placeholders, never real data.

Usage:
    python scripts/vertex_corpus_builder.py            # write the fixture
    python scripts/vertex_corpus_builder.py --check    # verify it is up to date
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "vertex" / "corpus.ndjson"

SEED = "STORY-360-vertex-corpus-v1"
BASE_TIME = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
PROJECT = "summitcare-clinical"
LOCATION_POOL = ["us-central1", "europe-west4"]

_PUBLISHER_MODELS = ["gemini-1.5-pro", "gemini-1.5-flash", "text-bison"]
_METHODS = [
    "google.cloud.aiplatform.v1.PredictionService.GenerateContent",
    "google.cloud.aiplatform.v1.PredictionService.Predict",
    "google.cloud.aiplatform.v1.PredictionService.StreamGenerateContent",
]


def _det(*parts: Any) -> int:
    digest = hashlib.sha256((SEED + "|" + "|".join(str(p) for p in parts)).encode())
    return int.from_bytes(digest.digest()[:8], "big")


def _insert_id(i: int) -> str:
    return hashlib.sha256((SEED + f"|insert|{i}").encode()).hexdigest()[:16]


def _iso_nanos(dt: datetime, extra_nanos: int) -> str:
    """RFC 3339 with 9 fractional digits — Cloud Logging's real precision."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:06d}{extra_nanos % 1000:03d}Z"


def _base_entry(i: int, *, publisher_model: bool = True) -> dict[str, Any]:
    location = LOCATION_POOL[_det(i, "loc") % len(LOCATION_POOL)]
    method = _METHODS[_det(i, "m") % len(_METHODS)]
    ts = BASE_TIME + timedelta(seconds=_det(i, "ts") % 3600, microseconds=i * 91)

    if publisher_model:
        model = _PUBLISHER_MODELS[_det(i, "mo") % len(_PUBLISHER_MODELS)]
        resource_name = (
            f"projects/{PROJECT}/locations/{location}/publishers/google/models/{model}"
        )
        labels = {"project_id": PROJECT, "location": location, "model_id": model}
        resource_type = "aiplatform.googleapis.com/PublisherModel"
    else:
        endpoint_id = str(1000000000 + (_det(i, "ep") % 8999999999))
        resource_name = f"projects/{PROJECT}/locations/{location}/endpoints/{endpoint_id}"
        labels = {"project_id": PROJECT, "location": location, "endpoint_id": endpoint_id}
        resource_type = "aiplatform.googleapis.com/Endpoint"

    return {
        "insertId": _insert_id(i),
        "logName": f"projects/{PROJECT}/logs/cloudaudit.googleapis.com%2Fdata_access",
        "timestamp": _iso_nanos(ts, _det(i, "ns")),
        "receiveTimestamp": _iso_nanos(ts + timedelta(milliseconds=40), _det(i, "ns2")),
        "severity": "INFO",
        "resource": {"type": resource_type, "labels": labels},
        "protoPayload": {
            "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
            "serviceName": "aiplatform.googleapis.com",
            "methodName": method,
            "resourceName": resource_name,
            "authenticationInfo": {"principalEmail": f"svc-{i % 5}@{PROJECT}.iam.gserviceaccount.com"},
            "requestMetadata": {"callerIp": "10.0.0.5", "callerSuppliedUserAgent": "vertex-client/1.0"},
            "status": {},
        },
    }


def generate_corpus() -> list[dict[str, Any]]:
    """56 entries covering the shared conformance scenarios."""
    records: list[dict[str, Any]] = []

    # 1. Happy path — publisher models, model identity resolvable.
    for i in range(30):
        records.append(_base_entry(i))

    # 2. Endpoint-deployed models — model identity NOT in the log (MISSING).
    for i in range(30, 38):
        records.append(_base_entry(i, publisher_model=False))

    # 3. Entries whose Data Access payload carries prompt/response content.
    #    The adapter must ignore these keys entirely (INV-2 under the hostile case).
    for i in range(38, 44):
        entry = _base_entry(i)
        entry["protoPayload"]["request"] = {
            "contents": [
                {"role": "user", "parts": [{"text": "SYNTHETIC-PHI patient MRN 000-11-2222 presents with chest pain"}]}
            ]
        }
        entry["protoPayload"]["response"] = {
            "candidates": [
                {"content": {"parts": [{"text": "SYNTHETIC-PHI assessment: recommend troponin panel"}]}}
            ]
        }
        records.append(entry)

    # 4. Missing region label.
    for i in range(44, 46):
        entry = _base_entry(i)
        entry["resource"]["labels"].pop("location")
        records.append(entry)

    # 5. Error statuses — google.rpc.Code values.
    for i, code in enumerate([7, 8, 4], start=46):
        entry = _base_entry(i)
        entry["protoPayload"]["status"] = {"code": code, "message": "synthetic failure"}
        entry["severity"] = "ERROR"
        records.append(entry)

    # 6. Enriched exports carrying tool metadata — in-scope tool use.
    for i in range(49, 51):
        entry = _base_entry(i)
        entry["labels"] = {
            "tools": [{"name": "lookup_care_pathway"}],
            "toolCalls": [{"name": "lookup_care_pathway"}],
        }
        records.append(entry)

    # 7. Tool-scope violation.
    entry = _base_entry(51)
    entry["labels"] = {
        "tools": [{"name": "lookup_care_pathway"}, {"name": "purge_audit_log"}],
        "toolCalls": [{"name": "purge_audit_log"}],
    }
    records.append(entry)

    # 8. Out-of-scope tool offered but not invoked.
    entry = _base_entry(52)
    entry["labels"] = {
        "tools": [{"name": "lookup_care_pathway"}, {"name": "bulk_export_records"}],
        "toolCalls": [{"name": "lookup_care_pathway"}],
    }
    records.append(entry)

    # 9. Another GCP service in the same sink — must be skipped, not misparsed.
    other = _base_entry(53)
    other["protoPayload"]["serviceName"] = "storage.googleapis.com"
    records.append(other)

    # 10. Malformed — no insertId.
    broken = _base_entry(54)
    broken.pop("insertId")
    records.append(broken)

    # 11. Malformed — no methodName.
    broken2 = _base_entry(55)
    broken2["protoPayload"].pop("methodName")
    records.append(broken2)

    return records


def render(records: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=True) for r in records) + "\n"


def main(argv: list[str]) -> int:
    content = render(generate_corpus())
    if "--check" in argv:
        if not FIXTURE.exists():
            print(f"FAIL: {FIXTURE} missing — run scripts/vertex_corpus_builder.py")
            return 1
        if FIXTURE.read_text(encoding="utf-8") != content:
            print("FAIL: Vertex corpus fixture is stale or the builder is non-deterministic")
            return 1
        print(f"vertex corpus OK: {len(content.splitlines())} records, byte-identical")
        return 0

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(content, encoding="utf-8")
    print(f"wrote {FIXTURE} ({len(content.splitlines())} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
