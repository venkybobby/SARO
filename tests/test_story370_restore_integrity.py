"""STORY-370 — DR backup inventory and post-restore integrity verification.

The test that carries the story is
``test_truncated_chain_is_caught_even_though_it_verifies_internally``: it
reproduces the exact failure the existing eight chain verifiers cannot see, and
proves this tool catches it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from verify_restore_integrity import (  # noqa: E402
    AHEAD,
    DATA_LOSS,
    MATCH,
    MISSING,
    TAMPER,
    ChainReading,
    build_manifest,
    compare,
)

pytestmark = pytest.mark.unit

DR_DOC = ROOT / "docs" / "ops" / "dr-backup.md"
ALERTS = ROOT / "docs" / "ops" / "alerts.md"


def _reading(count: int, tip: str, *, valid: bool = True, scope: str = "tenant-a") -> ChainReading:
    return ChainReading(
        family="self_audit",
        scope=scope,
        record_count=count,
        tip_hash=tip,
        internally_valid=valid,
    )


def _manifest(*readings: ChainReading) -> dict:
    return build_manifest(list(readings), label="test")


# ── The core distinction ────────────────────────────────────────────────────


def test_faithful_restore_matches():
    ref = _manifest(_reading(100, "aaa"))
    report = compare(ref, [_reading(100, "aaa")])
    assert report["overall"] == MATCH
    assert report["passed"] is True
    assert report["total_records_lost"] == 0


def test_truncated_chain_is_caught_even_though_it_verifies_internally():
    """The failure mode this tool exists for.

    The restored chain passes its own hash verification (`internally_valid=True`,
    exactly what all eight existing verifiers would report) but is missing 400
    records. Only comparison against a pre-incident reference reveals it.
    """
    ref = _manifest(_reading(1000, "tip-1000"))
    restored = _reading(600, "tip-600", valid=True)  # self-consistent, shorter

    report = compare(ref, [restored])

    assert report["overall"] == DATA_LOSS
    assert report["passed"] is False
    assert report["total_records_lost"] == 400
    assert "self-consistent but incomplete" in report["chains"][0]["detail"]


def test_same_count_different_tip_is_tamper_not_loss():
    """Content changed without changing the record count — a different fault."""
    ref = _manifest(_reading(50, "original-tip"))
    report = compare(ref, [_reading(50, "different-tip")])
    assert report["overall"] == TAMPER
    assert report["passed"] is False
    assert report["total_records_lost"] == 0


def test_internally_invalid_chain_is_tamper():
    ref = _manifest(_reading(50, "tip"))
    report = compare(ref, [_reading(50, "tip", valid=False)])
    assert report["overall"] == TAMPER
    assert "fails its own hash verification" in report["chains"][0]["detail"]


def test_extra_records_are_flagged_as_ahead_not_silently_passed():
    """More records than the reference means traffic resumed before verification."""
    ref = _manifest(_reading(100, "tip-100"))
    report = compare(ref, [_reading(140, "tip-140")])
    assert report["overall"] == AHEAD
    assert report["passed"] is True, "AHEAD is procedural, not evidence loss"
    assert "before resuming traffic" in report["chains"][0]["detail"]


def test_entirely_absent_chain_family_is_the_most_severe_verdict():
    """Nothing fails when there is nothing there to fail — so this is explicit."""
    ref = _manifest(_reading(300, "tip", scope="tenant-a"), _reading(10, "t2", scope="tenant-b"))
    report = compare(ref, [_reading(300, "tip", scope="tenant-a")])
    verdicts = {c["key"]: c["verdict"] for c in report["chains"]}
    assert verdicts["self_audit:tenant-b"] == MISSING
    assert report["passed"] is False
    assert report["total_records_lost"] == 10


def test_new_chain_absent_from_reference_does_not_fail_the_restore():
    ref = _manifest(_reading(5, "tip", scope="tenant-a"))
    report = compare(ref, [_reading(5, "tip", scope="tenant-a"), _reading(2, "n", scope="new")])
    assert report["overall"] == AHEAD
    assert report["passed"] is True


def test_worst_verdict_wins_across_chains():
    ref = _manifest(
        _reading(10, "a", scope="t1"), _reading(10, "b", scope="t2"), _reading(10, "c", scope="t3")
    )
    report = compare(
        ref,
        [
            _reading(10, "a", scope="t1"),   # MATCH
            _reading(12, "b2", scope="t2"),  # AHEAD
            _reading(4, "c2", scope="t3"),   # DATA_LOSS
        ],
    )
    assert report["overall"] == DATA_LOSS
    assert report["passed"] is False


# ── Manifest handling ───────────────────────────────────────────────────────


def test_manifest_round_trips_through_json():
    ref = json.loads(json.dumps(_manifest(_reading(7, "tip"))))
    assert compare(ref, [_reading(7, "tip")])["overall"] == MATCH


def test_manifest_records_when_it_was_captured():
    """A reference of unknown age cannot be interpreted."""
    manifest = _manifest(_reading(1, "x"))
    assert manifest["captured_at"]
    report = compare(manifest, [_reading(1, "x")])
    assert report["reference_captured_at"] == manifest["captured_at"]


def test_foreign_schema_is_rejected_rather_than_misread():
    with pytest.raises(ValueError, match="schema"):
        compare({"schema": "something-else", "chains": {}}, [_reading(1, "x")])


def test_empty_reference_with_current_data_does_not_claim_a_match():
    report = compare(build_manifest([]), [_reading(5, "tip")])
    assert report["overall"] == AHEAD


# ── AC-1 / AC-5: the documents ──────────────────────────────────────────────


def test_dr_doc_exists_with_backup_inventory():
    doc = DR_DOC.read_text(encoding="utf-8")
    assert "Supabase" in doc
    assert "PITR" in doc or "point-in-time" in doc.lower()
    assert "rule-pack" in doc.lower()


def test_dr_doc_marks_provider_settings_as_to_confirm_not_asserted():
    """Repo cannot see the Supabase console; claiming settings would be FM-1."""
    doc = DR_DOC.read_text(encoding="utf-8")
    assert "CONFIRM" in doc.upper()
    assert "[ ]" in doc, "expected an unchecked confirmation checklist"


def test_rto_rpo_are_blank_until_the_rehearsal_measures_them():
    """Writing plausible numbers before rehearsing is the FM-1 failure."""
    doc = DR_DOC.read_text(encoding="utf-8")
    assert "[HUMAN — OPEN]" in doc
    assert "not yet measured" in doc.lower()


def test_dr_doc_requires_the_manifest_to_be_stored_off_platform():
    """A manifest living only in the database it describes proves nothing."""
    doc = DR_DOC.read_text(encoding="utf-8")
    assert "off-platform" in doc.lower()


def test_dr_doc_forbids_rehearsing_against_production():
    doc = DR_DOC.read_text(encoding="utf-8")
    assert "never" in doc.lower() and "production" in doc.lower()


def test_a7_alert_is_wired_rather_than_a_placeholder():
    alerts = ALERTS.read_text(encoding="utf-8")
    a7 = alerts[alerts.index("### A7"):]
    a7 = a7[: a7.index("---")] if "---" in a7 else a7
    assert "verify_restore_integrity" in a7, "A7 should now name the verification script"
    assert "placeholder" not in a7.lower(), "A7 is still a placeholder"
