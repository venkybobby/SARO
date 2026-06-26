#!/usr/bin/env python3
"""Post-merge branch cleanup for SARO.

Loop: post-merge-cleanup (see loops/registry.yaml). Identifies remote feature
branches that have already been merged into the base branch and proposes them for
deletion. DRY-RUN by default: it only prints what it would delete. Actual deletion
requires --apply AND is restricted to branches git reports as fully merged into
the base. Protected branches (main/master/develop and any configured glob) are
never touched, and only the 'origin' remote is considered.

Usage:
    # List merged branches that are candidates for pruning (no deletion):
    python scripts/post_merge_cleanup.py

    # Actually delete them on origin (used only by the scheduled workflow):
    python scripts/post_merge_cleanup.py --apply
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Never delete these, even if git reports them merged.
DEFAULT_PROTECTED = ("main", "master", "develop", "HEAD")


def is_protected(branch: str, protected_globs: tuple[str, ...]) -> bool:
    """True if branch matches any protected name or glob pattern."""
    return any(fnmatch.fnmatch(branch, pat) for pat in protected_globs)


def select_prunable(
    merged_branches: list[str],
    base: str,
    protected_globs: tuple[str, ...],
) -> list[str]:
    """From a list of branches already merged into base, return those safe to
    prune: not the base itself, not protected, de-duplicated, order-preserved."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in merged_branches:
        branch = raw.strip()
        if not branch or branch == base:
            continue
        if is_protected(branch, protected_globs):
            continue
        if branch in seen:
            continue
        seen.add(branch)
        result.append(branch)
    return result


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def merged_remote_branches(base: str) -> list[str]:
    """Remote branches on origin fully merged into origin/<base>, with the
    'origin/' prefix stripped."""
    out = _git("branch", "-r", "--merged", f"origin/{base}")
    branches: list[str] = []
    for line in out.splitlines():
        name = line.strip()
        if not name or "->" in name:  # skip 'origin/HEAD -> origin/main'
            continue
        if name.startswith("origin/"):
            branches.append(name[len("origin/"):])
    return branches


def delete_remote_branch(branch: str) -> None:
    _git("push", "origin", "--delete", branch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune merged remote feature branches.")
    parser.add_argument("--base", default="main", help="Base branch to measure merges against.")
    parser.add_argument("--protect", action="append", default=[],
                        help="Extra protected branch name or glob (repeatable).")
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete the branches (default: dry-run).")
    args = parser.parse_args(argv)

    protected = DEFAULT_PROTECTED + tuple(args.protect)

    try:
        merged = merged_remote_branches(args.base)
    except subprocess.CalledProcessError as exc:
        print(f"error: could not list merged branches: {exc.stderr}", file=sys.stderr)
        return 1

    prunable = select_prunable(merged, args.base, protected)

    if not prunable:
        print("No merged feature branches to prune.")
        return 0

    verb = "Deleting" if args.apply else "Would delete"
    for branch in prunable:
        print(f"{verb}: {branch}")
        if args.apply:
            try:
                delete_remote_branch(branch)
            except subprocess.CalledProcessError as exc:
                print(f"  warning: failed to delete {branch}: {exc.stderr}", file=sys.stderr)

    if not args.apply:
        print(f"\nDry-run: {len(prunable)} branch(es) would be pruned. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
