"""STORY-380 — Epic 13 closure audit.

The story's whole point is honesty about a false premise, so the tests assert
the audit records the correction and links real evidence — and, load-bearing,
that the phantom stories it triages genuinely do not exist (so the audit cannot
quietly start pretending they do).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.unit

AUDIT = ROOT / "docs" / "validation" / "epic13-closure-audit.md"
SPECS = ROOT / "specs" / "stories"


def _audit() -> str:
    return AUDIT.read_text(encoding="utf-8")


# ── The ground truth the audit rests on ─────────────────────────────────────


def test_epic13_stories_genuinely_do_not_exist():
    """If STORY-340..357 ever appear, this audit's premise is wrong — fail loud."""
    phantom = [p for n in range(340, 358) for p in SPECS.glob(f"STORY-{n}*.md")]
    assert phantom == [], f"Epic 13 stories now exist: {phantom} — revisit the audit"


def test_the_real_validation_stories_do_exist():
    for n in (335, 336, 337, 338):
        assert list(SPECS.glob(f"STORY-{n}*.md")), f"STORY-{n} spec missing"


# ── AC-1: triage with evidence links ────────────────────────────────────────


def test_audit_triages_335_to_338_with_evidence():
    doc = _audit()
    for story in ("STORY-335", "STORY-336", "STORY-337", "STORY-338"):
        assert story in doc
    # each carries a code/test pointer
    assert "grc/checks/groundedness.py" in doc
    assert "grc/guards/external_model.py" in doc
    assert "qa_lab/labeling.py" in doc


def test_audit_links_evidence_that_exists_in_the_repo():
    """Spot-check that the cited implementation files are real (no phantom links)."""
    for path in (
        "grc/checks/groundedness.py",
        "grc/guards/external_model.py",
        "grc/guards/claims_registry.py",
        "qa_lab/labeling.py",
        "scripts/confusion_matrix_harness.py",
    ):
        assert (ROOT / path).exists(), f"audit links {path} but it does not exist"


def test_audit_covers_the_pack_epic18_completion_bar():
    doc = _audit()
    for story in ("STORY-377", "STORY-378", "STORY-379", "STORY-380"):
        assert story in doc


# ── AC-2: numbering correction recorded ─────────────────────────────────────


def test_audit_records_that_epic13_never_existed():
    doc = re.sub(r"\s+", " ", _audit()).lower()
    assert "no such stories exist" in doc or "never did" in doc
    assert "no epic 13" in doc


def test_audit_records_the_strategy_version_correction():
    doc = _audit()
    assert "v1.0" in doc
    assert "v1.1" in doc, "the correction must name the version that never existed"


# ── AC-3: closed, but honestly — open items named ───────────────────────────


def test_audit_names_the_human_gate_rather_than_claiming_completeness():
    doc = _audit()
    assert "[HUMAN — OPEN]" in doc
    assert "STORY-377" in doc
    assert "not \"complete\"" in doc or "not complete" in doc.lower()


def test_audit_discloses_only_t1_is_measured():
    doc = _audit().lower()
    assert "only tier t1" in doc
    for tier in ("t2", "t3", "t4"):
        assert tier in doc


def test_audit_has_a_verdict():
    doc = _audit()
    assert "## Verdict" in doc
