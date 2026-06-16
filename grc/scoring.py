"""STORY-310 — Risk scoring & disposition.

Every finding needs an unambiguous severity and outcome:

    score = likelihood(1–5) × impact(1–5)   →  band (from config)  →  one disposition

Band thresholds are read from config (STORY-331), never hard-coded. Disposition
values come from the JSON contract enum (STORY-328) so producers and the contract
never drift. ``CONDITIONAL`` / ``FAIL`` must carry a non-empty remediation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from grc.contract import DISPOSITIONS
from grc.policy import GRCPolicy, get_active_policy

# Disposition constants (sourced from the contract enum, not redefined).
PASS = "PASS"
CONDITIONAL = "CONDITIONAL"
FAIL = "FAIL"
EVIDENCE_GAP = "EVIDENCE_GAP"
OUT_OF_SCOPE = "OUT_OF_SCOPE"

# Dispositions that must always carry a remediation.
_REMEDIATION_REQUIRED = frozenset({CONDITIONAL, FAIL})

_SCALE_MIN, _SCALE_MAX = 1, 5


class ScoringError(ValueError):
    """Raised on invalid scoring inputs or a disposition-rule violation."""


class RiskScore(BaseModel):
    likelihood: int = Field(ge=_SCALE_MIN, le=_SCALE_MAX)
    impact: int = Field(ge=_SCALE_MIN, le=_SCALE_MAX)
    score: int
    band: str


def compute_score(likelihood: int, impact: int) -> int:
    """Return likelihood × impact, validating both are on the 1–5 scale."""
    for name, val in (("likelihood", likelihood), ("impact", impact)):
        if not isinstance(val, int) or not (_SCALE_MIN <= val <= _SCALE_MAX):
            raise ScoringError(f"{name} must be an int in [{_SCALE_MIN}, {_SCALE_MAX}]")
    return likelihood * impact


def band_for(score: int, policy: GRCPolicy | None = None) -> str:
    """Map a score to its band using the config thresholds (STORY-331)."""
    pol = policy or get_active_policy()
    return pol.band_for_score(score)


def score_risk(
    likelihood: int, impact: int, policy: GRCPolicy | None = None
) -> RiskScore:
    """Compute the full {likelihood, impact, score, band} risk object."""
    score = compute_score(likelihood, impact)
    return RiskScore(
        likelihood=likelihood,
        impact=impact,
        score=score,
        band=band_for(score, policy),
    )


def validate_disposition(disposition: str, remediation: str | None) -> None:
    """Enforce the disposition rules. Raises :class:`ScoringError` on violation.

    * disposition must be exactly one of the contract enum values;
    * ``CONDITIONAL`` / ``FAIL`` require a non-empty remediation.
    """
    if disposition not in DISPOSITIONS:
        raise ScoringError(f"disposition {disposition!r} not in {DISPOSITIONS}")
    if disposition in _REMEDIATION_REQUIRED and not (
        remediation and remediation.strip()
    ):
        raise ScoringError(f"{disposition} requires a non-empty remediation")
