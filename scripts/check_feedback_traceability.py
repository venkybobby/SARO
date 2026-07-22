#!/usr/bin/env python3
"""Feedback → roadmap traceability checker (STORY-383).

Verifies the loop between pilot feedback (STORY-382) and the stories it drove is
closed in BOTH directions:

* a feedback item marked ``story_linked`` to STORY-X should appear in STORY-X's
  ``feedback_ids`` line (a one-way link is a broken loop);
* a spec's ``feedback_ids`` should name feedback that exists and links back.

The core (:func:`check_traceability`) is pure — it takes the feedback rows and a
map of spec → feedback_ids — so it runs in CI without a live database. The CLI
wrapper reads feedback from the DB and the ids from ``specs/stories/*.md``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPECS = ROOT / "specs" / "stories"

# `**feedback_ids:** id, id` — ids are pilot_feedback UUIDs (or short prefixes).
_FEEDBACK_IDS_RE = re.compile(r"\*\*feedback_ids:\*\*\s*(.+)", re.IGNORECASE)
_STORY_RE = re.compile(r"STORY-[0-9A-Za-z-]+")


def parse_spec_feedback_ids(text: str) -> list[str]:
    """Return the feedback ids a spec cites, or []."""
    m = _FEEDBACK_IDS_RE.search(text)
    if not m:
        return []
    raw = m.group(1)
    return [tok.strip().strip(".,") for tok in re.split(r"[,\s]+", raw) if tok.strip().strip(".,")]


def _story_of(path: Path) -> str:
    m = _STORY_RE.search(path.name)
    return m.group(0) if m else path.stem


def check_traceability(
    feedback: list[dict],
    spec_feedback_ids: dict[str, list[str]],
) -> list[str]:
    """Return a list of broken-loop messages (empty == consistent).

    ``feedback`` items: ``{"id", "triage_status", "story_id"}``.
    ``spec_feedback_ids``: ``{story_id: [feedback_id, ...]}``.
    """
    problems: list[str] = []

    # Direction 1: story_linked feedback must be cited by its story's spec.
    for item in feedback:
        if item.get("triage_status") != "story_linked":
            continue
        story = item.get("story_id")
        fid = str(item.get("id", ""))
        if not story:
            problems.append(f"feedback {fid} is story_linked but names no story_id")
            continue
        cited = spec_feedback_ids.get(story)
        if cited is None:
            problems.append(
                f"feedback {fid} links to {story}, but that spec has no feedback_ids line"
            )
        elif not any(fid.startswith(c) or c.startswith(fid) for c in cited):
            problems.append(
                f"feedback {fid} links to {story}, but {story}'s feedback_ids does not cite it"
            )

    # Direction 2: a spec's feedback_ids must resolve to real feedback.
    known = {str(i.get("id", "")) for i in feedback}
    for story, ids in spec_feedback_ids.items():
        for cid in ids:
            if not any(k.startswith(cid) or cid.startswith(k) for k in known):
                problems.append(
                    f"{story} cites feedback_id {cid!r}, but no such feedback exists"
                )
    return problems


def _load_spec_feedback_ids() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in SPECS.glob("STORY-*.md"):
        ids = parse_spec_feedback_ids(path.read_text(encoding="utf-8"))
        if ids:
            out[_story_of(path)] = ids
    return out


def main(argv: list[str]) -> int:
    spec_ids = _load_spec_feedback_ids()

    feedback: list[dict] = []
    try:
        from database import _get_session_factory
        from models import PilotFeedback

        db = _get_session_factory()()
        try:
            feedback = [
                {"id": str(f.id), "triage_status": f.triage_status, "story_id": f.story_id}
                for f in db.query(PilotFeedback).all()
            ]
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — no DB in CI is fine; check specs only
        print(f"(no feedback DB available — checking spec side only: {exc})")

    problems = check_traceability(feedback, spec_ids)
    if problems:
        print("FEEDBACK TRACEABILITY — broken loop(s):")
        for p in problems:
            print(f"  {p}")
        return 1
    print(
        f"feedback traceability OK: {len(spec_ids)} spec(s) cite feedback, "
        f"{len(feedback)} feedback row(s) checked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
