#!/usr/bin/env python3
"""Seed/refresh quality/baseline.json from a real measurement run.

Run MANUALLY only (never in CI): python scripts/update_quality_baseline.py
Lowering the baseline must be a deliberate, human-reviewed commit touching only this file's output.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "quality" / "baseline.json"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def coverage_pct() -> float:
    run([sys.executable, "-m", "pytest", "tests/", "-q", "--cov=.", "--cov-report=json", "--tb=no", "-p", "no:cacheprovider"])
    cov_file = ROOT / "coverage.json"
    if not cov_file.exists():
        return 0.0
    return round(json.loads(cov_file.read_text())["totals"]["percent_covered"], 2)


def ruff_errors() -> int:
    p = run([sys.executable, "-m", "ruff", "check", ".", "--output-format", "json"])
    try:
        return len(json.loads(p.stdout or "[]"))
    except json.JSONDecodeError:
        return -1


def mypy_errors() -> int:
    p = run([sys.executable, "-m", "mypy", ".", "--ignore-missing-imports"])
    last = (p.stdout.strip().splitlines() or [""])[-1]
    if "no issues found" in last:
        return 0
    # "Found N errors in ..."
    for tok in last.split():
        if tok.isdigit():
            return int(tok)
    return -1


def main() -> None:
    baseline = {
        "measured_on": date.today().isoformat(),
        "coverage_pct": coverage_pct(),
        "ruff_errors": ruff_errors(),
        "mypy_errors": mypy_errors(),
        "ratchet_policy": "metrics may only improve or hold; lowering requires a human-reviewed commit",
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}:\n{json.dumps(baseline, indent=2)}")


if __name__ == "__main__":
    main()
