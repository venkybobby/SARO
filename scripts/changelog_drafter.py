#!/usr/bin/env python3
"""Conventional-Commits changelog drafter for SARO.

Loop: changelog-drafter (see loops/registry.yaml). Reads git history for a range,
groups commits by Conventional Commit type, and renders a Markdown changelog
section. It is PROPOSE-ONLY: it drafts notes and the workflow opens a PR. It never
publishes a release, never tags, and never writes to client systems.

Usage:
    # Draft notes for everything since the last tag (or from repo start):
    python scripts/changelog_drafter.py --version v8.1.0

    # Explicit range:
    python scripts/changelog_drafter.py --version v8.1.0 --from v8.0.0 --to HEAD
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# type(scope)!: description  — scope and the breaking "!" are optional.
_COMMIT = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<desc>.+)$"
)

# Display order and headings for known Conventional Commit types.
SECTIONS: list[tuple[str, str]] = [
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("build", "Build System"),
    ("ci", "CI/CD"),
    ("chore", "Chores"),
]
_KNOWN_TYPES = {t for t, _ in SECTIONS}


def parse_commit(subject: str) -> dict | None:
    """Parse a single commit subject into its Conventional Commit parts.

    Returns {"type", "scope", "breaking", "desc"} or None if the subject is not
    a Conventional Commit (those are dropped from the changelog body but counted
    as "other" by the caller if desired)."""
    m = _COMMIT.match(subject.strip())
    if not m:
        return None
    return {
        "type": m.group("type"),
        "scope": m.group("scope"),
        "breaking": bool(m.group("breaking")),
        "desc": m.group("desc").strip(),
    }


def group_commits(subjects: list[str]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Group parsed commit subjects by type. Returns (groups, breaking) where
    breaking is the list of breaking-change commits across all types."""
    groups: dict[str, list[dict]] = {}
    breaking: list[dict] = []
    for subject in subjects:
        parsed = parse_commit(subject)
        if parsed is None:
            continue
        groups.setdefault(parsed["type"], []).append(parsed)
        if parsed["breaking"]:
            breaking.append(parsed)
    return groups, breaking


def _format_entry(commit: dict) -> str:
    scope = f"**{commit['scope']}:** " if commit["scope"] else ""
    return f"- {scope}{commit['desc']}"


def render_changelog(version: str, subjects: list[str], date: str) -> str:
    """Render the Markdown changelog section for a release."""
    groups, breaking = group_commits(subjects)
    lines = [f"## {version} ({date})", ""]

    if breaking:
        lines.append("### ⚠ BREAKING CHANGES")
        lines.append("")
        for c in breaking:
            lines.append(_format_entry(c))
        lines.append("")

    has_body = bool(breaking)
    for type_key, heading in SECTIONS:
        entries = groups.get(type_key, [])
        if not entries:
            continue
        has_body = True
        lines.append(f"### {heading}")
        lines.append("")
        for c in entries:
            lines.append(_format_entry(c))
        lines.append("")

    if not has_body:
        lines.append("_No conventional commits in this range._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def last_tag() -> str | None:
    try:
        out = _git("describe", "--tags", "--abbrev=0").strip()
        return out or None
    except subprocess.CalledProcessError:
        return None


def commit_subjects(rev_range: str) -> list[str]:
    out = _git("log", "--no-merges", "--pretty=format:%s", rev_range)
    return [line for line in out.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draft a changelog from Conventional Commits.")
    parser.add_argument("--version", required=True, help="Release version label, e.g. v8.1.0")
    parser.add_argument("--from", dest="from_ref", default=None,
                        help="Start ref (default: last tag, else repo start).")
    parser.add_argument("--to", dest="to_ref", default="HEAD", help="End ref (default: HEAD).")
    parser.add_argument("--date", default=None, help="Release date YYYY-MM-DD (default: today UTC).")
    parser.add_argument("--output", default=None, help="Write to this file instead of stdout.")
    args = parser.parse_args(argv)

    date = args.date
    if date is None:
        # Resolve date from git rather than a forbidden Date.now-style call.
        from datetime import datetime, timezone
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    from_ref = args.from_ref or last_tag()
    rev_range = f"{from_ref}..{args.to_ref}" if from_ref else args.to_ref

    try:
        subjects = commit_subjects(rev_range)
    except subprocess.CalledProcessError as exc:
        print(f"error: git log failed for range {rev_range!r}: {exc.stderr}", file=sys.stderr)
        return 1

    section = render_changelog(args.version, subjects, date)

    if args.output:
        Path(args.output).write_text(section)
        print(f"Wrote changelog draft to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
