"""Cross-account STS AssumeRole credential handling (STORY-408).

SARO never stores client AWS credentials — only the parameters needed to
assume a client-provisioned, read-only IAM role via STS AssumeRole. Reaches
AWS STS (identity/token issuance) only, never a model-inference endpoint.

Two entry points:
  * `assume_role_credentials` — one-shot AssumeRole call, always passing the
    tenant's `external_id` (confused-deputy defense, AC-3.1).
  * `refreshable_session` — a boto3 Session backed by botocore's
    RefreshableCredentials, so long-running ingest runs never see stale/expired
    credentials (AC-2.2) without any re-assumption plumbing at call sites.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SESSION_NAME_PREFIX = "saro-ingest"


def _default_sts_client(region: str) -> Any:
    import boto3  # lazy: optional dependency, STS only

    return boto3.client("sts", region_name=region)


def _sts_credentials_to_dict(sts_response: dict) -> dict[str, Any]:
    """Normalize a raw STS AssumeRole response into botocore's
    RefreshableCredentials metadata shape."""
    creds = sts_response["Credentials"]
    expiry = creds["Expiration"]
    if isinstance(expiry, datetime):
        expiry_str = expiry.isoformat()
    else:
        expiry_str = str(expiry)
    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretAccessKey"],
        "token": creds["SessionToken"],
        "expiry_time": expiry_str,
    }


def assume_role_credentials(
    role_arn: str,
    external_id: str,
    *,
    sts_client: Optional[Any] = None,
    region: str = "us-east-1",
    session_name: str = _SESSION_NAME_PREFIX,
) -> dict[str, Any]:
    """One-shot STS AssumeRole call. ALWAYS passes ExternalId (AC-3.1) — there
    is no code path that omits it."""
    client = sts_client if sts_client is not None else _default_sts_client(region)
    response = client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
        ExternalId=external_id,
    )
    return _sts_credentials_to_dict(response)


def refreshable_session(
    role_arn: str,
    external_id: str,
    *,
    region: str,
    sts_client: Optional[Any] = None,
    session_name: str = _SESSION_NAME_PREFIX,
):
    """A boto3 Session whose credentials transparently re-assume the role on
    expiry (AC-2.2) — botocore's refreshable-credentials mechanism, chosen
    over re-assume-per-batch because it needs zero new orchestration code at
    every call site (S3LogStore, replay_backfill, the CLI)."""
    import boto3
    from botocore.credentials import RefreshableCredentials
    from botocore.session import Session as BotocoreSession

    def _refresh() -> dict[str, Any]:
        return assume_role_credentials(
            role_arn,
            external_id,
            sts_client=sts_client,
            region=region,
            session_name=session_name,
        )

    refreshable = RefreshableCredentials.create_from_metadata(
        metadata=_refresh(),
        refresh_using=_refresh,
        method="sts-assume-role",
    )

    botocore_session = BotocoreSession()
    botocore_session._credentials = refreshable  # noqa: SLF001 — the documented wiring point
    botocore_session.set_config_variable("region", region)

    return boto3.Session(botocore_session=botocore_session)
