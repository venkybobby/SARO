"""STORY-303 — Risk tiering engine.

Governance effort must scale with risk. Each registry entry is classified into
an internal tier, an EU AI Act category and a NIST impact level. The classifier
is **config-driven** (STORY-331's ``tiering_rules`` + ``tiering_default``) and
deliberately boring: a declarative, ordered rule set evaluated top-to-bottom,
first match wins — no opaque scoring black box an auditor cannot follow.

This module imports no DB and no :mod:`grc.registry` symbols (it accepts any
mapping / pydantic model / ORM row), so the registry can import *it* without a
cycle and auto-tier entries on create/update.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from grc.policy import GRCPolicy, TieringRule, get_active_policy

# Tiering inputs read from an entry. Kept explicit so re-tiering can detect when
# a *relevant* metadata change occurred (vs. a cosmetic one).
TIERING_INPUT_FIELDS = (
    "domain",
    "interacts_with_humans",
    "makes_autonomous_decisions",
    "affects_individuals",
    "purpose",
    "deployment_status",
)


class TieringResult(BaseModel):
    internal_tier: str
    eu_ai_act_category: str
    nist_impact_level: str
    rationale: str


def _as_mapping(entry: Any) -> Mapping[str, Any]:
    if isinstance(entry, Mapping):
        return entry
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    return {f: getattr(entry, f, None) for f in TIERING_INPUT_FIELDS}


def _condition_matches(value: Any, cond: Any) -> bool:
    """Evaluate one ``when`` condition against an entry field value."""
    if isinstance(cond, Mapping):
        if "in" in cond:
            return value in cond["in"]
        if "contains" in cond:
            try:
                return cond["contains"] in (value or [])
            except TypeError:
                return False
        if "not" in cond:
            return value != cond["not"]
        # Unknown operator → never matches (fail closed).
        return False
    return value == cond


def _rule_matches(rule: TieringRule, data: Mapping[str, Any]) -> bool:
    """A rule matches when *every* condition in its ``when`` clause holds.

    An empty ``when`` (the default rule) always matches.
    """
    for field, cond in rule.when.items():
        if not _condition_matches(data.get(field), cond):
            return False
    return True


def classify(entry: Any, policy: GRCPolicy | None = None) -> TieringResult:
    """Classify an entry into {internal_tier, eu_ai_act_category, nist_impact_level}.

    Rules are evaluated in order; the first match wins, else the configured
    default applies. Returns the matched rule's rationale for auditability.
    """
    pol = policy or get_active_policy()
    data = _as_mapping(entry)
    for rule in pol.tiering_rules:
        if _rule_matches(rule, data):
            return _to_result(rule)
    return _to_result(pol.tiering_default)


def _to_result(rule: TieringRule) -> TieringResult:
    return TieringResult(
        internal_tier=rule.internal_tier,
        eu_ai_act_category=rule.eu_ai_act_category,
        nist_impact_level=rule.nist_impact_level,
        rationale=rule.rationale,
    )


def tiering_inputs(entry: Any) -> dict[str, Any]:
    """Extract just the tiering-input fields from an entry (change detection)."""
    data = _as_mapping(entry)
    return {f: data.get(f) for f in TIERING_INPUT_FIELDS}


def apply_tiering(entry: Any, policy: GRCPolicy | None = None) -> TieringResult:
    """Classify and write the result onto a mutable ORM/attr entry.

    Sets ``internal_tier``, ``eu_ai_act_category``, ``nist_impact_level``,
    ``tiering_rationale`` and a ``tiered_at`` timestamp so the (re-)tiering is
    logged with its rationale (AC). Returns the result.
    """
    result = classify(entry, policy)
    entry.internal_tier = result.internal_tier
    entry.eu_ai_act_category = result.eu_ai_act_category
    entry.nist_impact_level = result.nist_impact_level
    entry.tiering_rationale = result.rationale
    entry.tiered_at = datetime.now(tz=timezone.utc)
    return result
