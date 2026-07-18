"""STORY-408 FR-4 — client onboarding CloudFormation template + doc.

Structural checks on the template (well-formed, matches FR-4's exact
requirement list). AC-4.1/AC-4.2 were live-verified against a real AWS
account on 2026-07-13 (see implementation-notes.md and this doc's own
"Validation status" section) — this test suite proves the template/doc are
well-formed and that the doc honestly discloses what was and wasn't covered
by that pass, not that it deploys clean (the live pass proved that; it isn't
re-run here since it requires a real AWS account).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[1]
_TEMPLATE_PATH = _REPO / "docs" / "deploy" / "cross-account-role.yaml"
_DOC_PATH = _REPO / "docs" / "deploy" / "cross-account-onboarding.md"


class _CfnLoader(yaml.SafeLoader):
    pass


def _cfn_multi_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    return {tag_suffix: loader.construct_mapping(node)}


_CfnLoader.add_multi_constructor("!", _cfn_multi_constructor)


def _load_template() -> dict:
    return yaml.load(_TEMPLATE_PATH.read_text(encoding="utf-8"), Loader=_CfnLoader)


def _flatten_if(stmt):
    """A statement may be `{"If": [condition, true_branch, false_branch]}`
    (Fn::If conditionally including a statement). Return the true_branch dict
    (or None if the false branch is Ref/AWS::NoValue) so tests can inspect the
    real statement contents regardless of whether it's conditional."""
    if isinstance(stmt, dict) and set(stmt.keys()) == {"If"}:
        _condition, true_branch, _false_branch = stmt["If"]
        return true_branch
    return stmt


@pytest.mark.unit
def test_template_is_structurally_valid_yaml():
    doc = _load_template()
    assert doc["AWSTemplateFormatVersion"] == "2010-09-09"
    assert "SaroCrossAccountRole" in doc["Resources"]


@pytest.mark.unit
def test_trust_policy_requires_external_id_condition():
    doc = _load_template()
    role = doc["Resources"]["SaroCrossAccountRole"]["Properties"]
    trust = role["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Action"] == "sts:AssumeRole"
    condition = trust["Condition"]["StringEquals"]
    assert "sts:ExternalId" in condition


@pytest.mark.unit
def test_permissions_are_least_privilege_no_wildcards():
    doc = _load_template()
    policy = doc["Resources"]["SaroCrossAccountRole"]["Properties"]["Policies"][0]
    statements = [_flatten_if(s) for s in policy["PolicyDocument"]["Statement"]]
    statements = [s for s in statements if s is not None]
    actions = set()
    for stmt in statements:
        action = stmt.get("Action")
        actions.add(action)
        resource_str = str(stmt.get("Resource"))
        assert resource_str != "*", f"wildcard resource on action {action}"

    assert actions == {"s3:ListBucket", "s3:GetObject", "kms:Decrypt"}
    # No write/delete actions anywhere in the policy.
    forbidden_fragments = ("Put", "Delete", "*:*")
    for stmt in statements:
        action_str = str(stmt.get("Action", ""))
        assert not any(f in action_str for f in forbidden_fragments)


@pytest.mark.unit
def test_list_bucket_is_prefix_conditioned():
    doc = _load_template()
    policy = doc["Resources"]["SaroCrossAccountRole"]["Properties"]["Policies"][0]
    statements = [_flatten_if(s) for s in policy["PolicyDocument"]["Statement"]]
    list_stmt = next(
        s for s in statements if s and s.get("Sid") == "ListBucketPrefixOnly"
    )
    assert "Condition" in list_stmt
    assert "s3:prefix" in list_stmt["Condition"]["StringLike"]


@pytest.mark.unit
def test_kms_decrypt_is_conditional_not_unconditional():
    doc = _load_template()
    assert "HasKmsKey" in doc.get("Conditions", {})
    policy = doc["Resources"]["SaroCrossAccountRole"]["Properties"]["Policies"][0]
    raw_statements = policy["PolicyDocument"]["Statement"]
    # The KMS statement must be the true-branch of an Fn::If, not a bare
    # unconditional statement — proves it's only granted when a KMS key was
    # actually supplied.
    conditional = [s for s in raw_statements if isinstance(s, dict) and "If" in s]
    assert len(conditional) == 1
    condition_name, true_branch, _false_branch = conditional[0]["If"]
    assert condition_name == "HasKmsKey"
    assert true_branch.get("Sid") == "DecryptLogObjects"
    assert true_branch.get("Action") == "kms:Decrypt"


@pytest.mark.unit
def test_role_arn_output_present():
    doc = _load_template()
    assert "RoleArn" in doc["Outputs"]


# ── onboarding doc: required content per FR-4's bullet list ──────────────────
@pytest.mark.unit
def test_onboarding_doc_covers_required_steps():
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert "put-model-invocation-logging-configuration" in text
    assert "cloudformation deploy" in text
    assert "RoleArn" in text or "role ARN" in text


@pytest.mark.unit
def test_onboarding_doc_does_not_overclaim_adr_004():
    text = " ".join(_DOC_PATH.read_text(encoding="utf-8").lower().split())
    # Positive-claim phrasing would be an ADR-004 overclaim; a *negated*
    # disclaimer ("does not certify...") is the correct, expected pattern and
    # must not trip this check.
    forbidden = (
        "is certified",
        "we certify",
        "saro certifies",
        "saro guarantees",
        "we ensure",
        "fully secure",
    )
    for phrase in forbidden:
        assert phrase not in text


@pytest.mark.unit
def test_onboarding_doc_discloses_validation_status_honestly():
    """AC-4.1/AC-4.2 were live-verified against a real AWS account
    (2026-07-13) — the doc must say so, but must not overclaim beyond what
    that pass actually covered: the ~81s figure is bot-executed AWS-side
    command latency, not a clocked human run, and the pass used a single AWS
    account rather than a literal two-account (client vs. SARO) dry run.
    Both caveats must stay visible, not get smoothed away into a bare claim
    of "validated"."""
    text = " ".join(_DOC_PATH.read_text(encoding="utf-8").lower().split())
    assert "executed for real against aws account" in text
    assert "has not been clocked against an actual first-time human run" in text
    assert "only one aws account was available" in text
