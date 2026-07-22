"""STORY-377 — the completion bar is a PROPOSAL, and cannot enforce unsigned.

This is a human-gated story. The load-bearing test —
``test_proposed_bar_is_not_in_force`` — is the structural guarantee that a
validation bar SARO wrote for itself does not become active without an owner's
signature. If a future change accidentally marks it signed, this fails.
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
PROPOSAL = ROOT / "quality" / "validation" / "completion-bar.proposed.yaml"


def _proposal() -> dict:
    return yaml.safe_load(PROPOSAL.read_text(encoding="utf-8"))


# ── The gate: unsigned cannot enforce ───────────────────────────────────────


def test_proposed_bar_is_not_in_force():
    """AC-3: no self-certified bar. Until an owner signs, nothing enforces it."""
    assert bar.is_in_force() is False
    assert bar.active_thresholds() is None, (
        "an unsigned proposal must expose NO enforceable thresholds"
    )
    assert bar.status() == "PROPOSED_AWAITING_SIGNOFF"


def test_proposal_file_is_not_marked_signed():
    p = _proposal()
    assert p["status"] == "PROPOSED_AWAITING_SIGNOFF"
    assert p["signed_by"] is None
    assert p["chosen_profile"] is None, "the profile is the owner's choice, not preset"


def test_a_signed_bar_would_take_precedence_and_enforce(tmp_path, monkeypatch):
    """Prove the mechanism works: a SIGNED file DOES put thresholds in force.

    This does not sign the real bar — it points the loader at a temp signed file,
    so the enforcement path is exercised without self-certifying anything.
    """
    signed = tmp_path / "completion-bar.yaml"
    signed.write_text(
        yaml.safe_dump(
            {
                "status": "SIGNED",
                "chosen_profile": "A_recall_weighted",
                "profiles": {
                    "A_recall_weighted": {
                        "thresholds": {"RP-OBS-COMPLETE": {"T1": {"precision": 0.99, "recall": 0.99}}}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bar, "_SIGNED", signed)
    assert bar.is_in_force() is True
    thresholds = bar.active_thresholds()
    assert thresholds["RP-OBS-COMPLETE"]["T1"]["recall"] == 0.99


# ── AC-1: thresholds proposed with rationale, per tier ──────────────────────


def test_two_profiles_are_offered_not_one_preset_choice():
    """AC-3: present tradeoffs, do not decide. Two profiles = an owner choice."""
    profiles = _proposal()["profiles"]
    assert "A_recall_weighted" in profiles
    assert "B_balanced" in profiles


def test_thresholds_cover_both_packs_across_available_tiers():
    profiles = _proposal()["profiles"]
    for profile in profiles.values():
        th = profile["thresholds"]
        for pack in ("RP-OBS-COMPLETE", "RP-TOOL-SCOPE"):
            assert pack in th
            for tier in ("T1", "T2", "T3"):
                assert th[pack][tier] is not None


def test_t4_pilot_thresholds_are_blank_because_no_data_exists():
    """Proposing a number for data that does not exist is the failure to avoid."""
    for profile in _proposal()["profiles"].values():
        for pack in profile["thresholds"].values():
            assert pack["T4"] is None, "T4 must stay unset until pilot data exists"


def test_strategy_doc_states_the_fp_fn_tradeoff():
    doc = STRATEGY.read_text(encoding="utf-8").lower()
    assert "false positive" in doc and "false negative" in doc
    assert "recall" in doc and "precision" in doc


def test_strategy_doc_carries_a_human_signoff_gate():
    doc = STRATEGY.read_text(encoding="utf-8")
    assert "[HUMAN — OPEN]" in doc
    assert "sign-off" in doc.lower() or "signed" in doc.lower()
    assert "self-certify" in doc.lower()


def test_strategy_records_the_numbering_correction():
    """v1.1 never existed — say so, so a future plan does not re-assume it."""
    import re

    doc = re.sub(r"\s+", " ", STRATEGY.read_text(encoding="utf-8")).lower()
    assert "v1.0" in doc
    assert "no such document ever existed" in doc, "the numbering correction must be explicit"


# ── AC-2: measurement protocol ──────────────────────────────────────────────


def test_protocol_is_per_tier_not_a_blended_average():
    """Averaging across tiers hides poor real-world behaviour behind good synthetic."""
    doc = STRATEGY.read_text(encoding="utf-8").lower()
    assert "per-tier" in doc
    assert "not a blended average" in doc or "averaging across tiers" in doc


def test_protocol_states_exclusions_cadence_and_triggers():
    doc = STRATEGY.read_text(encoding="utf-8").lower()
    assert "exclusion" in doc
    assert "cadence" in doc
    assert "re-validation trigger" in doc or "re-validation" in doc


# ── AC-4 dependency: downstream stays inert while unsigned ──────────────────


def test_376_validation_stage_still_defers_to_this_bar():
    import services.rule_pack_lifecycle as lifecycle

    assert lifecycle.BAR_PENDING == "bar_pending:STORY-377"
    # And the bar it is waiting on is genuinely not in force.
    assert bar.is_in_force() is False
