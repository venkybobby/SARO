"""STORY-408 — S3LogStore cross-account entry point + security properties.

Covers:
  AC-2.1  S3LogStore.for_tenant obtains credentials via STS AssumeRole with
          the tenant's external_id
  AC-2.3  a missing-KMS-permission failure produces a distinct, actionable
          error message naming the key requirement
  AC-2.4  existing local/own-account paths continue to work unchanged
  AC-3.2  the reader never attempts writes (interface-level guarantee)
  AC-3.3  read scope is prefix-bound: keys outside the configured prefix are
          never requested
"""

from __future__ import annotations

import gzip
import inspect
import json

import pytest

from adapters.bedrock.source import LocalLogStore, LogObjectStore, S3LogStore
from services.tenant_log_source_config import validate_source_config

_ROLE_ARN = "arn:aws:iam::123456789012:role/SaroCrossAccountRole"
_EXTERNAL_ID = "a" * 32


def _tenant_config(**overrides):
    kwargs = dict(
        role_arn=_ROLE_ARN,
        external_id=_EXTERNAL_ID,
        bucket="summitcare-bedrock-logs",
        prefix="bedrock-logs",
        region="us-east-1",
        kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/abcd-1234",
    )
    kwargs.update(overrides)
    return validate_source_config(**kwargs)


class _FakeStsClient:
    def assume_role(self, **kwargs):
        self.last_call = kwargs
        import datetime

        return {
            "Credentials": {
                "AccessKeyId": "AKIA-TEST",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=1),
            }
        }


class _FakeS3Client:
    """Duck-typed boto3 s3 client: records every call's params, serves gzipped
    NDJSON objects from an in-memory dict keyed by full S3 key."""

    def __init__(self, objects: dict[str, bytes]):
        self._objects = objects
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []

    def get_paginator(self, op_name):
        assert op_name == "list_objects_v2"
        client = self

        class _Paginator:
            def paginate(self, **kwargs):
                client.list_calls.append(kwargs)
                prefix = kwargs.get("Prefix", "")
                contents = [{"Key": k} for k in client._objects if k.startswith(prefix)]
                yield {"Contents": contents}

        return _Paginator()

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self._objects:
            raise KeyError(key)

        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self, _n=None):
                return self._data

        return {"Body": _Body(self._objects[key])}


class _KmsDeniedS3Client(_FakeS3Client):
    def get_object(self, **kwargs):
        from botocore.exceptions import ClientError

        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDenied",
                    "Message": "User is not authorized to perform: kms:Decrypt",
                }
            },
            "GetObject",
        )


def _record_bytes(record: dict) -> bytes:
    return gzip.compress((json.dumps(record) + "\n").encode("utf-8"), mtime=0)


# ── AC-2.1: role assumption wiring ────────────────────────────────────────────
@pytest.mark.unit
def test_for_tenant_assumes_role_with_external_id(monkeypatch):
    config = _tenant_config()
    fake_sts = _FakeStsClient()
    fake_s3 = _FakeS3Client({})

    store = S3LogStore.for_tenant(
        config, sts_client=fake_sts, s3_client_override=fake_s3
    )

    assert store.bucket == config.bucket
    assert store.prefix_root == "bedrock-logs"
    assert fake_sts.last_call["ExternalId"] == _EXTERNAL_ID
    assert fake_sts.last_call["RoleArn"] == _ROLE_ARN


# ── AC-2.3: KMS access-denied maps to a clear, actionable error ─────────────
@pytest.mark.unit
def test_missing_kms_permission_raises_actionable_error():
    config = _tenant_config()
    fake_sts = _FakeStsClient()
    fake_s3 = _KmsDeniedS3Client({})

    store = S3LogStore.for_tenant(
        config, sts_client=fake_sts, s3_client_override=fake_s3
    )
    key = "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/2026/07/06/00/obj.json.gz"
    key = f"bedrock-logs/{key}"  # not used directly — read_bytes takes the bare key
    bare_key = "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/2026/07/06/00/obj.json.gz"

    with pytest.raises(ValueError) as exc_info:
        store.read_bytes(bare_key)
    msg = str(exc_info.value).lower()
    assert "kms" in msg
    assert config.kms_key_arn.lower() in msg


# ── AC-2.4: existing local/own-account paths unchanged ───────────────────────
@pytest.mark.unit
def test_plain_s3_log_store_construction_unchanged():
    store = S3LogStore("my-bucket", prefix_root="some/prefix")
    assert store.bucket == "my-bucket"
    assert store.prefix_root == "some/prefix"


@pytest.mark.unit
def test_local_log_store_unaffected(tmp_path):
    store = LocalLogStore(tmp_path)
    assert store.root == tmp_path


# ── AC-3.2: interface-level no-write guarantee ────────────────────────────────
@pytest.mark.unit
def test_s3_log_store_exposes_no_write_methods():
    members = {name for name, _ in inspect.getmembers(S3LogStore)}
    forbidden = {"put_object", "delete_object", "write_bytes", "delete", "put"}
    assert not (members & forbidden)


@pytest.mark.unit
def test_log_object_store_protocol_is_read_only():
    protocol_methods = (
        set(LogObjectStore.__protocol_attrs__)
        if hasattr(LogObjectStore, "__protocol_attrs__")
        else {name for name in dir(LogObjectStore) if not name.startswith("_")}
    )
    assert protocol_methods == {"iter_object_keys", "read_bytes"}


# ── AC-3.3: prefix-bound reads ─────────────────────────────────────────────────
@pytest.mark.unit
def test_discovery_and_read_never_escape_the_configured_prefix():
    from adapters.bedrock.source import discover_object_keys, iter_backfill_records

    good_key = "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/2026/07/06/00/obj.json.gz"
    full_key = f"bedrock-logs/{good_key}"
    record = {"schemaType": "ModelInvocationLog"}

    config = _tenant_config()
    fake_sts = _FakeStsClient()
    fake_s3 = _FakeS3Client({full_key: _record_bytes(record)})
    store = S3LogStore.for_tenant(
        config, sts_client=fake_sts, s3_client_override=fake_s3
    )

    keys = discover_object_keys(store, account_id="999888777666", region="us-east-1")
    assert keys == [good_key]
    list(iter_backfill_records(store, keys))

    for call in fake_s3.list_calls:
        assert call["Prefix"].startswith("bedrock-logs")
    for call in fake_s3.get_calls:
        assert call["Key"].startswith("bedrock-logs/")
