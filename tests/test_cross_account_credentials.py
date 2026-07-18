"""STORY-408 — cross-account STS AssumeRole credential handling.

Covers:
  AC-2.1  S3LogStore obtains credentials via STS AssumeRole with the tenant's
          external_id
  AC-2.2  credentials auto-refresh past a simulated expiry
  AC-3.1  confused-deputy: our code always passes ExternalId to AssumeRole
          (contract test — moto does not enforce IAM trust-policy conditions
          for AssumeRole, confirmed experimentally; documented in
          implementation-notes.md Deviations)
"""

from __future__ import annotations

import datetime

import pytest

from adapters.bedrock.cross_account import assume_role_credentials, refreshable_session

_ROLE_ARN = "arn:aws:iam::123456789012:role/SaroCrossAccountRole"
_EXTERNAL_ID = "a" * 32


class _FakeStsClient:
    """Captures every assume_role call; returns short-lived fake credentials."""

    def __init__(self, credential_sequence=None):
        self.calls: list[dict] = []
        self._sequence = list(credential_sequence or [])
        self._call_count = 0

    def assume_role(self, **kwargs):
        self.calls.append(kwargs)
        self._call_count += 1
        if self._sequence:
            idx = min(self._call_count - 1, len(self._sequence) - 1)
            return self._sequence[idx]
        return {
            "Credentials": {
                "AccessKeyId": f"AKIA-{self._call_count}",
                "SecretAccessKey": "secret",
                "SessionToken": f"token-{self._call_count}",
                "Expiration": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=1),
            }
        }


@pytest.mark.unit
def test_assume_role_always_passes_external_id():
    fake = _FakeStsClient()
    assume_role_credentials(_ROLE_ARN, _EXTERNAL_ID, sts_client=fake)
    assert len(fake.calls) == 1
    assert fake.calls[0]["ExternalId"] == _EXTERNAL_ID
    assert fake.calls[0]["RoleArn"] == _ROLE_ARN


@pytest.mark.unit
def test_assume_role_uses_a_stable_session_name_prefix():
    fake = _FakeStsClient()
    assume_role_credentials(_ROLE_ARN, _EXTERNAL_ID, sts_client=fake)
    assert fake.calls[0]["RoleSessionName"].startswith("saro-ingest")


@pytest.mark.unit
def test_returned_credentials_shape():
    fake = _FakeStsClient()
    creds = assume_role_credentials(_ROLE_ARN, _EXTERNAL_ID, sts_client=fake)
    assert set(creds.keys()) >= {"access_key", "secret_key", "token", "expiry_time"}


# ── AC-2.2: credentials auto-refresh past a simulated expiry ────────────────
@pytest.mark.unit
def test_refreshable_session_reassumes_on_expiry(monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    expired = now - datetime.timedelta(seconds=1)
    fresh = now + datetime.timedelta(hours=1)

    fake = _FakeStsClient(
        credential_sequence=[
            {
                "Credentials": {
                    "AccessKeyId": "AKIA-EXPIRED",
                    "SecretAccessKey": "s1",
                    "SessionToken": "t1",
                    "Expiration": expired,
                }
            },
            {
                "Credentials": {
                    "AccessKeyId": "AKIA-FRESH",
                    "SecretAccessKey": "s2",
                    "SessionToken": "t2",
                    "Expiration": fresh,
                }
            },
        ]
    )

    session = refreshable_session(
        _ROLE_ARN, _EXTERNAL_ID, region="us-east-1", sts_client=fake
    )
    creds = session.get_credentials()
    frozen = creds.get_frozen_credentials()
    # First call issued expired credentials; RefreshableCredentials must
    # re-assume transparently on access rather than returning stale creds.
    assert frozen.access_key == "AKIA-FRESH"
    assert len(fake.calls) == 2
    assert all(c["ExternalId"] == _EXTERNAL_ID for c in fake.calls)


@pytest.mark.unit
def test_refreshable_session_is_scoped_to_the_given_region():
    fake = _FakeStsClient()
    session = refreshable_session(
        _ROLE_ARN, _EXTERNAL_ID, region="eu-west-1", sts_client=fake
    )
    assert session.region_name == "eu-west-1"
