"""STORY-408 AC-3.4 — no client data or credentials in log output.

Runs a full assumed-role discover+read cycle under caplog and asserts the
external_id, session token, access key, and object body content never appear
in captured log text.
"""

from __future__ import annotations

import gzip
import json
import logging

import pytest

from adapters.bedrock.source import (
    S3LogStore,
    discover_object_keys,
    iter_backfill_records,
)
from services.tenant_log_source_config import validate_source_config

_EXTERNAL_ID = "super-secret-external-id-value-0123456789"
_STS_SESSION_CREDENTIAL = "super-secret-session-token-abcdefghijk"
_ACCESS_KEY = "AKIASECRETACCESSKEYVALUE"  # gitleaks:allow — fake AKIA constant; this test asserts it never reaches logs
_BODY_SECRET_MARKER = "PATIENT_PHI_MARKER_SHOULD_NEVER_BE_LOGGED"


class _FakeStsClient:
    def assume_role(self, **kwargs):
        import datetime

        assert kwargs["ExternalId"] == _EXTERNAL_ID
        return {
            "Credentials": {
                "AccessKeyId": _ACCESS_KEY,
                "SecretAccessKey": "secret",
                "SessionToken": _STS_SESSION_CREDENTIAL,
                "Expiration": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=1),
            }
        }


class _FakeS3Client:
    def __init__(self, objects):
        self._objects = objects

    def get_paginator(self, op_name):
        client = self

        class _Paginator:
            def paginate(self, **kwargs):
                yield {"Contents": [{"Key": k} for k in client._objects]}

        return _Paginator()

    def get_object(self, **kwargs):
        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self, _n=None):
                return self._data

        return {"Body": _Body(self._objects[kwargs["Key"]])}


@pytest.mark.unit
def test_no_secrets_or_body_content_in_log_output(caplog):
    config = validate_source_config(
        role_arn="arn:aws:iam::123456789012:role/SaroCrossAccountRole",
        external_id=_EXTERNAL_ID,
        bucket="summitcare-bedrock-logs",
        prefix="bedrock-logs",
        region="us-east-1",
        kms_key_arn=None,
    )
    good_key = "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/2026/07/06/00/obj.json.gz"
    full_key = f"bedrock-logs/{good_key}"
    record = {"schemaType": "ModelInvocationLog", "note": _BODY_SECRET_MARKER}
    body = gzip.compress((json.dumps(record) + "\n").encode("utf-8"), mtime=0)

    fake_sts = _FakeStsClient()
    fake_s3 = _FakeS3Client({full_key: body})

    with caplog.at_level(logging.DEBUG):
        store = S3LogStore.for_tenant(
            config, sts_client=fake_sts, s3_client_override=fake_s3
        )
        keys = discover_object_keys(
            store, account_id="999888777666", region="us-east-1"
        )
        list(iter_backfill_records(store, keys))

    log_text = caplog.text
    assert _EXTERNAL_ID not in log_text
    assert _STS_SESSION_CREDENTIAL not in log_text
    assert _ACCESS_KEY not in log_text
    assert _BODY_SECRET_MARKER not in log_text
