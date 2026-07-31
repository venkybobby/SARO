"""FND-094: a literal `|` in a waiver's Reason cell silently drops the row.

check_scan_waivers.ROW_RE parses security/scan-waivers.md by matching each
table row against a fixed column-count regex. If a Reason cell ever contains
a literal pipe (e.g. inside a code span like `grep "A\\|B"`), the extra pipe
shifts every column after it, the row no longer matches ROW_RE, and it was
silently dropped from the active waiver list — no error, no warning. The
finding "fails closed" (the scanner just re-gates on that finding instead of
over-suppressing), but it is still a footgun for whoever edits the waiver
file next without noticing the row vanished.

Fix: parse_waivers() now walks the active waiver table's row region and
raises WaiverParseError if any line that looks like a table row fails to
match the expected 5-column shape, instead of silently skipping it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_scan_waivers import WaiverParseError, parse_waivers  # noqa: E402

pytestmark = pytest.mark.unit

_HEADER = "| ID | Package | Reason | Expiry | Owner |\n|---|---|---|---|---|\n"


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "scan-waivers.md"
    p.write_text(_HEADER + body, encoding="utf-8")
    return p


def test_pipe_in_reason_cell_fails_loud_instead_of_dropping_the_row(tmp_path):
    """The exact FND-094 pattern: a code span with an escaped pipe in Reason."""
    row = (
        '| PYSEC-2026-9999 | somepkg 1.0 | Confirmed via `grep "A\\|B" file` — safe | '
        "2026-12-01 | Venky |\n"
    )
    path = _write(tmp_path, row)
    with pytest.raises(WaiverParseError):
        parse_waivers(path)


def test_well_formed_row_still_parses(tmp_path):
    """Control case: a normal row with no stray pipes parses cleanly."""
    row = (
        "| PYSEC-2026-9999 | somepkg 1.0 | Safe, no fix needed | 2026-12-01 | Venky |\n"
    )
    path = _write(tmp_path, row)
    rows = parse_waivers(path)
    assert rows == [("PYSEC-2026-9999", __import__("datetime").date(2026, 12, 1))]


def test_retired_table_rows_are_not_parsed_as_active(tmp_path):
    """Rows under '## Retired waivers' must never count as active waivers."""
    body = (
        "| PYSEC-2026-1 | pkg | fine | 2026-12-01 | Venky |\n"
        "\n## Retired waivers\n\n"
        "| ID | Package | Retired | How resolved |\n|---|---|---|---|\n"
        "| GHSA-old | pkg | 2026-01-01 | upgraded |\n"
    )
    path = _write(tmp_path, body)
    rows = parse_waivers(path)
    assert [vid for vid, _ in rows] == ["PYSEC-2026-1"]
