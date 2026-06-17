"""STORY-302 — Registry completeness enforcement tests.

AC coverage:
- An entry missing any required field produces one GOVERNANCE_GAP per missing field.
- Gaps are listable per system and across the portfolio.
- has_open_gaps == True for a system with >=1 open gap.
- Resolving the missing field clears the corresponding gap.
"""

from __future__ import annotations

import uuid

import pytest

from grc.completeness import (
    GAP_FLAG,
    check_completeness,
    has_open_gaps,
    portfolio_gaps,
)
from grc.policy import get_active_policy
from grc.registry import RegistryEntryData

pytestmark = pytest.mark.unit

REQUIRED = tuple(get_active_policy().required_registry_fields)


def _complete(**over) -> RegistryEntryData:
    base: dict = dict(
        id=uuid.uuid4(),
        name="Claims Triage",
        version="1.0.0",
        owner="Dr. Alice Chen",
        purpose="Triage claims",
        data_sources=["claims_db"],
        model_version="claude-sonnet-4",
        lifecycle_stage="production",
        deployment_status="active",
    )
    base.update(over)
    return RegistryEntryData(**base)


def test_complete_entry_has_no_gaps() -> None:
    assert check_completeness(_complete()) == []
    assert has_open_gaps(_complete()) is False


def test_each_missing_field_produces_exactly_one_gap() -> None:
    for field in REQUIRED:
        entry = _complete(**{field: None})
        gaps = check_completeness(entry)
        assert len(gaps) == 1, f"{field} should yield exactly one gap"
        assert gaps[0].field == field
        assert gaps[0].flag == GAP_FLAG


def test_empty_string_and_empty_list_count_as_missing() -> None:
    assert any(g.field == "owner" for g in check_completeness(_complete(owner="   ")))
    assert any(
        g.field == "data_sources"
        for g in check_completeness(_complete(data_sources=[]))
    )


def test_multiple_missing_fields_produce_multiple_gaps() -> None:
    entry = _complete(owner=None, purpose=None)
    fields = {g.field for g in check_completeness(entry)}
    assert fields == {"owner", "purpose"}


def test_has_open_gaps_true_with_one_gap() -> None:
    assert has_open_gaps(_complete(owner=None)) is True


def test_resolving_field_clears_gap() -> None:
    entry = _complete(owner=None)
    assert has_open_gaps(entry) is True
    entry.owner = "Dr. Alice Chen"
    assert check_completeness(entry) == []


def test_portfolio_gaps_aggregates_only_incomplete() -> None:
    good = _complete()
    bad = _complete(owner=None)
    agg = portfolio_gaps([good, bad])
    assert str(good.id) not in agg
    assert str(bad.id) in agg
    assert agg[str(bad.id)][0].field == "owner"


def test_required_fields_are_config_driven() -> None:
    # Overriding the required-field list changes what counts as a gap.
    entry = _complete(owner=None)
    assert check_completeness(entry, required_fields=["name"]) == []
    assert len(check_completeness(entry, required_fields=["owner"])) == 1
