#!/usr/bin/env python3
"""STORY-413: no hardcoded placeholder KPI tiles on the Dashboard.

Fences the exact failure mode STORY-413 removed (fabricated compliance
numbers captioned "sample — not yet wired to live data") from regenerating.
A `placeholder: true` KPI tile must never ship again — if the data doesn't
exist, the tile doesn't exist.

Exit 0 = clean, exit 1 = violation (printed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "frontend" / "src" / "pages" / "Dashboard.jsx"

_PLACEHOLDER_FLAG = re.compile(r"placeholder\s*:\s*true")
_STALE_CAPTION = "sample — not yet wired to live data"


def main() -> int:
    if not DASHBOARD.exists():
        print(f"ERROR: {DASHBOARD} not found")
        return 1

    text = DASHBOARD.read_text(encoding="utf-8")
    violations: list[str] = []

    for i, line in enumerate(text.splitlines(), start=1):
        if _PLACEHOLDER_FLAG.search(line):
            violations.append(f"Dashboard.jsx:{i}: hardcoded placeholder KPI tile: {line.strip()[:100]}")

    # Per-line matching alone can be defeated by wrapping `placeholder:` and
    # `true` across two lines (a per-line regex can never see the newline
    # between them). A whitespace-collapsed whole-file pass catches that case
    # too — no line number to report, but it still fails the build.
    collapsed = re.sub(r"\s+", " ", text)
    if not violations and _PLACEHOLDER_FLAG.search(collapsed):
        violations.append("Dashboard.jsx: a placeholder: true tile split across multiple lines evaded the per-line scan")

    if _STALE_CAPTION in text:
        violations.append(f'Dashboard.jsx: stale "{_STALE_CAPTION}" caption string still present')

    if violations:
        print("Placeholder-KPI-tile guard FAILED (STORY-413):")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("Placeholder-KPI-tile guard OK: no placeholder: true tiles, no stale caption.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
