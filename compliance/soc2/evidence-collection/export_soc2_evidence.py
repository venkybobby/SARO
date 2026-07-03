#!/usr/bin/env python3
"""SOC 2 Type II — read-only recurring-evidence exporter (STORY-SOC-03, Epic 15).

Type II proves controls operate *over time*, so recurring evidence must be captured continuously
across the observation window rather than reconstructed at the end. This script snapshots the
*repo-resident* evidence into a timestamped bundle for the auditor.

HARD SAFETY CONSTRAINTS (STORY-SOC-03 AC-3 / DoD — "no runtime behavior changed"):
  * It imports NO SARO application module (no `engine`, `main`, `database`, `grc`, ...).
  * It opens NO database connection and makes NO network call.
  * It only READS repo artifacts (git metadata, quality baseline, regression manifest, CI workflow
    inventory) and WRITES a bundle under the chosen --out directory. It writes nowhere else.
  * `git` is invoked read-only (log/rev-parse) and treated as optional; absence is not fatal.

What it collects (maps to STORY-SOC-02 controls):
  * change management (CC8.1)      -> recent merge/commit history + current HEAD
  * quality ratchet (CC4.1)        -> quality/baseline.json snapshot
  * regression coverage (CC8.1)    -> tests/regression/manifest.yaml (finding -> status)
  * vuln mgmt / CI gates (CC7.3)   -> inventory of .github/workflows/*.yml
The output is a JSON manifest plus verbatim copies of the source artifacts.

Manual / off-repo evidence (access reviews, Fly.io/Supabase IAM exports, uptime, DR tests,
governance minutes) is intentionally OUT of scope here — it needs console access this script does
not have, and is captured manually per STORY-SOC-03 §2.

Suggested cadence (wiring left for the SOC-03 human gate to approve — it adds a CI workflow):
    # .github/workflows/soc2-evidence.yml (illustrative)
    # on:
    #   schedule: [{cron: "0 6 * * 1"}]   # Mondays 06:00 UTC
    #   workflow_dispatch:
    # jobs:
    #   export:
    #     runs-on: ubuntu-latest
    #     steps:
    #       - uses: actions/checkout@v4
    #         with: {fetch-depth: 0}       # full history for change-mgmt evidence
    #       - run: python compliance/soc2/evidence-collection/export_soc2_evidence.py --out _soc2_evidence
    #       - uses: actions/upload-artifact@v4
    #         with: {name: soc2-evidence, path: _soc2_evidence}

Usage:
    python compliance/soc2/evidence-collection/export_soc2_evidence.py [--out DIR] [--since-days N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Repo root = three levels up from this file (compliance/soc2/evidence-collection/).
REPO_ROOT = Path(__file__).resolve().parents[3]

# Repo-resident artifacts to snapshot verbatim, keyed by the SOC-02 control they evidence.
ARTIFACTS: dict[str, str] = {
    "quality_ratchet": "quality/baseline.json",
    "regression_manifest": "tests/regression/manifest.yaml",
}
CI_WORKFLOWS_DIR = ".github/workflows"


def _run_git(*args: str) -> str | None:
    """Run a read-only git command; return stdout or None if git/data is unavailable.

    git is optional evidence — a shallow checkout or a non-git export must not crash the run.
    """
    try:
        out = subprocess.run(  # noqa: S603 - fixed argv, no shell, read-only git subcommands
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def _change_management_evidence(since_days: int) -> dict:
    """Change-management evidence (CC8.1): current HEAD + recent commit/merge history."""
    head = _run_git("rev-parse", "HEAD")
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    log = _run_git(
        "log",
        f"--since={since_days}.days.ago",
        "--pretty=format:%h%x09%an%x09%aI%x09%s",
    )
    merges = _run_git(
        "log",
        f"--since={since_days}.days.ago",
        "--merges",
        "--pretty=format:%h%x09%aI%x09%s",
    )
    commits = [
        dict(zip(("sha", "author", "date", "subject"), line.split("\t", 3)))
        for line in (log.splitlines() if log else [])
        if line
    ]
    merge_list = [
        dict(zip(("sha", "date", "subject"), line.split("\t", 2)))
        for line in (merges.splitlines() if merges else [])
        if line
    ]
    return {
        "git_available": head is not None,
        "head": head,
        "branch": branch,
        "since_days": since_days,
        "commit_count": len(commits),
        "commits": commits,
        "merge_count": len(merge_list),
        "merges": merge_list,
    }


def _ci_workflow_inventory() -> dict:
    """Vuln-management / change-management gate evidence (CC7.3 / CC8.1): CI workflow inventory."""
    wf_dir = REPO_ROOT / CI_WORKFLOWS_DIR
    if not wf_dir.is_dir():
        return {"present": False, "workflows": []}
    workflows = sorted(
        p.name for p in wf_dir.iterdir() if p.suffix in {".yml", ".yaml"} and p.is_file()
    )
    return {"present": True, "count": len(workflows), "workflows": workflows}


def _copy_artifacts(bundle_dir: Path) -> dict:
    """Copy repo-resident artifacts verbatim into the bundle; record which were found/missing."""
    captured: dict[str, dict] = {}
    for key, rel in ARTIFACTS.items():
        src = REPO_ROOT / rel
        if src.is_file():
            dest = bundle_dir / Path(rel).name
            shutil.copy2(src, dest)
            captured[key] = {"source": rel, "captured_as": dest.name, "present": True}
        else:
            captured[key] = {"source": rel, "present": False}
    return captured


def export(out_dir: Path, since_days: int) -> Path:
    """Write a timestamped, read-only evidence bundle under out_dir; return the bundle path."""
    # UTC stamp is provided by the caller's clock (evidence provenance); no randomness used.
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    bundle_dir = out_dir / f"soc2-evidence-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "artifact": "SOC2 Type II recurring-evidence bundle",
        "story": "STORY-SOC-03 (Epic 15)",
        "generated_at_utc": stamp,
        "repo_root": str(REPO_ROOT),
        "disclaimer": (
            "Read-only repo-resident evidence snapshot. Not a SOC 2 report and not an "
            "attestation. Manual/off-repo evidence (access reviews, provider IAM, uptime, DR "
            "tests, governance minutes) is captured separately per STORY-SOC-03 section 2."
        ),
        "change_management_cc8_1": _change_management_evidence(since_days),
        "ci_gates_cc7_3_cc8_1": _ci_workflow_inventory(),
        "captured_artifacts": _copy_artifacts(bundle_dir),
    }

    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return bundle_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "_exports"),
        help="Output directory for the evidence bundle (default: ./_exports next to this script).",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=7,
        help="Look-back window in days for change-management (commit/merge) evidence (default: 7).",
    )
    args = parser.parse_args()

    bundle = export(Path(args.out).resolve(), args.since_days)
    print(f"SOC 2 evidence bundle written to: {bundle}")
    print(f"  manifest: {bundle / 'manifest.json'}")


if __name__ == "__main__":
    main()
