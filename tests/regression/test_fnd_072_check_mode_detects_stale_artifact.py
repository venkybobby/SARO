"""FND-072 — --check never compared the committed artifact against fresh compute.

FND-071 made `confusion_matrix_harness.py --check` read-only (correct), but the
write it removed had been an *accidental* freshness gate: rewriting
`quality/validation/confusion-latest.json` in the CI workspace meant the next
conformance.yml step (`generate_validation_report.py --check`) compared the
committed report against CURRENT rule-pack behaviour. With the write gone, both
sides of that comparison are committed files — self-referential — so a
rule-pack precision/recall regression leaves the committed evidence artifact
silently stale and no CI step notices.

Fix: in --check mode the harness diffs the freshly computed matrix (excluding
`generated_at`, the only field legitimately allowed to differ) against the
committed MATRIX_OUT and exits non-zero on mismatch — still with ZERO writes
(FND-071's read-only pin stays in force).

This test pins it by pointing MATRIX_OUT at a tampered copy of the committed
artifact and asserting --check fails loudly, passes when only the timestamp
differs, fails when the artifact is missing, and never writes even while
failing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import confusion_matrix_harness as harness  # noqa: E402

pytestmark = [pytest.mark.regression, pytest.mark.integration]


@pytest.fixture()
def sandboxed_artifact(tmp_path, monkeypatch):
    """Committed matrix as a dict + a tmp MATRIX_OUT the harness reads instead.

    TREND_OUT is sandboxed too so a regression that reintroduces writes can
    never touch the checked-in trend history from this test.
    """
    committed = json.loads(harness.MATRIX_OUT.read_text(encoding="utf-8"))
    matrix_copy = tmp_path / "confusion-latest.json"
    monkeypatch.setattr(harness, "MATRIX_OUT", matrix_copy)
    monkeypatch.setattr(harness, "TREND_OUT", tmp_path / "trend.jsonl")
    monkeypatch.setattr(harness, "OUT_DIR", tmp_path)
    return committed, matrix_copy


def _write(path: Path, matrix: dict) -> bytes:
    payload = (json.dumps(matrix, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return payload


def test_check_fails_when_committed_metrics_are_stale(sandboxed_artifact, capsys):
    committed, matrix_copy = sandboxed_artifact
    committed["packs"]["RP-OBS-COMPLETE@1.0.0"]["overall"]["precision"] = 0.5
    tampered_bytes = _write(matrix_copy, committed)

    exit_code = harness.main(["--check"])

    assert exit_code != 0, (
        "--check exited 0 against a committed artifact whose metrics no longer "
        "match current rule-pack behaviour — the evidence of record is stale "
        "and CI would ship it silently"
    )
    out = capsys.readouterr().out.lower()
    assert "stale" in out, "staleness must be named loudly, not buried in an exit code"
    # FND-071 still holds even on the failure path: --check never writes.
    assert matrix_copy.read_bytes() == tampered_bytes, (
        "--check modified the artifact while reporting it stale — check mode "
        "must stay read-only (FND-071)"
    )


def test_check_passes_when_only_generated_at_differs(sandboxed_artifact):
    committed, matrix_copy = sandboxed_artifact
    committed["generated_at"] = "1999-01-01T00:00:00+00:00"
    _write(matrix_copy, committed)

    assert harness.main(["--check"]) == 0, (
        "generated_at is the only field allowed to differ (same exclusion as "
        "the STORY-378 determinism test) — a timestamp-only delta is not stale"
    )


def test_check_fails_when_artifact_is_missing(sandboxed_artifact, capsys):
    _committed, matrix_copy = sandboxed_artifact
    assert not matrix_copy.exists()

    assert harness.main(["--check"]) != 0, (
        "a missing artifact of record is the worst staleness, not a pass"
    )
    assert "stale" in capsys.readouterr().out.lower()


def test_check_fails_when_artifact_is_corrupt(sandboxed_artifact):
    _committed, matrix_copy = sandboxed_artifact
    matrix_copy.write_text("{not json", encoding="utf-8")

    assert harness.main(["--check"]) != 0
