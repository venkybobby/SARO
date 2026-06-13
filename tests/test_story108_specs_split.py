"""STORY-108: multi-story bundles are split into one-file-per-story.

Pins that the three bundles are gone and each split story file is a well-formed,
single-story spec (a `# STORY-...` header + a Goal section), so a future edit can't
silently re-bundle or drop a story.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_SPECS = Path(__file__).parent.parent / "specs" / "stories"

_REMOVED_BUNDLES = [
    "SARO_RiskForm_Stories.md",
    "SARO_AIInsights_Stories.md",
    "SARO_Stories_Reports_Settings_Nav_Mobile.md",
]

_EXPECTED_PREFIXES = ("STORY-RISKFORM-", "STORY-AIINSIGHTS-", "STORY-REP-", "STORY-SET-", "STORY-NAV-", "STORY-MOB-")


@pytest.mark.unit
def test_bundles_are_removed():
    for b in _REMOVED_BUNDLES:
        assert not (_SPECS / b).exists(), f"multi-story bundle still present: {b}"


@pytest.mark.unit
def test_all_31_split_stories_exist():
    files = [p.name for p in _SPECS.glob("STORY-*.md")]
    split = [f for f in files if f.startswith(_EXPECTED_PREFIXES)]
    assert len(split) == 31, f"expected 31 split story files, found {len(split)}: {sorted(split)}"


@pytest.mark.unit
def test_each_split_file_is_a_single_wellformed_story():
    for p in _SPECS.glob("STORY-*.md"):
        if not p.name.startswith(_EXPECTED_PREFIXES):
            continue
        text = p.read_text(encoding="utf-8")
        first = text.splitlines()[0]
        assert first.startswith("# STORY-"), f"{p.name}: first line must be a level-1 STORY header, got {first!r}"
        # exactly one story header per file (no bundling)
        assert sum(1 for ln in text.splitlines() if ln.startswith("# STORY-")) == 1, (
            f"{p.name}: must contain exactly one story"
        )
        assert "## Goal" in text, f"{p.name}: missing Goal section"
