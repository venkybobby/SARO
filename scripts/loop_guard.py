#!/usr/bin/env python3
"""Loop preflight guard for SARO — kill switch + daily run cap.

Each loop workflow runs a `guard` job that calls this before doing any work:

    python scripts/loop_guard.py <loop-id>

Exit 0  -> proceed (the loop may run).
Exit 3  -> halt    (kill switch engaged, loop disabled, or daily run cap reached).

A halt is a normal, expected outcome — the calling workflow turns exit 3 into a
GREEN "skipped" run, NOT a failure. This closes the loop-engineering "no kill
switch" anti-pattern and gives operators a fleet-wide and per-loop off switch
(see loops/limits.yaml).

Run-count enforcement queries the GitHub Actions API for how many times the loop's
workflow ran today (UTC). If a token/repo isn't available it skips the cap check
(fail-open on the cap only) — the kill switch and the enabled flag are always
enforced because they need no network.
"""
from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
LIMITS = ROOT / "loops" / "limits.yaml"
API_ROOT = "https://api.github.com"

EXIT_PROCEED = 0
EXIT_HALT = 3

_TRUTHY = {"1", "true", "yes", "on"}


def load_limits(path: Path = LIMITS) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def env_kill_engaged(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return env.get("SARO_LOOPS_KILL_SWITCH", "").strip().lower() in _TRUTHY


def evaluate(
    limits: dict,
    loop_id: str,
    runs_today: int | None = None,
    env_kill: bool = False,
) -> tuple[bool, str]:
    """Pure decision: (proceed, reason).

    Order matters: kill switch first (cheapest, fleet-wide), then per-loop enabled,
    then the daily run cap. An unknown loop id is allowed by default so adding a new
    loop never silently blocks it — but the sync test keeps limits and registry aligned.
    """
    if env_kill or limits.get("kill_switch"):
        return False, "global kill switch engaged"
    cfg = (limits.get("loops") or {}).get(loop_id)
    if cfg is None:
        return True, f"no limits configured for '{loop_id}' (allowed by default)"
    if not cfg.get("enabled", True):
        return False, f"loop '{loop_id}' is disabled in loops/limits.yaml"
    cap = cfg.get("daily_run_cap", (limits.get("defaults") or {}).get("daily_run_cap"))
    if cap is not None and runs_today is not None and runs_today >= cap:
        return False, f"daily run cap reached ({runs_today}/{cap})"
    return True, "ok"


def runs_today(repo: str, workflow_file: str, token: str | None) -> int | None:
    """Count workflow runs created today (UTC) for the given workflow file, or None
    if it can't be determined (no repo/workflow/token, or API error)."""
    if not repo or not workflow_file:
        return None
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        params: dict[str, str | int] = {"created": f">={today}", "per_page": 100}
        resp = requests.get(
            f"{API_ROOT}/repos/{repo}/actions/workflows/{workflow_file}/runs",
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return int(resp.json().get("total_count", 0))
    except (requests.RequestException, ValueError, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loop preflight guard (kill switch + run cap).")
    parser.add_argument("loop_id", help="Loop id (must match loops/registry.yaml).")
    parser.add_argument("--limits", default=str(LIMITS), help="Path to limits.yaml.")
    parser.add_argument("--runs-today", type=int, default=None,
                        help="Override today's run count (else queried from the Actions API).")
    args = parser.parse_args(argv)

    limits = load_limits(Path(args.limits))
    cfg = (limits.get("loops") or {}).get(args.loop_id) or {}

    count = args.runs_today
    if count is None and not (env_kill_engaged() or limits.get("kill_switch")):
        count = runs_today(
            os.environ.get("GITHUB_REPOSITORY", ""),
            cfg.get("workflow", ""),
            os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        )

    proceed, reason = evaluate(limits, args.loop_id, count, env_kill_engaged())
    status = "PROCEED" if proceed else "HALT"
    print(f"[loop-guard] {args.loop_id}: {status} — {reason}")
    return EXIT_PROCEED if proceed else EXIT_HALT


if __name__ == "__main__":
    raise SystemExit(main())
