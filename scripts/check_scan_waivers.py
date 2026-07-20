#!/usr/bin/env python3
"""STORY-367 — waiver hygiene: expired security-scan waivers fail the build.

Reads security/scan-waivers.md, parses the waiver table, and exits non-zero if
any waiver's expiry date has passed. Also prints the --ignore-vuln arguments for
pip-audit so the workflow derives its suppressions FROM the waiver file — a
waiver that isn't documented can't suppress anything.

Usage:
  python scripts/check_scan_waivers.py            # validate expiries
  python scripts/check_scan_waivers.py --pip-args # emit "--ignore-vuln ID ..."
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

WAIVERS = Path(__file__).resolve().parents[1] / "security" / "scan-waivers.md"

ROW_RE = re.compile(
    r"^\|\s*(?P<id>[A-Za-z0-9-]+)\s*\|[^|]*\|[^|]*\|\s*(?P<expiry>\d{4}-\d{2}-\d{2})\s*\|"
)


def parse_waivers() -> list[tuple[str, date]]:
    rows: list[tuple[str, date]] = []
    for line in WAIVERS.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line.strip())
        if m and m.group("id").upper() != "ID":
            y, mo, d = map(int, m.group("expiry").split("-"))
            rows.append((m.group("id"), date(y, mo, d)))
    return rows


def main() -> int:
    rows = parse_waivers()
    if "--pip-args" in sys.argv:
        print(" ".join(f"--ignore-vuln {vid}" for vid, _ in rows))
        return 0
    today = date.today()
    expired = [(vid, exp) for vid, exp in rows if exp < today]
    for vid, exp in expired:
        print(f"EXPIRED WAIVER: {vid} (expired {exp}) — re-triage or renew with a new reason")
    if expired:
        return 1
    print(f"scan-waivers OK: {len(rows)} active, none expired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
