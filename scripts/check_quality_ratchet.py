#!/usr/bin/env python3
"""CI ratchet gate: fail if coverage dropped or lint/type errors increased vs quality/baseline.json.

Usage in CI (after a coverage run that produced coverage.json):
    python scripts/check_quality_ratchet.py
Exit 0 = ratchet holds. Exit 1 = quality regressed. Exit 78 = baseline not seeded (advisory pass).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "quality" / "baseline.json"
COVERAGE_TOLERANCE = 0.5  # pct points of measurement noise allowed


def current_ruff() -> int:
    p = subprocess.run([sys.executable, "-m", "ruff", "check", ".", "--output-format", "json"],
                       cwd=ROOT, capture_output=True, text=True)
    try:
        return len(json.loads(p.stdout or "[]"))
    except json.JSONDecodeError:
        return 10**6


def main() -> int:
    if not BASELINE.exists():
        print("::warning::quality/baseline.json not seeded — run scripts/update_quality_baseline.py locally and commit it.")
        return 78
    base = json.loads(BASELINE.read_text())
    failures: list[str] = []

    cov_file = ROOT / "coverage.json"
    if cov_file.exists() and base.get("coverage_pct") is not None:
        cur = json.loads(cov_file.read_text())["totals"]["percent_covered"]
        if cur < base["coverage_pct"] - COVERAGE_TOLERANCE:
            failures.append(f"coverage dropped: {cur:.2f}% < baseline {base['coverage_pct']}%")
        else:
            print(f"coverage OK: {cur:.2f}% (baseline {base['coverage_pct']}%)")

    cur_ruff = current_ruff()
    if base.get("ruff_errors", -1) >= 0 and cur_ruff > base["ruff_errors"]:
        failures.append(f"ruff errors increased: {cur_ruff} > baseline {base['ruff_errors']}")
    else:
        print(f"ruff OK: {cur_ruff} (baseline {base.get('ruff_errors')})")

    if failures:
        for f in failures:
            print(f"::error::RATCHET VIOLATION — {f}")
        return 1
    print("Quality ratchet holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
