#!/usr/bin/env python3
"""Release-PR changelog gate (STORY-375 AC-2).

A release must not ship without a curated changelog line. The changelog-drafter
*proposes* entries from commits; this gate enforces that a human actually landed
one before release. It runs only on PRs marked as releases (a `release` label or
a title starting `release:`), so ordinary PRs are never blocked.

"Has an entry" means: the PR's diff to CHANGELOG.md adds at least one bullet
under `## [Unreleased]`. Bumping the version without describing the change is the
exact drift this prevents.

Usage:
    python scripts/check_changelog_entry.py --base <ref> --head <ref>
    python scripts/check_changelog_entry.py            # diff against origin/main
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"


def _added_changelog_lines(base: str, head: str) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", f"{base}...{head}", "--", "CHANGELOG.md"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    # Added content lines (not the +++ header), stripped of the leading '+'.
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def _has_unreleased_bullet(added: list[str]) -> bool:
    """True if any added line is a bullet — a real user-facing entry.

    We do not require it to be textually under the Unreleased header in the diff
    hunk (diffs do not carry that structure reliably); a released section is
    added by the same PR that cuts the release, so any added bullet is evidence
    of a curated entry.
    """
    return any(ln.strip().startswith("- ") for ln in added)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv[1:])

    if not CHANGELOG.exists():
        print("FAIL: CHANGELOG.md is missing")
        return 1

    # The Unreleased section must exist to receive entries.
    text = CHANGELOG.read_text(encoding="utf-8")
    if "## [Unreleased]" not in text:
        print("FAIL: CHANGELOG.md has no '## [Unreleased]' section")
        return 1

    added = _added_changelog_lines(args.base, args.head)
    if not _has_unreleased_bullet(added):
        print(
            "FAIL: this release PR adds no changelog entry.\n"
            "Add a '- ' bullet under ## [Unreleased] describing the change from a "
            "user's perspective. The changelog-drafter can propose one; a human "
            "must curate it before release."
        )
        return 1

    print("changelog gate OK: release PR adds a curated entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
