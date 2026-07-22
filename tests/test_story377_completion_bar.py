"""STORY-377 — the completion bar, SIGNED (Profile A, 2026-07-21).

The owner signed Profile A (recall-weighted) for T1–T3 with binding conditions.
These tests pin the SIGNED state and — load-bearing — the conditions that keep a
recall-weighted bar honest: a per-pack precision floor must accompany the recall
targets, and T4 must stay blank until pilot data exists.

History: this suite previously pinned the UNSIGNED state (no self-certified bar).
That guarantee did its job through the whole build; signing is the owner's
decision legitimately changing the state, so the assertions moved to the signed
state rather than being dropped. The unsigned mechanism is still exercised by
`test_unsigned_bar_would_not_enforce` against a temp file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import services.validation_bar as bar  # noqa: E402

pytestmark = pytest.mark.unit

STRATEGY = ROOT / "docs" / "validation" / "validation-strategy-v1.0.md"
SIGNED_BAR = ROOT / "quality" / "validation" / "completion-bar.yaml"


def _bar() -> dict:
    return yaml.safe_load(SIGNED_BAR.read_text(encoding="utf-8"))


# ── Signed state ────────────────────────────────────────────────────────────


def test_bar_is_signed_and_in_force():
    assert bar.status() == "SIGNED"
    assert bar.is_in_force() is True
    assert bar.active_thresholds() is not None


def test_chosen_profile_is_a_recall_weighted():
    b = _bar()
    assert b["chosen_profile"] == "A_recall_weighted"
    assert b["signed_by"], "a signed bar must name who signed it"
    assert b["signed_date"] == "2026-07-21"


def test_active_thresholds_are_profile_a():
    th = bar.active_thresholds()
    # recall-weighted: recall >= precision at the messier tiers
    assert th["RP-OBS-COMPLETE"]["T2"]["recall"] == 0.95
    assert th["RP-OBS-COMPLETE"]["T2"]["precision"] == 0.90


def test_unsigned_bar_would_not_enforce(tmp_path, monkeypatch):
    """The mechanism still fails closed: point the loader at an unsigned file."""
    proposed = tmp_path / "completion-bar.proposed.yaml"
    proposed.write_text(
        yaml.safe_dump({"status": "PROPOSED_AWAITING_SIGNOFF", "profiles": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bar, "_SIGNED", tmp_path / "nonexistent.yaml")
    monkeypatch.setattr(bar, "_PROPOSED", proposed)
    assert bar.is_in_force() is False
    assert bar.active_thresholds() is None


# ── Condition 1: precision floor, not recall-only (the trust guard) ─────────


def test_profile_a_carries_a_precision_floor_for_every_pack_and_tier():
    """The signed condition: a recall-weighted bar WITHOUT a precision floor is
    how repeated false positives erode trust. This fails if any measured tier
    becomes recall-only."""
    th = _bar()["profiles"]["A_recall_weighted"]["thresholds"]
    for pack in ("RP-OBS-COMPLETE", "RP-TOOL-SCOPE"):
        for tier in ("T1", "T2", "T3"):
            cell = th[pack][tier]
            assert cell is not None
            assert "precision" in cell and cell["precision"] is not None, (
                f"{pack} {tier} has no precision floor — recall-only violates the sign-off condition"
            )
            assert "recall" in cell and cell["recall"] is not None


def test_precision_floor_condition_is_recorded_in_the_bar():
    assert _bar()["conditions"]["precision_floor_required"] is True


def test_severity_is_the_recorded_reviewer_sort_key():
    """The pressure valve for a recall-weighted tool — must be a real finding field."""
    from rule_packs.observation.evaluate import Finding

    assert _bar()["conditions"]["severity_sort_key"] == "severity"
    assert "severity" in Finding.__dataclass_fields__


# ── Condition 3: T4 blank and NOT backfilled ────────────────────────────────


def test_t4_thresholds_are_null_and_backfill_is_prohibited():
    """Pilot thresholds are set jointly with SummitCare — not here, not by a
    future session."""
    th = _bar()["profiles"]["A_recall_weighted"]["thresholds"]
    for pack in ("RP-OBS-COMPLETE", "RP-TOOL-SCOPE"):
        assert th[pack]["T4"] is None, "T4 must stay blank until pilot-labeled data exists"
    assert _bar()["conditions"]["t4_backfill_prohibited"] is True


# ── Condition 4: profile revisited at T4 ────────────────────────────────────


def test_profile_choice_is_revisitable_at_t4():
    assert _bar()["conditions"]["revisit_profile_at_tier"] == "T4"
    doc = STRATEGY.read_text(encoding="utf-8")
    assert "revisited at T4" in doc or "revisit" in doc.lower()


def test_thresholds_are_recorded_as_provisional():
    assert _bar()["conditions"]["thresholds_provisional_until_real_data"] is True


# ── AC-1: strategy doc still carries the tradeoff + both profiles remain ─────


def test_both_profiles_remain_documented_for_the_t4_revisit():
    """B stays available: the A-vs-B choice reopens when T4 data lands."""
    profiles = _bar()["profiles"]
    assert "A_recall_weighted" in profiles and "B_balanced" in profiles


def test_strategy_doc_states_the_fp_fn_tradeoff():
    doc = STRATEGY.read_text(encoding="utf-8").lower()
    assert "false positive" in doc and "false negative" in doc
    assert "recall" in doc and "precision" in doc


def test_strategy_records_the_numbering_correction():
    import re

    doc = re.sub(r"\s+", " ", STRATEGY.read_text(encoding="utf-8")).lower()
    assert "v1.0" in doc
    assert "no such document ever existed" in doc


def test_strategy_doc_records_the_signature_and_conditions():
    doc = STRATEGY.read_text(encoding="utf-8")
    assert "SIGNED" in doc
    assert "Profile A" in doc
    assert "Precision floor" in doc or "precision floor" in doc


# ── AC-2: measurement protocol ──────────────────────────────────────────────


def test_protocol_is_per_tier_not_a_blended_average():
    doc = STRATEGY.read_text(encoding="utf-8").lower()
    assert "per-tier" in doc
    assert "not a blended average" in doc or "averaging across tiers" in doc


def test_protocol_states_exclusions_cadence_and_triggers():
    doc = STRATEGY.read_text(encoding="utf-8").lower()
    assert "exclusion" in doc
    assert "cadence" in doc
    assert "re-validation" in doc


# ── Downstream now enforces ─────────────────────────────────────────────────


def test_harness_now_enforces_because_the_bar_is_signed():
    assert bar.is_in_force() is True
    assert bar.active_thresholds() is not None
