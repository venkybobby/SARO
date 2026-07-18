"""STORY-408 — per-tenant cross-account log source config validation.

Covers:
  AC-1.1  config validated at load (ARN shape, region format, prefix normalization)
  AC-1.2  external_id is cryptographically random, >=32 chars, never appears in
          repr()/str() (informational secret, but "never logged")
"""

from __future__ import annotations

import pytest

from services.tenant_log_source_config import (
    SourceConfigValidationError,
    account_id_from_role_arn,
    generate_external_id,
    validate_source_config,
)


def _valid_kwargs(**overrides):
    kwargs = dict(
        role_arn="arn:aws:iam::123456789012:role/SaroCrossAccountRole",
        external_id="a" * 32,
        bucket="summitcare-bedrock-logs",
        prefix="bedrock-logs/",
        region="us-east-1",
        kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/abcd-1234",
    )
    kwargs.update(overrides)
    return kwargs


@pytest.mark.unit
def test_valid_config_passes():
    cfg = validate_source_config(**_valid_kwargs())
    assert cfg.role_arn == "arn:aws:iam::123456789012:role/SaroCrossAccountRole"
    assert cfg.prefix == "bedrock-logs/"


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_arn",
    [
        "not-an-arn",
        "arn:aws:s3:::some-bucket",  # wrong service
        "arn:aws:iam::123:role/x",  # account id not 12 digits
        "",
    ],
)
def test_bad_role_arn_rejected(bad_arn):
    with pytest.raises(SourceConfigValidationError):
        validate_source_config(**_valid_kwargs(role_arn=bad_arn))


@pytest.mark.unit
@pytest.mark.parametrize("bad_region", ["US-EAST-1", "us_east_1", "", "us-east-1;drop"])
def test_bad_region_rejected(bad_region):
    with pytest.raises(SourceConfigValidationError):
        validate_source_config(**_valid_kwargs(region=bad_region))


@pytest.mark.unit
def test_prefix_normalization_strips_leading_slash():
    cfg = validate_source_config(**_valid_kwargs(prefix="/bedrock-logs/"))
    assert cfg.prefix == "bedrock-logs/"


@pytest.mark.unit
def test_prefix_traversal_rejected():
    with pytest.raises(SourceConfigValidationError):
        validate_source_config(**_valid_kwargs(prefix="../etc"))


@pytest.mark.unit
@pytest.mark.parametrize("bad_external_id", ["short", "x" * 31, "", None])
def test_short_external_id_rejected(bad_external_id):
    with pytest.raises(SourceConfigValidationError):
        validate_source_config(**_valid_kwargs(external_id=bad_external_id))


@pytest.mark.unit
def test_bad_bucket_name_rejected():
    with pytest.raises(SourceConfigValidationError):
        validate_source_config(**_valid_kwargs(bucket="Not_A_Valid_Bucket!"))


# ── AC-1.2: external_id generation + never-logged discipline ─────────────────
@pytest.mark.unit
def test_generate_external_id_is_long_and_random():
    a = generate_external_id()
    b = generate_external_id()
    assert len(a) >= 32
    assert a != b


@pytest.mark.unit
def test_validated_config_repr_never_leaks_external_id():
    cfg = validate_source_config(
        **_valid_kwargs(external_id="super-secret-value-x" * 2)
    )
    assert "super-secret-value-x" not in repr(cfg)
    assert "super-secret-value-x" not in str(cfg)


# ── account_id derivation from role_arn ───────────────────────────────────────
@pytest.mark.unit
def test_account_id_extracted_from_role_arn():
    assert (
        account_id_from_role_arn("arn:aws:iam::123456789012:role/SaroCrossAccountRole")
        == "123456789012"
    )


@pytest.mark.unit
def test_validated_config_exposes_account_id_property():
    cfg = validate_source_config(**_valid_kwargs())
    assert cfg.account_id == "123456789012"
