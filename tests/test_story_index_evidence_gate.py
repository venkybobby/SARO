"""The story-index evidence gate must catch claimed-implemented-without-evidence.

A gate that passes everything is worse than no gate — it manufactures false
confidence, which is the same class of failure it was built to stop. These tests
feed it the exact drift patterns that caused the Epic 13 incident.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_story_index import check_index  # noqa: E402

pytestmark = pytest.mark.unit

_HEADER = "| Story | Title | Status | Evidence |\n|---|---|---|---|\n"


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "TEST-INDEX.md"
    p.write_text(_HEADER + body, encoding="utf-8")
    return p


def test_implemented_without_any_evidence_fails(tmp_path):
    """The Epic 13 pattern: a status asserted with nothing backing it."""
    v = check_index(_write(tmp_path, "| STORY-999 | Ghost work | IMPLEMENTED | — |\n"))
    assert len(v) == 1
    assert "no commit SHA" in v[0]


def test_implemented_with_nonexistent_sha_fails(tmp_path):
    """A cited-but-invented SHA must not satisfy the gate."""
    v = check_index(_write(tmp_path, "| STORY-999 | Ghost | IMPLEMENTED | deadbee · tests pass |\n"))
    assert len(v) == 1
    assert "does not exist" in v[0]


def test_implemented_with_real_sha_passes(tmp_path):
    """A real commit from this repo satisfies it."""
    import subprocess

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()
    v = check_index(_write(tmp_path, f"| STORY-999 | Real | IMPLEMENTED | {sha} · 5 pass |\n"))
    assert v == []


def test_drafted_row_citing_a_commit_fails(tmp_path):
    """Under-claiming is drift too — if it shipped, the row must say so."""
    import subprocess

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip()
    v = check_index(_write(tmp_path, f"| STORY-999 | Mislabeled | DRAFTED | {sha} |\n"))
    assert len(v) == 1
    assert "mark it IMPLEMENTED" in v[0]


@pytest.mark.parametrize("word", ["DONE", "COMPLETE", "SHIPPED", "FINISHED"])
def test_ambiguous_status_words_are_rejected(tmp_path, word):
    """'Done' is precisely the word that let 'drafted' read as 'delivered'."""
    v = check_index(_write(tmp_path, f"| STORY-999 | Ambiguous | {word} | — |\n"))
    assert len(v) == 1
    assert "closed vocabulary" in v[0]


def test_drafted_and_specified_pass_without_evidence(tmp_path):
    body = (
        "| STORY-1 | A spec | DRAFTED | — |\n"
        "| STORY-2 | Criteria written | SPECIFIED | — |\n"
        "| STORY-3 | Unverified dependency | PREMISE-UNVERIFIED | — |\n"
    )
    assert check_index(_write(tmp_path, body)) == []


def test_vocabulary_legend_table_is_not_parsed_as_status(tmp_path):
    """The legend documents the rules; it must not be read as claims."""
    p = tmp_path / "TEST-INDEX.md"
    p.write_text(
        "| Status | Means | Evidence required |\n|---|---|---|\n"
        "| `IMPLEMENTED` | Code exists | >=1 commit SHA |\n"
        "| `DRAFTED` | Doc written | must NOT cite a commit |\n",
        encoding="utf-8",
    )
    assert check_index(p) == []


def test_table_context_resets_between_tables(tmp_path):
    """Prose after a status table must not be parsed as more status rows."""
    p = tmp_path / "TEST-INDEX.md"
    p.write_text(
        _HEADER
        + "| STORY-1 | Spec | SPECIFIED | — |\n"
        + "\nSome prose paragraph.\n\n"
        + "| Pack claimed | Verified? | Repo reality |\n|---|---|---|\n"
        + "| Epic 13 exists | FALSE | no such files |\n",
        encoding="utf-8",
    )
    assert check_index(p) == []


def test_the_real_pack_index_passes(tmp_path):
    """The live index must satisfy its own gate."""
    real = ROOT / "specs" / "stories" / "STORY-PACK-14-19-INDEX.md"
    assert real.exists()
    assert check_index(real) == [], "the canonical status ledger violates its own rules"
