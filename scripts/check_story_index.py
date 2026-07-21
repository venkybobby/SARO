#!/usr/bin/env python3
"""Story-index evidence gate — the repo is the only status ledger that counts.

Root cause this closes: three ledgers (chat memory, planning docs, the repo)
drifted apart, and planning outputs — "produced the Epic 13 backlog", "published
the genesis rule-packs" — were carried forward as shipped fact. Twenty-six
stories were then authored on top of a premise no one had checked.

The structural fix: a story index row may only claim an implemented-class status
if it cites evidence that exists in git. This script verifies that claim
mechanically, so a stale row fails CI instead of misleading the next reader.

Rules enforced per index row:
  1. Implemented-class status (IMPLEMENTED / MERGED) REQUIRES an evidence cell
     containing at least one commit SHA that resolves in this repository.
  2. A cited SHA must actually exist (`git cat-file -e`) — a typo'd or
     invented SHA is the exact failure being guarded against.
  3. Draft-class status (DRAFTED / SPECIFIED / PLANNED / PREMISE-UNVERIFIED)
     must NOT cite commit evidence — if it shipped, say so.
  4. Vocabulary is closed: an unrecognised status word fails, because
     "done"/"complete" are the ambiguous terms that let drafted read as shipped.

Usage:
    python scripts/check_story_index.py [index.md ...]
Defaults to every specs/stories/*INDEX*.md file.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Closed status vocabulary. "drafted != implemented" is enforced here, not by
# convention: there is deliberately no "done" or "complete" — both blur the line.
IMPLEMENTED_STATUSES = {"IMPLEMENTED", "MERGED"}
DRAFT_STATUSES = {"DRAFTED", "SPECIFIED", "PLANNED", "PREMISE-UNVERIFIED", "BLOCKED", "N/A"}
VALID_STATUSES = IMPLEMENTED_STATUSES | DRAFT_STATUSES

SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
ROW_RE = re.compile(r"^\|(?P<cells>.+)\|\s*$")


def _sha_exists(sha: str) -> bool:
    """True only if *sha* is a commit REACHABLE from HEAD.

    Existence alone is not enough. `git cat-file` also resolves commits that
    were amended away, reset off the branch, or belong to an abandoned worktree:
    they linger in the object store until gc. Citing one of those is precisely
    the drift this gate exists to stop — the evidence looks real and points at
    nothing in the branch's history. Reachability is the property that actually
    means "this work is in the code you are looking at".

    (Found the hard way: amending a commit invalidated the SHA the index had
    just cited, and the existence-only check passed anyway.)
    """
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT, capture_output=True
    )
    if exists.returncode != 0:
        return False
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=ROOT, capture_output=True
    )
    return reachable.returncode == 0


def _split_row(line: str) -> list[str] | None:
    m = ROW_RE.match(line.strip())
    if not m:
        return None
    return [c.strip() for c in m.group("cells").split("|")]


def check_index(path: Path) -> list[str]:
    """Return a list of violation strings for one index file."""
    violations: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    status_col: int | None = None
    evidence_col: int | None = None

    for lineno, line in enumerate(lines, 1):
        cells = _split_row(line)
        if cells is None:
            # A non-table line ends the current table. Without this reset the
            # parser bleeds into the next table and reads its prose as status.
            status_col = evidence_col = None
            continue
        upper = [c.upper() for c in cells]

        # A status table is identified by all three columns: a subject column
        # (Story/Item), a Status column, and an Evidence column. Requiring the
        # subject column is what distinguishes a real status table from the
        # vocabulary legend, which also has Status/Evidence headers but
        # documents the rules rather than asserting any story's state.
        has_subject = any(c in ("STORY", "ITEM") for c in upper)
        if has_subject and "STATUS" in upper and any("EVIDENCE" in c for c in upper):
            status_col = upper.index("STATUS")
            evidence_col = next(i for i, c in enumerate(upper) if "EVIDENCE" in c)
            continue

        if status_col is None or evidence_col is None:
            continue
        if set("".join(cells)) <= set("-: "):  # markdown separator row
            continue
        if len(cells) <= max(status_col, evidence_col):
            continue

        story = cells[0]
        status = re.sub(r"[*`_]", "", cells[status_col]).strip().upper()
        evidence_cell = cells[evidence_col]
        if not status:
            continue

        where = f"{path.name}:{lineno} [{story}]"

        if status not in VALID_STATUSES:
            violations.append(
                f"{where}: status {status!r} is outside the closed vocabulary "
                f"{sorted(VALID_STATUSES)} — 'done'/'complete' blur drafted vs implemented"
            )
            continue

        # Candidates are hex-shaped tokens. Do NOT pre-filter all-digit strings:
        # roughly 1 in 27 short SHAs is all decimal digits ((10/16)**7), and an
        # earlier version of this gate discarded exactly such a SHA as "not a
        # commit", reporting a correctly-evidenced row as unevidenced. Git is
        # the authority on what resolves, so ask it rather than guessing.
        candidates = SHA_RE.findall(evidence_cell)
        resolvable = [s for s in candidates if _sha_exists(s)]

        if status in IMPLEMENTED_STATUSES:
            if resolvable:
                continue
            if candidates:
                violations.append(
                    f"{where}: cites {candidates} — no such commit is reachable "
                    "from HEAD in this repo"
                )
            else:
                violations.append(
                    f"{where}: claims {status} with no commit SHA in the evidence "
                    "column — claimed-implemented without commit evidence (FM-1)"
                )
        else:
            # Only commits that actually resolve count as an over-claim; a bare
            # number in prose is not evidence of shipped work.
            if resolvable:
                violations.append(
                    f"{where}: status {status} but cites commit(s) {resolvable} — "
                    "if it shipped, mark it IMPLEMENTED"
                )

    return violations


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]]
    if not targets:
        targets = sorted((ROOT / "specs" / "stories").glob("*INDEX*.md"))
    if not targets:
        print("check_story_index: no index files found — nothing to verify")
        return 0

    all_violations: list[str] = []
    for path in targets:
        if not path.exists():
            print(f"check_story_index: {path} not found")
            return 1
        all_violations.extend(check_index(path))

    if all_violations:
        print("STORY INDEX EVIDENCE GATE — FAILED\n")
        for v in all_violations:
            print(f"  {v}")
        print(
            "\nThe repo is the only status ledger that counts. A row is only "
            "IMPLEMENTED when it cites a commit that exists."
        )
        return 1

    print(f"check_story_index OK: {len(targets)} index file(s), all claims evidence-backed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
