"""FND-071 — harness --check mutated the checked-in validation artifacts.

`confusion_matrix_harness.main()` wrote `quality/validation/confusion-latest.json`
and appended a `trend.jsonl` line unconditionally — including in `--check` mode,
which is what CI and the STORY-378 test call. Consequence: every full pytest run
dirtied the working tree (fresh `generated_at`, duplicate trend lines) and broke
STORY-379's committed-report-equals-generated equality mid-run. Seven identical
trend lines of pure test churn had accumulated before this was caught.

Fix: `--check` is a read-only verification mode (compute + verdict + exit code,
no writes); only the default invocation persists the artifact and trend line.

This test pins it by byte-snapshotting both files, running `main(["--check"])`,
and asserting neither changed. The snapshot is restored even on failure so a
red run cannot itself dirty the tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import confusion_matrix_harness as harness  # noqa: E402

pytestmark = [pytest.mark.regression, pytest.mark.integration]


def test_check_mode_writes_nothing(tmp_path):
    matrix_before = harness.MATRIX_OUT.read_bytes()
    trend_before = harness.TREND_OUT.read_bytes()

    # finally-restore so even a regressed main() that writes AND raises cannot
    # leave the tree dirty — that contamination is exactly what this FND pins.
    try:
        exit_code = harness.main(["--check"])
        matrix_after = harness.MATRIX_OUT.read_bytes()
        trend_after = harness.TREND_OUT.read_bytes()
    finally:
        harness.MATRIX_OUT.write_bytes(matrix_before)
        harness.TREND_OUT.write_bytes(trend_before)

    assert exit_code == 0
    assert matrix_after == matrix_before, (
        "--check rewrote confusion-latest.json — check mode must be read-only "
        "(it runs inside pytest and CI, and every write dirties the tree and "
        "breaks STORY-379's committed-report equality)"
    )
    assert trend_after == trend_before, (
        "--check appended a trend line — trend history must record real "
        "validation runs, not test-suite churn"
    )
