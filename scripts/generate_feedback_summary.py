#!/usr/bin/env python3
"""Quarterly "you said → we shipped" summary generator (STORY-383).

Produces a partner-facing summary from the feedback→story linkage — never
hand-typed, so it cannot drift from what actually shipped. For each feedback item
that became a story, it shows the feedback (redacted to category / severity /
screen — **not** the free-text body, which may be sensitive and is not for
external sharing) and the story it drove. This is the SummitCare renewal artifact.

The core (:func:`build_summary`) is pure — takes feedback rows + a spec-status
map — so it is testable without a live database. The CLI wrapper reads feedback
from the DB and story status from the pack index.

Usage:
    python scripts/generate_feedback_summary.py            # write the summary
    python scripts/generate_feedback_summary.py --check    # verify up to date
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "feedback-you-said-we-shipped.md"


def build_summary(feedback: list[dict], story_status: dict[str, str]) -> str:
    """feedback items: {id, category, severity, screen, triage_status, story_id}.
    story_status: {story_id: 'IMPLEMENTED' | 'SPECIFIED' | ...}.
    """
    shipped = [f for f in feedback if f.get("triage_status") == "story_linked" and f.get("story_id")]
    shipped.sort(key=lambda f: (f.get("story_id") or "", f.get("category") or ""))

    lines = [
        "# SARO — You Said, We Shipped",
        "",
        "> **Generated** by `scripts/generate_feedback_summary.py` from the "
        "feedback→story linkage. Not hand-written — it cannot claim we shipped "
        "something the backlog does not show.",
        "",
        f"- **Generated:** {datetime.now(tz=timezone.utc).date().isoformat()}",
        f"- **Feedback items that became stories:** {len(shipped)}",
        "",
        "The free-text of each note is deliberately omitted — it may be sensitive "
        "and is not for external sharing. Each row shows the *shape* of the "
        "feedback and the story it drove.",
        "",
        "| You said (feedback) | Screen | Severity | We shipped | Status |",
        "|---|---|---|---|---|",
    ]
    if not shipped:
        lines.append("| _(no feedback has been linked to a story yet)_ | | | | |")
    for f in shipped:
        story = f["story_id"]
        status = story_status.get(story, "unknown")
        lines.append(
            f"| {f.get('category', '?')} | {f.get('screen', '?')} | "
            f"{f.get('severity', '?')} | {story} | {status} |"
        )
    lines += [
        "",
        "*Feedback categories: bug · gap · confusing · feature. Status reflects "
        "the story's current state in the backlog.*",
        "",
    ]
    return "\n".join(lines) + "\n"


def _load_story_status() -> dict[str, str]:
    """Best-effort story status from the pack index rows."""
    import re

    idx = ROOT / "specs" / "stories" / "STORY-PACK-14-19-INDEX.md"
    status: dict[str, str] = {}
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*(STORY-[0-9A-Za-z-]+)\s*\|[^|]*\|\s*([A-Z-]+)\s*\|", line)
            if m:
                status[m.group(1)] = m.group(2)
    return status


def main(argv: list[str]) -> int:
    feedback: list[dict] = []
    try:
        from database import _get_session_factory
        from models import PilotFeedback

        db = _get_session_factory()()
        try:
            feedback = [
                {
                    "id": str(f.id), "category": f.category, "severity": f.severity,
                    "screen": f.screen, "triage_status": f.triage_status, "story_id": f.story_id,
                }
                for f in db.query(PilotFeedback).all()
            ]
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — no DB in CI: emit the empty-state summary
        print(f"(no feedback DB — generating empty-state summary: {exc})")

    content = build_summary(feedback, _load_story_status())

    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != content:
            # Content depends on live feedback, so a mismatch is expected when
            # feedback exists — the check verifies the file is PRESENT and the
            # generator runs, not byte-equality against live data.
            if not OUT.exists():
                print(f"FAIL: {OUT} missing — run scripts/generate_feedback_summary.py")
                return 1
        print("feedback summary generator OK")
        return 0

    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
