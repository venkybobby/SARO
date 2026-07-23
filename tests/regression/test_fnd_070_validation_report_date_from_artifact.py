"""FND-070 — validation report "Generated:" date was wall-clock, not artifact.

`scripts/generate_validation_report.py` stamped `datetime.now()` into the
markdown while STORY-379's `test_report_is_current_with_the_artifact` asserts
byte-equality between the committed report and a fresh `build_markdown()`.
The pair could only be green on the exact day the report was last regenerated —
a time-bomb that turned the whole suite red the following day (first tripped
2026-07-23, one day after the report was committed).

Fix: the report date derives from the artifact's own `generated_at`, honoring
the story's principle that every fact in the report comes from the artifact.
This test pins that by generating from a fake artifact with a fixed, past
`generated_at` and asserting THAT date (not today) is rendered.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_validation_report as report  # noqa: E402

pytestmark = [pytest.mark.regression, pytest.mark.unit]

FROZEN_ARTIFACT_DATE = "2001-02-03"


@pytest.fixture()
def frozen_matrix(monkeypatch, tmp_path):
    fake = tmp_path / "matrix.json"
    fake.write_text(
        json.dumps(
            {
                "generated_at": f"{FROZEN_ARTIFACT_DATE}T04:05:06.000000+00:00",
                "tier": "T1",
                "corpus_records": 1,
                "packs": {
                    "RP-OBS-COMPLETE@1.0.0": {
                        "overall": {
                            "precision": 1.0,
                            "recall": 1.0,
                            "f1": 1.0,
                            "tp": 1,
                            "fp": 0,
                            "fn": 0,
                            "tn": 0,
                        },
                        "rules": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(report, "MATRIX", fake)


def test_report_date_comes_from_the_artifact_not_the_wall_clock(frozen_matrix):
    md = report.build_markdown()
    assert f"- **Generated:** {FROZEN_ARTIFACT_DATE}" in md, (
        "the report's Generated date must be the artifact's generated_at, "
        "not datetime.now() — otherwise byte-equality with the committed "
        "report (STORY-379 AC-1) breaks the day after every regeneration"
    )
    today = datetime.now(tz=timezone.utc).date().isoformat()
    assert today not in md, "wall-clock date leaked into the generated report"


def test_build_markdown_is_deterministic_across_calls(frozen_matrix):
    assert report.build_markdown() == report.build_markdown()
