"""STORY-331 — Configurable policy layer.

Policy must change without code changes. Tier rules, risk-band thresholds, the
gate aggregation threshold (High-FAIL ``N``) and the sign-off role→tier map all
live in config and are read by the tiering (STORY-303), scoring (STORY-310),
gate (STORY-326) and sign-off (STORY-327) stories.

Design
------
* The policy is a versioned, validated document. The active version string is
  stamped onto every emitted audit result so an audit is reproducible against
  the exact policy that produced it.
* Validation happens **at load** (fail fast): overlapping/gappy band ranges,
  unknown enum values, or a non-positive gate threshold are rejected before any
  audit logic runs.
* The source is overridable without a redeploy: set ``SARO_GRC_POLICY_PATH`` to
  a JSON file and it is read on demand. With no override the built-in default
  policy is used. Tests inject a policy directly via :func:`load_policy`.

Single-tenant for the MVP (per the story's out-of-scope note); a per-tenant
store and a config-editing UI are later work.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Risk-band and tier enums are intentionally aligned: ``internal_tier`` and a
# finding's risk band share the same four ordered levels (STORY-303 note).
RiskBand = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
EU_AI_ACT_CATEGORIES = ("UNACCEPTABLE", "HIGH", "LIMITED", "MINIMAL")
NIST_IMPACT_LEVELS = ("LOW", "MODERATE", "HIGH")

# The integer score domain is likelihood(1–5) × impact(1–5) ∈ [1, 25].
SCORE_MIN = 1
SCORE_MAX = 25


class PolicyError(ValueError):
    """Raised when a policy document fails validation at load time."""


class BandThreshold(BaseModel):
    """One inclusive risk-band range over the integer score domain [1, 25]."""

    band: RiskBand
    min: int = Field(ge=SCORE_MIN, le=SCORE_MAX)
    max: int = Field(ge=SCORE_MIN, le=SCORE_MAX)

    @model_validator(mode="after")
    def _min_le_max(self) -> "BandThreshold":
        if self.min > self.max:
            raise PolicyError(f"band {self.band}: min {self.min} > max {self.max}")
        return self


class TieringRule(BaseModel):
    """A single declarative, inspectable tiering rule.

    Rules are evaluated in list order; the first whose ``when`` clause matches a
    registry entry wins (see STORY-303's evaluator). Keeping the rule set
    declarative — rather than an opaque scoring black box — is a hard
    requirement so an auditor can follow exactly why a system was tiered.
    """

    when: dict[str, Any] = Field(
        description="field → expected value (or {'in': [...]} / {'contains': x})"
    )
    internal_tier: RiskBand
    eu_ai_act_category: str
    nist_impact_level: str
    rationale: str = Field(min_length=1)

    @field_validator("eu_ai_act_category")
    @classmethod
    def _eu_known(cls, v: str) -> str:
        if v not in EU_AI_ACT_CATEGORIES:
            raise PolicyError(f"unknown eu_ai_act_category: {v!r}")
        return v

    @field_validator("nist_impact_level")
    @classmethod
    def _nist_known(cls, v: str) -> str:
        if v not in NIST_IMPACT_LEVELS:
            raise PolicyError(f"unknown nist_impact_level: {v!r}")
        return v


class GRCPolicy(BaseModel):
    """The full, versioned GRC policy document."""

    version: str = Field(min_length=1)

    # STORY-310 — risk-band thresholds.
    band_thresholds: list[BandThreshold]

    # STORY-326 — number of High FAILs that forces NO_GO (exactly 1 → conditions).
    gate_high_fail_threshold: int = Field(ge=1)

    # STORY-303 — ordered declarative tiering rules + a catch-all default.
    tiering_rules: list[TieringRule]
    tiering_default: TieringRule

    # STORY-302 — required governance fields a registry entry must carry.
    required_registry_fields: list[str]

    # STORY-327 — sign-off: tier → roles permitted to accept residual risk.
    signoff_roles_by_tier: dict[str, list[str]]

    @field_validator("band_thresholds")
    @classmethod
    def _bands_cover_domain(cls, bands: list[BandThreshold]) -> list[BandThreshold]:
        """Reject overlapping ranges and gaps; require full [1,25] coverage."""
        if not bands:
            raise PolicyError("band_thresholds must not be empty")
        ordered = sorted(bands, key=lambda b: b.min)
        if ordered[0].min != SCORE_MIN:
            raise PolicyError(f"band coverage must start at {SCORE_MIN}")
        if ordered[-1].max != SCORE_MAX:
            raise PolicyError(f"band coverage must end at {SCORE_MAX}")
        prev = ordered[0]
        for nxt in ordered[1:]:
            if nxt.min <= prev.max:
                raise PolicyError(
                    f"overlapping band ranges: {prev.band}[{prev.min}-{prev.max}] "
                    f"and {nxt.band}[{nxt.min}-{nxt.max}]"
                )
            if nxt.min != prev.max + 1:
                raise PolicyError(
                    f"gap in band coverage between {prev.max} and {nxt.min}"
                )
            prev = nxt
        return bands

    @model_validator(mode="after")
    def _signoff_tiers_valid(self) -> "GRCPolicy":
        for tier in self.signoff_roles_by_tier:
            if tier not in ("LOW", "MODERATE", "HIGH", "CRITICAL"):
                raise PolicyError(f"signoff_roles_by_tier: unknown tier {tier!r}")
        return self

    # ── consumer helpers ──────────────────────────────────────────────────
    def band_for_score(self, score: int) -> RiskBand:
        """Map an integer score to its band (STORY-310 consumes this)."""
        if not (SCORE_MIN <= score <= SCORE_MAX):
            raise ValueError(f"score {score} outside [{SCORE_MIN}, {SCORE_MAX}]")
        for b in self.band_thresholds:
            if b.min <= score <= b.max:
                return b.band
        # Unreachable once _bands_cover_domain has run, but fail loud if not.
        raise PolicyError(f"no band covers score {score}")

    def signoff_roles_for_tier(self, tier: str) -> list[str]:
        """Roles permitted to accept residual risk at a tier (STORY-327)."""
        return self.signoff_roles_by_tier.get(tier, [])


# ── Built-in default policy ───────────────────────────────────────────────
# Defaults encode the decisions recorded in the GRC specs (band edges in
# STORY-310; N=2 in STORY-326 / OPEN-DEC-1). Override via SARO_GRC_POLICY_PATH.
_DEFAULT_POLICY: dict[str, Any] = {
    "version": "grc-policy-1.0.0",
    "band_thresholds": [
        {"band": "LOW", "min": 1, "max": 6},
        {"band": "MODERATE", "min": 7, "max": 12},
        {"band": "HIGH", "min": 13, "max": 19},
        {"band": "CRITICAL", "min": 20, "max": 25},
    ],
    "gate_high_fail_threshold": 2,
    "tiering_rules": [
        {
            "when": {"domain": {"in": ["healthcare", "medical", "clinical"]}},
            "internal_tier": "HIGH",
            "eu_ai_act_category": "HIGH",
            "nist_impact_level": "HIGH",
            "rationale": "Health/clinical decision support is an EU AI Act high-risk domain.",
        },
        {
            "when": {"makes_autonomous_decisions": True, "affects_individuals": True},
            "internal_tier": "HIGH",
            "eu_ai_act_category": "HIGH",
            "nist_impact_level": "HIGH",
            "rationale": "Autonomous decisions affecting individuals carry high impact.",
        },
        {
            "when": {"interacts_with_humans": True},
            "internal_tier": "MODERATE",
            "eu_ai_act_category": "LIMITED",
            "nist_impact_level": "MODERATE",
            "rationale": "Human-facing systems carry transparency obligations (limited risk).",
        },
    ],
    "tiering_default": {
        "when": {},
        "internal_tier": "LOW",
        "eu_ai_act_category": "MINIMAL",
        "nist_impact_level": "LOW",
        "rationale": "No high-risk indicators present; minimal-risk default.",
    },
    "required_registry_fields": [
        "name",
        "version",
        "owner",
        "purpose",
        "data_sources",
        "model_version",
        "lifecycle_stage",
        "deployment_status",
    ],
    "signoff_roles_by_tier": {
        "LOW": ["risk_officer", "compliance_lead", "admin"],
        "MODERATE": ["risk_officer", "compliance_lead", "admin"],
        "HIGH": ["compliance_lead", "admin"],
        "CRITICAL": ["compliance_lead", "admin"],
    },
}

_POLICY_PATH_ENV = "SARO_GRC_POLICY_PATH"


def _read_source() -> dict[str, Any]:
    """Read the raw policy document from the override path or the default."""
    path = os.environ.get(_POLICY_PATH_ENV)
    if path:
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise PolicyError(f"could not read GRC policy at {path}: {exc}") from exc
    return _DEFAULT_POLICY


def load_policy(source: dict[str, Any] | None = None) -> GRCPolicy:
    """Validate and return a :class:`GRCPolicy`.

    Pass ``source`` to validate an explicit document (used by tests and by the
    DB-backed config store). With no argument the override file or built-in
    default is used. Raises :class:`PolicyError` on any invalid document.
    """
    raw = source if source is not None else _read_source()
    try:
        return GRCPolicy.model_validate(raw)
    except PolicyError:
        raise
    except Exception as exc:  # pydantic ValidationError → uniform PolicyError
        raise PolicyError(str(exc)) from exc


@lru_cache(maxsize=1)
def _cached_policy() -> GRCPolicy:
    return load_policy()


def get_active_policy() -> GRCPolicy:
    """Return the process-wide active policy (cached).

    Changing ``SARO_GRC_POLICY_PATH`` and calling :func:`reload_active_policy`
    swaps the policy without a redeploy of the audit logic.
    """
    return _cached_policy()


def reload_active_policy() -> GRCPolicy:
    """Clear the cache and re-read the policy source. Returns the new policy."""
    _cached_policy.cache_clear()
    return _cached_policy()
