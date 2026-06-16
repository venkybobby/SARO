"""STORY-327 — Named-human residual-risk sign-off.

Accountability is non-delegable. Accepting residual risk (a ``GO_WITH_CONDITIONS``)
requires a named human in a role permitted for the system's tier — the system
records who, in what role, and when. A ``GO_WITH_CONDITIONS`` cannot be finalized
without a completed sign-off.

The role → tier map (org RACI) is config-driven (STORY-331's
``signoff_roles_by_tier``). ``accepted_at`` is immutable once set (the model is
frozen).
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, field_validator

from grc.gate import GO_WITH_CONDITIONS
from grc.policy import GRCPolicy, get_active_policy


class SignOffError(ValueError):
    """Raised when a sign-off is missing, malformed, or has a disallowed role."""


class SignOff(BaseModel):
    """An immutable residual-risk acceptance record."""

    role: str
    accepted_by: str
    tier: str
    accepted_at: datetime

    # Frozen → every field, including accepted_at, is immutable once set.
    model_config = {"frozen": True}

    @field_validator("accepted_by", "role")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise SignOffError("must be a non-empty value")
        return v.strip()


def create_signoff(
    *,
    role: str,
    accepted_by: str,
    tier: str,
    accepted_at: datetime | None = None,
    policy: GRCPolicy | None = None,
) -> SignOff:
    """Validate and build a sign-off record.

    Rejects a missing/blank ``accepted_by`` and a ``role`` not permitted for the
    tier by config. ``accepted_at`` defaults to now and is immutable thereafter.
    """
    pol = policy or get_active_policy()
    if not accepted_by or not accepted_by.strip():
        raise SignOffError("residual-risk acceptance requires a named accepted_by")

    allowed = pol.signoff_roles_for_tier(tier)
    if role not in allowed:
        raise SignOffError(
            f"role {role!r} is not an allowed sign-off role for tier {tier!r} "
            f"(allowed: {allowed})"
        )

    return SignOff(
        role=role,
        accepted_by=accepted_by.strip(),
        tier=tier,
        accepted_at=accepted_at or datetime.now(tz=timezone.utc),
    )


def finalize_gate(gate_recommendation: str, signoff: SignOff | None) -> None:
    """Enforce that a ``GO_WITH_CONDITIONS`` is not finalized without a sign-off.

    Raises :class:`SignOffError` if a residual-risk acceptance is required but
    absent. ``GO`` needs no sign-off; this is a no-op for it.
    """
    if gate_recommendation == GO_WITH_CONDITIONS and signoff is None:
        raise SignOffError(
            "GO_WITH_CONDITIONS cannot be finalized without a named-human sign-off"
        )


def requires_signoff(gate_recommendation: str) -> bool:
    """True when the recommendation needs a residual-risk sign-off to finalize."""
    return gate_recommendation == GO_WITH_CONDITIONS
