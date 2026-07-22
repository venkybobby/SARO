"""STORY-383 — feedback → roadmap traceability.

The loop only works if it is closed both ways: feedback → story (via
PilotFeedback.story_id) and story → feedback (via a spec's feedback_ids). These
tests exercise the pure checker on both broken directions and the generated
"you said → we shipped" artifact.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_feedback_traceability as trace  # noqa: E402
import generate_feedback_summary as summary  # noqa: E402

pytestmark = pytest.mark.unit

STORY_QUALITY = ROOT / "docs" / "story-quality.md"
STANDARDS = ROOT / "docs" / "engineering-standards.md"


# ── AC-1: bidirectional linkage checker ─────────────────────────────────────


def test_a_fully_linked_loop_is_consistent():
    feedback = [{"id": "abc123", "triage_status": "story_linked", "story_id": "STORY-999"}]
    specs = {"STORY-999": ["abc123"]}
    assert trace.check_traceability(feedback, specs) == []


def test_story_linked_feedback_without_a_back_reference_is_flagged():
    """A one-way link is a broken loop."""
    feedback = [{"id": "abc123", "triage_status": "story_linked", "story_id": "STORY-999"}]
    specs = {}  # STORY-999 spec has no feedback_ids line
    problems = trace.check_traceability(feedback, specs)
    assert len(problems) == 1
    assert "no feedback_ids line" in problems[0]


def test_spec_citing_nonexistent_feedback_is_flagged():
    feedback = []
    specs = {"STORY-999": ["ghost-id"]}
    problems = trace.check_traceability(feedback, specs)
    assert any("no such feedback exists" in p for p in problems)


def test_story_linked_without_a_story_id_is_flagged():
    feedback = [{"id": "abc123", "triage_status": "story_linked", "story_id": None}]
    problems = trace.check_traceability(feedback, {})
    assert any("names no story_id" in p for p in problems)


def test_declined_and_parked_feedback_need_no_story_link():
    feedback = [
        {"id": "d1", "triage_status": "declined", "story_id": None},
        {"id": "p1", "triage_status": "parked", "story_id": None},
        {"id": "n1", "triage_status": "new", "story_id": None},
    ]
    assert trace.check_traceability(feedback, {}) == []


def test_short_prefix_ids_match_full_ids():
    """A spec may cite a short prefix of the feedback UUID."""
    feedback = [{"id": "3f2a9c1180ab", "triage_status": "story_linked", "story_id": "STORY-1"}]
    specs = {"STORY-1": ["3f2a"]}
    assert trace.check_traceability(feedback, specs) == []


def test_parse_feedback_ids_from_a_spec():
    text = "Some spec text\n\n**feedback_ids:** 3f2a, 9c11\n\nmore text"
    assert trace.parse_spec_feedback_ids(text) == ["3f2a", "9c11"]


def test_spec_without_feedback_ids_returns_empty():
    assert trace.parse_spec_feedback_ids("a normal spec with no feedback line") == []


# ── AC-2: the "you said → we shipped" summary ───────────────────────────────


def test_summary_lists_only_story_linked_feedback():
    feedback = [
        {"id": "a", "category": "confusing", "severity": "medium", "screen": "TraceView",
         "triage_status": "story_linked", "story_id": "STORY-999"},
        {"id": "b", "category": "bug", "severity": "high", "screen": "Hub",
         "triage_status": "declined", "story_id": None},
    ]
    md = summary.build_summary(feedback, {"STORY-999": "IMPLEMENTED"})
    assert "STORY-999" in md
    assert "IMPLEMENTED" in md
    assert md.count("| confusing |") == 1
    assert "| bug |" not in md, "declined feedback must not appear as shipped"


def test_summary_omits_the_free_text_body():
    """The body may be sensitive — it is deliberately not in the partner artifact."""
    feedback = [
        {"id": "a", "category": "gap", "severity": "low", "screen": "TraceView",
         "triage_status": "story_linked", "story_id": "STORY-1",
         "body": "SECRET internal detail that must not leak"},
    ]
    md = summary.build_summary(feedback, {})
    assert "SECRET internal detail" not in md


def test_summary_handles_the_empty_state_honestly():
    md = summary.build_summary([], {})
    assert "no feedback has been linked to a story yet" in md
    assert "0" in md


def test_summary_is_generated_not_hand_written():
    md = summary.build_summary([], {})
    assert "Not hand-written" in md
    assert "cannot claim we shipped" in md.lower()


# ── AC-3: convention documented (and honest about the missing agent) ────────


def test_story_quality_doc_defines_the_feedback_ids_convention():
    doc = STORY_QUALITY.read_text(encoding="utf-8")
    assert "feedback_ids" in doc
    assert "STORY-383" in doc


def test_convention_is_referenced_from_engineering_standards():
    doc = STANDARDS.read_text(encoding="utf-8")
    assert "feedback_ids" in doc
    assert "story-quality.md" in doc


def test_doc_is_honest_that_saro_story_author_does_not_exist():
    """Same FM-2 discipline: enforce via a real check, not a phantom agent."""
    doc = STORY_QUALITY.read_text(encoding="utf-8").lower()
    assert "does not exist" in doc
    assert "check_feedback_traceability" in doc


def test_the_real_specs_pass_the_traceability_check():
    """No spec in the repo currently has a broken feedback loop."""
    specs = trace._load_spec_feedback_ids()
    # No live feedback in CI, so this checks the spec side is internally sane.
    problems = trace.check_traceability([], specs)
    assert problems == [], f"a spec has a broken feedback link: {problems}"
