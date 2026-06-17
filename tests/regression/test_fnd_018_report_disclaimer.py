"""FND-018: /risk/board-export PDF was missing the required compliance disclaimer.

docs/COMPLIANCE_CLAIMS_MATRIX.md ("Required Disclaimer (all reports)") mandates the
disclaimer on *every* exported report. The SPEC-FE2 board-summary export already
carried it, but the older ``export_board_pdf`` (/risk/board-export) built a full
board PDF with no disclaimer paragraph.

Fix: a single module-level ``_REPORT_DISCLAIMER`` constant, appended to both PDF
exporters. Pinned by (a) the constant matching the matrix text and (b) the
board-export function body referencing it.
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from routers import risk_dashboard
from routers.risk_dashboard import _REPORT_DISCLAIMER

pytestmark = pytest.mark.regression

_MATRIX = (
    pathlib.Path(__file__).parents[2] / "docs" / "COMPLIANCE_CLAIMS_MATRIX.md"
)


def test_disclaimer_constant_matches_compliance_matrix():
    text = _MATRIX.read_text(encoding="utf-8")
    # The canonical disclaimer sentence must appear verbatim in the matrix.
    assert _REPORT_DISCLAIMER.split(".")[0] in text, (
        "_REPORT_DISCLAIMER drifted from docs/COMPLIANCE_CLAIMS_MATRIX.md"
    )
    assert "does not constitute" in _REPORT_DISCLAIMER
    assert "regulatory certification" in _REPORT_DISCLAIMER


def test_board_export_function_appends_disclaimer():
    src = inspect.getsource(risk_dashboard.export_board_pdf)
    assert "_REPORT_DISCLAIMER" in src, (
        "/risk/board-export must append _REPORT_DISCLAIMER to the PDF (FND-018)"
    )


def test_both_pdf_exporters_use_the_shared_disclaimer():
    src = pathlib.Path(risk_dashboard.__file__).read_text(encoding="utf-8")
    # Both exporters reference the shared constant rather than an inline string.
    uses = len(re.findall(r"_REPORT_DISCLAIMER", src))
    assert uses >= 3, (
        "Expected the disclaimer constant defined once and used by both exporters "
        f"(definition + 2 uses); found {uses} references."
    )
