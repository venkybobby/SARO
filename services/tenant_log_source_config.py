"""Per-tenant cross-account log source config — validation + generation (STORY-408).

Boundary validation for `TenantLogSourceConfig` (models.py), matching the
discipline `scripts/demo_corpus_builder.py` already applies to manifest fields
(account_id/region regex checks) and `adapters/bedrock/source.py` applies to
object keys (`_KEY_SHAPE_RE`, path-traversal containment).

Never reads or writes AWS resources — pure validation/generation.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Optional

_ROLE_ARN_RE = re.compile(r"^arn:aws:iam::(\d{12}):role/[A-Za-z0-9+=,.@_-]{1,64}$")
_KMS_ARN_RE = re.compile(r"^arn:aws:kms:[a-z0-9-]+:\d{12}:key/[A-Za-z0-9-]{1,128}$")
_REGION_RE = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")
# S3 bucket naming rules (lowercase, digits, hyphens, dots; 3-63 chars).
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_MIN_EXTERNAL_ID_LEN = 32


class SourceConfigValidationError(ValueError):
    """Raised when a tenant log source config fails boundary validation."""

    def __init__(self, field_name: str, detail: str) -> None:
        self.field_name = field_name
        super().__init__(f"tenant_log_source_config: field={field_name!r} — {detail}")


@dataclass(frozen=True)
class ValidatedSourceConfig:
    role_arn: str
    external_id: str
    bucket: str
    prefix: str
    region: str
    kms_key_arn: Optional[str] = None

    def __repr__(self) -> str:  # AC-1.2: external_id never appears in repr/str
        return (
            f"ValidatedSourceConfig(role_arn={self.role_arn!r}, "
            f"external_id=<redacted>, bucket={self.bucket!r}, "
            f"prefix={self.prefix!r}, region={self.region!r}, "
            f"kms_key_arn={self.kms_key_arn!r})"
        )

    @property
    def account_id(self) -> str:
        return account_id_from_role_arn(self.role_arn)

    __str__ = __repr__


def account_id_from_role_arn(role_arn: str) -> str:
    """The Bedrock S3 key layout embeds the client's AWS account id
    (AWSLogs/{account_id}/...) — derived from role_arn rather than stored as a
    separate field, since an IAM role ARN already carries its account id and a
    second copy would be one more place for the two to silently drift apart."""
    match = _ROLE_ARN_RE.match(role_arn)
    if not match:
        raise SourceConfigValidationError(
            "role_arn", f"cannot extract account id from {role_arn!r}"
        )
    return match.group(1)


def generate_external_id() -> str:
    """Cryptographically random, >=32 chars (AC-1.2). Not an AWS credential —
    a confused-deputy defense SARO itself generates and controls."""
    return secrets.token_urlsafe(32)


def _normalize_prefix(prefix: str) -> str:
    p = (prefix or "").strip()
    if ".." in p:
        raise SourceConfigValidationError(
            "prefix", f"must not contain '..': {prefix!r}"
        )
    return p.lstrip("/")


def validate_source_config(
    *,
    role_arn: str,
    external_id: Optional[str],
    bucket: str,
    prefix: str,
    region: str,
    kms_key_arn: Optional[str] = None,
) -> ValidatedSourceConfig:
    """Validate all fields at the boundary (AC-1.1). Raises
    SourceConfigValidationError on the first invalid field, never partially
    constructs a config from unvalidated input."""
    if not role_arn or not _ROLE_ARN_RE.match(role_arn):
        raise SourceConfigValidationError(
            "role_arn", f"must match {_ROLE_ARN_RE.pattern}, got {role_arn!r}"
        )
    if not external_id or len(external_id) < _MIN_EXTERNAL_ID_LEN:
        raise SourceConfigValidationError(
            "external_id",
            f"must be >= {_MIN_EXTERNAL_ID_LEN} chars (got "
            f"{len(external_id) if external_id else 0})",
        )
    if not bucket or not _BUCKET_RE.match(bucket):
        raise SourceConfigValidationError(
            "bucket", f"must be a valid S3 bucket name, got {bucket!r}"
        )
    if not region or not _REGION_RE.match(region):
        raise SourceConfigValidationError(
            "region", f"must match {_REGION_RE.pattern}, got {region!r}"
        )
    if kms_key_arn and not _KMS_ARN_RE.match(kms_key_arn):
        raise SourceConfigValidationError(
            "kms_key_arn", f"must match {_KMS_ARN_RE.pattern}, got {kms_key_arn!r}"
        )

    normalized_prefix = _normalize_prefix(prefix)

    return ValidatedSourceConfig(
        role_arn=role_arn,
        external_id=external_id,
        bucket=bucket,
        prefix=normalized_prefix,
        region=region,
        kms_key_arn=kms_key_arn,
    )
