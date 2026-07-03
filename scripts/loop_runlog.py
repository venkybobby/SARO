#!/usr/bin/env python3
"""Loop run-log recorder for SARO — observability for the loop fleet.

Loop-engineering anti-pattern #10 is "no run log": without a history of what each
loop did, you cannot debug a past decision. This records a structured, append-only
entry per loop run.

Two sinks, used together:
- ``loops/run-log.md`` (``--append``): a committed, auditable ledger. The low-
  frequency maintenance loops commit an entry per run (mirroring the weekly
  security-evidence pattern, with ``[skip ci]``), so the audit trail lives in git.
- the GitHub Actions job summary (``$GITHUB_STEP_SUMMARY``, written automatically
  when that env var is set): per-run observability for every loop, including the
  high-frequency LLM loops, with zero commit noise.

Usage:
    python scripts/loop_runlog.py <loop-id> --outcome ok --detail "2 PRs triaged" \
        --append loops/run-log.md
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_LOG = ROOT / "loops" / "run-log.md"

# The row marker delimits the appendable table body so new rows insert cleanly.
TABLE_HEADER = "| Timestamp (UTC) | Loop | Run | Outcome | Detail |"
TABLE_SEP = "|---|---|---|---|---|"

OUTCOMES = ("ok", "no-op", "halted", "failed")


def _escape(text: str) -> str:
    """Keep a value safe for a single Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def format_entry(timestamp: str, loop_id: str, run_id: str, outcome: str, detail: str) -> str:
    """Render one Markdown table row."""
    return (
        f"| {_escape(timestamp)} | {_escape(loop_id)} | {_escape(run_id or '-')} "
        f"| {_escape(outcome)} | {_escape(detail or '-')} |"
    )


def ensure_log(path: Path) -> None:
    """Create the run-log with its header if it does not exist yet."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# SARO Loop Run-Log\n\n"
        "Append-only history of loop runs (observability per loops/registry.yaml).\n"
        "Newest entries at the bottom. Written by scripts/loop_runlog.py.\n\n"
        f"{TABLE_HEADER}\n{TABLE_SEP}\n"
    )


def append_entry(path: Path, row: str) -> None:
    """Append a rendered row to the run-log, creating the file if needed."""
    ensure_log(path)
    with path.open("a") as fh:
        fh.write(row + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a loop run.")
    parser.add_argument("loop_id", help="Loop id (loops/registry.yaml).")
    parser.add_argument("--outcome", default="ok", choices=OUTCOMES,
                        help="Run outcome.")
    parser.add_argument("--detail", default="", help="Short free-text detail.")
    parser.add_argument("--run-id", default=None,
                        help="CI run id (default: $GITHUB_RUN_ID).")
    parser.add_argument("--timestamp", default=None, help="Override timestamp (UTC ISO).")
    parser.add_argument("--append", default=None,
                        help="Path to a run-log file to append to (e.g. loops/run-log.md).")
    args = parser.parse_args(argv)

    run_id = args.run_id or os.environ.get("GITHUB_RUN_ID", "")
    timestamp = args.timestamp or _now_iso()
    row = format_entry(timestamp, args.loop_id, run_id, args.outcome, args.detail)

    if args.append:
        append_entry(Path(args.append), row)

    # Per-run observability with no commit: write to the Actions job summary.
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(f"### Loop run: {args.loop_id}\n\n{TABLE_HEADER}\n{TABLE_SEP}\n{row}\n")

    print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
