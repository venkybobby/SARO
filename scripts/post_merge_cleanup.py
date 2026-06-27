#!/usr/bin/env python3
"""Post-merge branch cleanup for SARO.

Loop: post-merge-cleanup (see loops/registry.yaml). Identifies remote feature
branches whose pull request has been MERGED and proposes them for deletion.

Merge detection uses the GitHub PR API (``merged_at``), NOT git ancestry. This is
deliberate: with squash- or rebase-merge strategies (GitHub's common defaults) a
merged branch's tip is not an ancestor of the base, so ``git branch --merged``
would miss it entirely. Keying off the PR's merged state is strategy-agnostic.

DRY-RUN by default: it only prints candidates. Deletion requires --apply and is
restricted to branches that (a) have a merged PR and (b) still exist on origin.
Protected branches (main/master/develop and any configured glob) are never touched.

Usage:
    # List branches with a merged PR that still exist (no deletion):
    GITHUB_REPOSITORY=owner/repo python scripts/post_merge_cleanup.py

    # Actually delete them on origin (used only by the scheduled workflow):
    GITHUB_REPOSITORY=owner/repo GITHUB_TOKEN=... python scripts/post_merge_cleanup.py --apply
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

# Never delete these, even if their PR was merged.
DEFAULT_PROTECTED = ("main", "master", "develop", "HEAD")

API_ROOT = "https://api.github.com"


def is_protected(branch: str, protected_globs: tuple[str, ...]) -> bool:
    """True if branch matches any protected name or glob pattern."""
    return any(fnmatch.fnmatch(branch, pat) for pat in protected_globs)


def extract_merged_head_refs(prs: list[dict]) -> list[str]:
    """From a list of PR objects, return the head branch names of those actually
    merged (``merged_at`` set), order-preserved."""
    refs: list[str] = []
    for pr in prs:
        if pr.get("merged_at") is None:
            continue
        ref = (pr.get("head") or {}).get("ref")
        if ref:
            refs.append(ref)
    return refs


def candidate_branches(
    merged_head_refs: list[str],
    existing_remote: list[str],
    base: str,
    protected_globs: tuple[str, ...],
) -> list[str]:
    """Branches safe to prune: their PR was merged AND they still exist on origin,
    excluding the base and any protected branch. De-duplicated, order-preserved."""
    existing = set(existing_remote)
    seen: set[str] = set()
    result: list[str] = []
    for ref in merged_head_refs:
        if not ref or ref == base or ref in seen:
            continue
        if ref not in existing:  # already deleted on origin
            continue
        if is_protected(ref, protected_globs):
            continue
        seen.add(ref)
        result.append(ref)
    return result


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def existing_remote_branches() -> list[str]:
    """Branch names that currently exist on origin (without the 'origin/' prefix)."""
    out = _git("branch", "-r")
    branches: list[str] = []
    for line in out.splitlines():
        name = line.strip()
        if not name or "->" in name:  # skip 'origin/HEAD -> origin/main'
            continue
        if name.startswith("origin/"):
            branches.append(name[len("origin/"):])
    return branches


def fetch_merged_prs(repo: str, base: str, token: str | None) -> list[dict]:
    """Fetch closed PRs targeting ``base`` from the GitHub API (paginated). The
    caller filters for merged ones via extract_merged_head_refs."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    prs: list[dict] = []
    page = 1
    while True:
        params: dict[str, str | int] = {
            "state": "closed", "base": base, "per_page": 100, "page": page,
        }
        resp = requests.get(
            f"{API_ROOT}/repos/{repo}/pulls",
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        prs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return prs


def delete_remote_branch(branch: str) -> None:
    _git("push", "origin", "--delete", branch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune branches whose PR was merged.")
    parser.add_argument("--base", default="main", help="Base branch PRs were merged into.")
    parser.add_argument("--repo", default=None,
                        help="owner/repo (default: $GITHUB_REPOSITORY).")
    parser.add_argument("--protect", action="append", default=[],
                        help="Extra protected branch name or glob (repeatable).")
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete the branches (default: dry-run).")
    args = parser.parse_args(argv)

    repo = args.repo or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("error: --repo or $GITHUB_REPOSITORY is required", file=sys.stderr)
        return 1
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    protected = DEFAULT_PROTECTED + tuple(args.protect)

    try:
        existing = existing_remote_branches()
    except subprocess.CalledProcessError as exc:
        print(f"error: could not list remote branches: {exc.stderr}", file=sys.stderr)
        return 1
    try:
        prs = fetch_merged_prs(repo, args.base, token)
    except requests.RequestException as exc:
        print(f"error: GitHub API request failed: {exc}", file=sys.stderr)
        return 1

    merged_refs = extract_merged_head_refs(prs)
    prunable = candidate_branches(merged_refs, existing, args.base, protected)

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
