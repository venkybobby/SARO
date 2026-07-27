"""GcsExportStore — direct read from a customer GCS bucket (INV-6/INV-3).

No network, no google-cloud-storage SDK: a fake client is injected, so these
tests exercise the real store + reader isolation logic without either. The one
test that DOES touch the SDK path asserts the actionable error when it's absent
(it is absent in CI), never a live call.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.export_source import (
    GcsExportStore,
    OutOfScopeKey,
    build_gcs_store,
    parse_gs_uri,
)
from adapters.vertex_ai.source import for_tenant

pytestmark = pytest.mark.unit


# ── Fake GCS client (mirrors the slice of the SDK the store uses) ────────────


class _FakeBlob:
    def __init__(self, name: str, text: str) -> None:
        self.name = name
        self._text = text

    def download_as_text(self) -> str:
        return self._text


class _FakeBucketHandle:
    def __init__(self, blobs: dict[str, str]) -> None:
        self._blobs = blobs

    def blob(self, key: str) -> _FakeBlob:
        return _FakeBlob(key, self._blobs[key])


class _FakeClient:
    """Exposes list_blobs(bucket, prefix=...) and bucket(name).blob(key)."""

    def __init__(self, bucket: str, blobs: dict[str, str]) -> None:
        self._bucket = bucket
        self._blobs = blobs

    def list_blobs(self, bucket: str, prefix=None):
        assert bucket == self._bucket
        for name, text in self._blobs.items():
            if prefix is None or name.startswith(prefix):
                yield _FakeBlob(name, text)

    def bucket(self, name: str) -> _FakeBucketHandle:
        assert name == self._bucket
        return _FakeBucketHandle(self._blobs)


_VERTEX_LINE = (
    '{"insertId":"abc123","timestamp":"2026-07-26T00:00:00.000000000Z",'
    '"resource":{"labels":{"location":"us-central1"}},'
    '"protoPayload":{"@type":"type.googleapis.com/google.cloud.audit.AuditLog",'
    '"serviceName":"aiplatform.googleapis.com",'
    '"methodName":"google.cloud.aiplatform.v1.PredictionService.GenerateContent",'
    '"resourceName":"projects/p/locations/us-central1/publishers/google/models/gemini-2.0-flash",'
    '"status":{}}}'
)

BUCKET = "saro-vertex-export-veriaegis"


def _client(blobs: dict[str, str]) -> _FakeClient:
    return _FakeClient(BUCKET, blobs)


# ── parse_gs_uri ─────────────────────────────────────────────────────────────


def test_parse_gs_uri_variants():
    assert parse_gs_uri("gs://b/tenant-1/logs") == ("b", "tenant-1/logs")
    assert parse_gs_uri("gs://b") == ("b", "")
    assert parse_gs_uri("gs://b/p/") == ("b", "p")
    with pytest.raises(ValueError):
        parse_gs_uri("s3://b/p")
    with pytest.raises(ValueError):
        parse_gs_uri("gs://")


# ── list_keys scope (the cross-tenant hazard) ────────────────────────────────


def test_list_keys_prefix_scope_is_segment_bounded():
    # tenant-1/ must NOT admit tenant-10/ — the classic startswith bug.
    blobs = {
        "tenant-1/a.ndjson": _VERTEX_LINE,
        "tenant-1/sub/b.ndjson": _VERTEX_LINE,
        "tenant-10/c.ndjson": _VERTEX_LINE,
        "other/d.ndjson": _VERTEX_LINE,
    }
    store = GcsExportStore(BUCKET, client=_client(blobs))
    keys = store.list_keys(BUCKET, "tenant-1/")
    assert keys == ["tenant-1/a.ndjson", "tenant-1/sub/b.ndjson"]


def test_read_text_downloads_the_named_blob():
    store = GcsExportStore(BUCKET, client=_client({"tenant-1/a.ndjson": _VERTEX_LINE}))
    assert store.read_text(BUCKET, "tenant-1/a.ndjson") == _VERTEX_LINE


# ── build_gcs_store + reader end-to-end (fake client, no network) ────────────


def test_build_gcs_store_returns_bucket_and_prefix():
    store, container, prefix = build_gcs_store(
        "gs://saro-vertex-export-veriaegis/demo-tenant", client=_client({})
    )
    assert isinstance(store, GcsExportStore)
    assert container == "saro-vertex-export-veriaegis"
    assert prefix == "demo-tenant"


def test_reader_reads_records_through_gcs_store():
    blobs = {
        "demo-tenant/2026-07-26.ndjson": _VERTEX_LINE,
        "another-tenant/x.ndjson": _VERTEX_LINE,  # out of scope, must be ignored
    }
    store = GcsExportStore(BUCKET, client=_client(blobs))
    reader = for_tenant(uuid.uuid4(), BUCKET, prefix="demo-tenant/", store=store)
    records = reader.read_all()
    assert len(records) == 1
    assert records[0].request_id == "abc123"
    assert records[0].model_id == "gemini-2.0-flash"
    # provenance points at the gs source, tenancy is the operator's uuid
    assert records[0].provenance.source_uri.startswith("gs://")


def test_out_of_scope_key_is_rejected_by_reader():
    # A blob the store somehow lists outside prefix is still caught by the reader.
    store = GcsExportStore(BUCKET, client=_client({"evil/x.ndjson": _VERTEX_LINE}))
    reader = for_tenant(uuid.uuid4(), BUCKET, prefix="demo-tenant/", store=store)
    # nothing in scope -> empty, and a direct out-of-scope read raises
    assert reader.list_objects() == []
    with pytest.raises(OutOfScopeKey):
        reader.read_object("evil/x.ndjson")


# ── SDK-absent path (google-cloud-storage is not installed in CI) ────────────


def test_no_client_raises_actionable_error():
    # No client injected -> _default_client. Whether the SDK is absent (ImportError)
    # or present-but-unauthenticated (DefaultCredentialsError in CI, where the dep
    # is installed but no ADC exists), the operator must get one actionable
    # RuntimeError naming the fix — never a raw google traceback.
    with pytest.raises(RuntimeError, match="google-cloud-storage|reader principal"):
        GcsExportStore(BUCKET)
