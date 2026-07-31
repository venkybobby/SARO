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


class WaiverParseError(ValueError):
    """A line in the active waiver table looks like a row but doesn't match ROW_RE.

    Most commonly a literal `|` inside a Reason cell (e.g. a code span like
    `` `grep "A\\|B"` ``), which shifts every column after it. Without this
    check the row just silently drops out of the active waiver list — FND-094.
    """


def parse_waivers(path: Path = WAIVERS) -> list[tuple[str, date]]:
    rows: list[tuple[str, date]] = []
    unparsed: list[str] = []
    # Only the active table (above "## Retired waivers") is suppression-relevant.
    active_section = path.read_text(encoding="utf-8").split("## Retired waivers", 1)[0]
    for line in active_section.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        if set(stripped) <= set("|-: "):
            continue  # markdown separator row, e.g. |---|---|---|---|---|
        m = ROW_RE.match(stripped)
        if m:
            if m.group("id").upper() != "ID":
                y, mo, d = map(int, m.group("expiry").split("-"))
                rows.append((m.group("id"), date(y, mo, d)))
            continue
        if stripped.lower().startswith("| id "):
            continue  # header row
        unparsed.append(stripped)
    if unparsed:
        joined = "\n".join(f"  {line}" for line in unparsed)
        raise WaiverParseError(
            "row(s) in the active waiver table don't match the expected "
            "`| ID | Package | Reason | YYYY-MM-DD | Owner |` shape. A literal `|` "
            "inside a cell misaligns columns and would otherwise drop the row "
            f"silently — escape it as `\\|` or rephrase. Offending row(s):\n{joined}"
        )
    return rows


def main() -> int:
    try:
        rows = parse_waivers()
    except WaiverParseError as exc:
        print(f"scan-waivers PARSE ERROR: {exc}", file=sys.stderr)
        return 1
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
