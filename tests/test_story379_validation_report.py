"""STORY-379 — buyer-facing validation report.

This is a document a buyer takes to their own risk review, so the tests are
about it not overclaiming: numbers come from the artifact (not hand-typed), the
Limitations section is honest about how narrow the results are, and prohibited
claim language cannot reach it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_validation_report as report  # noqa: E402

pytestmark = pytest.mark.integration

MATRIX = ROOT / "quality" / "validation" / "confusion-latest.json"
MD = ROOT / "docs" / "validation" / "validation-report.md"
PDF = ROOT / "docs" / "validation" / "validation-report.pdf"


# ── AC-1: generated from the artifact, not hand-typed ───────────────────────


def test_report_is_current_with_the_artifact():
    assert MD.exists()
    assert MD.read_text(encoding="utf-8") == report.build_markdown()


def test_numbers_come_from_the_matrix_not_the_source(monkeypatch, tmp_path):
    """Change the artifact → the report changes. That is the anti-drift control."""
    fake = tmp_path / "matrix.json"
    fake.write_text(
        json.dumps(
            {
                "tier": "T1",
                "corpus_records": 3,
                "packs": {
                    "RP-OBS-COMPLETE@1.0.0": {
                        "overall": {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1, "fp": 1, "fn": 1, "tn": 0},
                        "rules": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(report, "MATRIX", fake)
    md = report.build_markdown()
    assert "0.5" in md, "a changed artifact must change the reported numbers"
    assert "| RP-OBS-COMPLETE@1.0.0 | 0.5 |" in md


def test_real_matrix_rates_appear_in_the_report():
    m = json.loads(MATRIX.read_text(encoding="utf-8"))
    md = report.build_markdown()
    for ref, pack in m["packs"].items():
        assert ref in md
        assert str(pack["overall"]["precision"]) in md


# ── AC-2: honest Limitations ────────────────────────────────────────────────


def test_limitations_section_is_present_and_prominent():
    md = report.build_markdown()
    assert "## Limitations" in md
    assert "understatement over overstatement" in md.lower()


def test_limitations_name_the_tiers_not_covered():
    """A perfect T1 must not read as broad validation."""
    md = report.build_markdown()
    assert "Only tier T1 was measured" in md
    for uncovered in ("T2", "T3", "T4"):
        assert uncovered in md


def test_limitations_disclose_synthetic_corpus_and_unsigned_bar():
    md = report.build_markdown().lower()
    assert "synthetic" in md
    assert "not real customer traffic" in md
    assert "no completion bar is signed" in md


def test_report_does_not_imply_a_pass_while_the_bar_is_unsigned():
    md = report.build_markdown().lower()
    assert "measured rates" in md
    assert "not a pass against an agreed bar" in md


# ── AC-3: language guardrails ───────────────────────────────────────────────


def test_report_contains_no_prohibited_claim_language():
    assert report._check_language(report.build_markdown()) == []


@pytest.mark.parametrize("phrase", report.PROHIBITED_PHRASES)
def test_language_guard_trips_on_each_prohibited_phrase(phrase):
    """The guard must actually fire — a check that never trips is decoration."""
    assert report._check_language(f"SARO is {phrase}.") == [phrase]


def test_report_states_no_customer_results():
    md = report.build_markdown().lower()
    assert "no customer results" in md


# ── AC-4: markdown + PDF output ─────────────────────────────────────────────


def test_pdf_is_generated_and_nonempty():
    assert PDF.exists()
    data = PDF.read_bytes()
    assert data.startswith(b"%PDF"), "output is not a PDF"
    assert len(data) > 1000


def test_report_lives_in_the_compliance_docs_area():
    assert MD.parent.name == "validation"
    assert (ROOT / "docs" / "validation").is_dir()
