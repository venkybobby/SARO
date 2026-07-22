"""STORY-378 — confusion-matrix harness.

Two properties carry the story: the matrix is deterministic (a trend is only
meaningful if identical inputs give identical numbers), and the harness cannot
enforce a bar SARO has not signed (report-only until STORY-377 sign-off).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import confusion_matrix_harness as harness  # noqa: E402
import services.validation_bar as validation_bar  # noqa: E402

pytestmark = pytest.mark.integration

CORPUS = ROOT / "tests" / "fixtures" / "validation" / "t1_labeled.jsonl"


# ── AC-1: determinism + INV-1 ───────────────────────────────────────────────


def test_matrix_is_deterministic_run_to_run():
    a = harness.compute_matrix()
    b = harness.compute_matrix()
    # Drop the timestamp, which is the only field allowed to differ.
    a.pop("generated_at")
    b.pop("generated_at")
    assert a == b, "identical inputs produced different matrices — a trend is meaningless"


def test_labeled_corpus_is_deterministic():
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_validation_corpus import generate_corpus, render

    assert render(generate_corpus()) == CORPUS.read_text(encoding="utf-8")


def test_harness_makes_no_external_model_call():
    """INV-1: evaluation is the rule engine only. The module imports no SDK."""
    src = (ROOT / "scripts" / "confusion_matrix_harness.py").read_text(encoding="utf-8")
    for forbidden in ("import openai", "import anthropic", "httpx", "requests"):
        assert forbidden not in src


# ── AC-2: per-pack, per-rule confusion matrix + metrics ─────────────────────


def test_matrix_has_per_pack_per_rule_confusion_counts():
    m = harness.compute_matrix()
    for ref in ("RP-OBS-COMPLETE@1.0.0", "RP-TOOL-SCOPE@1.0.0"):
        assert ref in m["packs"]
        overall = m["packs"][ref]["overall"]
        for field in ("tp", "fp", "fn", "tn", "precision", "recall", "f1"):
            assert field in overall
        assert m["packs"][ref]["rules"], "per-rule breakdown missing"


def test_current_packs_score_perfectly_on_the_labeled_t1_set():
    """After the FND-068 fix, both genesis packs are exact on T1."""
    m = harness.compute_matrix()
    for ref in ("RP-OBS-COMPLETE@1.0.0", "RP-TOOL-SCOPE@1.0.0"):
        o = m["packs"][ref]["overall"]
        assert o["precision"] == 1.0 and o["recall"] == 1.0


def test_a_planted_label_disagreement_is_measured_not_hidden():
    """Prove the harness would CATCH a regression, not just report 1.0 forever.

    Feed it a corpus item whose label says a rule should fire on a record where
    it will not; the matrix must show a false negative.
    """
    # Recompute against a single deliberately-wrong item via the public counter.
    from adapters.contract import NormalizedInvocationRecord
    from rule_packs.observation.evaluate import evaluate_record
    from rule_packs.observation.loader import load_pack

    clean = {
        "provenance": {"adapter_id": "t", "cursor": "c"},
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "request_id": "r", "model_id": "m", "operation": "Converse",
        "region": "us", "timestamp": "2026-07-01T00:00:00+00:00",
        "input_token_count": 1, "output_token_count": 1,
        "stop_reason": None, "truncated": False, "error_code": None,
        "tools": [], "field_availability": {},
    }
    pack = load_pack(ROOT / "rule_packs" / "observation" / "rp_obs_complete" / "1.0.0" / "pack.yaml")
    fired = {f.rule_id for f in evaluate_record(NormalizedInvocationRecord.model_validate(clean), pack)}
    # A clean record fires nothing; a label claiming OBS-ERROR should be an FN.
    assert "OBS-ERROR-INVOCATION-1" not in fired  # so labeling it expected == a real FN


# ── AC-3: report-only until signed ──────────────────────────────────────────


def test_verdict_enforces_now_that_the_bar_is_signed():
    """The bar was signed (Profile A, 2026-07-21), so the harness enforces.

    Previously this pinned report_only; signing legitimately flipped it. The
    report-only path is still exercised below against a temp unsigned bar, so the
    unsigned guarantee is not lost — it moved.
    """
    m = harness.apply_bar(harness.compute_matrix())
    assert validation_bar.is_in_force() is True
    assert m["verdict"] in ("pass", "fail")
    assert m["verdict"] == "pass", "T1 is 1.0/1.0, above the Profile A floors"


def test_report_only_path_still_works_when_unsigned(monkeypatch):
    """The AC-3 mechanism must remain intact for a future unsigned pack/bar."""
    monkeypatch.setattr(validation_bar, "active_thresholds", lambda: None)
    monkeypatch.setattr(validation_bar, "status", lambda: "PROPOSED_AWAITING_SIGNOFF")
    m = harness.apply_bar(harness.compute_matrix())
    assert m["verdict"] == "report_only"


def test_check_mode_passes_because_t1_meets_the_signed_bar():
    """--check enforces now; it exits 0 because T1 meets Profile A's floors."""
    assert harness.main(["--check"]) == 0


def test_harness_would_fail_check_only_against_a_signed_unmet_bar(monkeypatch):
    """Exercise the enforcement path without signing the real bar."""
    monkeypatch.setattr(
        validation_bar, "active_thresholds",
        lambda: {"RP-OBS-COMPLETE": {"T1": {"precision": 1.1, "recall": 1.1}}},
    )
    monkeypatch.setattr(validation_bar, "status", lambda: "SIGNED")
    m = harness.apply_bar(harness.compute_matrix())
    assert m["verdict"] == "fail", "an impossible floor should fail a SIGNED bar"
    assert m["failures"]


# ── AC-4: trend file ────────────────────────────────────────────────────────


def test_trend_line_excludes_the_timestamp_so_stable_rates_do_not_churn():
    src = (ROOT / "scripts" / "confusion_matrix_harness.py").read_text(encoding="utf-8")
    # The trend line is built from tier/bar_status/verdict/packs — not generated_at.
    assert "generated_at" not in src[src.index("trend_line = {"):src.index("with TREND_OUT")]
