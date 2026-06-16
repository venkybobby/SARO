"""STORY-302 — Registry completeness enforcement.

Unknown metadata must never be read as a safe default. A registry entry missing
any required governance field is a governance gap, and a gap must be able to
block a deployment gate (STORY-326 consumes :func:`has_open_gaps`).

This is a pure function over a registry entry plus the config-driven required-
field list (STORY-331's ``required_registry_fields``); it touches no database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from grc.policy import get_active_policy
from grc.registry import RegistryEntryData

GAP_FLAG = "GOVERNANCE_GAP"


class GovernanceGap(BaseModel):
    """One missing required governance field on one registry entry."""

    flag: str = GAP_FLAG
    entry_id: str | None = None
    field: str
    message: str


def _is_missing(value: Any) -> bool:
    """A value is missing if it is None or an empty string/collection."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _as_mapping(entry: RegistryEntryData | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(entry, Mapping):
        return entry
    return entry.model_dump()


def _required_fields(required_fields: Iterable[str] | None) -> tuple[str, ...]:
    if required_fields is not None:
        return tuple(required_fields)
    return tuple(get_active_policy().required_registry_fields)


def check_completeness(
    entry: RegistryEntryData | Mapping[str, Any],
    required_fields: Iterable[str] | None = None,
) -> list[GovernanceGap]:
    """Return one :class:`GovernanceGap` per missing required field.

    A complete entry yields an empty list. ``required_fields`` defaults to the
    active policy's list so the requirement is config-driven (STORY-331).
    """
    data = _as_mapping(entry)
    entry_id = data.get("id")
    entry_id_str = str(entry_id) if entry_id is not None else None
    gaps: list[GovernanceGap] = []
    for field in _required_fields(required_fields):
        if _is_missing(data.get(field)):
            gaps.append(
                GovernanceGap(
                    entry_id=entry_id_str,
                    field=field,
                    message=f"Required governance field '{field}' is missing.",
                )
            )
    return gaps


def has_open_gaps(
    entry: RegistryEntryData | Mapping[str, Any],
    required_fields: Iterable[str] | None = None,
) -> bool:
    """True when the entry has ≥1 governance gap (consumed by STORY-326)."""
    return len(check_completeness(entry, required_fields)) > 0


def portfolio_gaps(
    entries: Iterable[RegistryEntryData | Mapping[str, Any]],
    required_fields: Iterable[str] | None = None,
) -> dict[str, list[GovernanceGap]]:
    """Aggregate gaps across the portfolio, keyed by entry id.

    Entries with no gaps are omitted. Entries without an id are grouped under
    the ``"<unknown>"`` key.
    """
    out: dict[str, list[GovernanceGap]] = {}
    for entry in entries:
        gaps = check_completeness(entry, required_fields)
        if gaps:
            key = gaps[0].entry_id or "<unknown>"
            out.setdefault(key, []).extend(gaps)
    return out
