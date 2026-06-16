"""STORY-327 — Named-human residual-risk sign-off tests.

AC coverage:
- A residual-risk acceptance without a named accepted_by is rejected.
- The role must match an allowed sign-off role from config for that tier.
- accepted_at is recorded and immutable once set.
- GO_WITH_CONDITIONS is not finalized until sign-off is present.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from grc.signoff import (
    SignOff,
    SignOffError,
    create_signoff,
    finalize_gate,
    requires_signoff,
)

pytestmark = pytest.mark.unit


def test_missing_accepted_by_rejected() -> None:
    with pytest.raises(SignOffError, match="named accepted_by"):
        create_signoff(role="compliance_lead", accepted_by="", tier="HIGH")
    with pytest.raises(SignOffError):
        create_signoff(role="compliance_lead", accepted_by="   ", tier="HIGH")


def test_role_must_be_allowed_for_tier() -> None:
    # Default policy: HIGH tier allows compliance_lead/admin, not risk_officer.
    with pytest.raises(SignOffError, match="not an allowed sign-off role"):
        create_signoff(role="risk_officer", accepted_by="Jordan Lee", tier="HIGH")


def test_allowed_role_creates_signoff() -> None:
    so = create_signoff(role="compliance_lead", accepted_by="Dana Lee", tier="HIGH")
    assert so.accepted_by == "Dana Lee"
    assert so.role == "compliance_lead"
    assert so.accepted_at is not None


def test_lower_tier_allows_risk_officer() -> None:
    so = create_signoff(role="risk_officer", accepted_by="Sam Patel", tier="MODERATE")
    assert so.role == "risk_officer"


def test_accepted_at_is_immutable() -> None:
    so = create_signoff(
        role="compliance_lead",
        accepted_by="Dana Lee",
        tier="HIGH",
        accepted_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    with pytest.raises(Exception):  # frozen model → assignment raises
        so.accepted_at = datetime.now(tz=timezone.utc)  # type: ignore[misc]


def test_go_with_conditions_requires_signoff_to_finalize() -> None:
    assert requires_signoff("GO_WITH_CONDITIONS") is True
    with pytest.raises(SignOffError, match="without a named-human sign-off"):
        finalize_gate("GO_WITH_CONDITIONS", None)

    so = create_signoff(role="compliance_lead", accepted_by="Dana Lee", tier="HIGH")
    finalize_gate("GO_WITH_CONDITIONS", so)  # must not raise


def test_go_needs_no_signoff() -> None:
    assert requires_signoff("GO") is False
    finalize_gate("GO", None)  # must not raise


def test_signoff_model_rejects_blank_role() -> None:
    # The field validator's SignOffError is wrapped by pydantic into a
    # ValidationError (a ValueError subclass).
    with pytest.raises(ValueError):
        SignOff(
            role="  ",
            accepted_by="x",
            tier="HIGH",
            accepted_at=datetime.now(tz=timezone.utc),
        )
