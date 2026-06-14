"""STORY-103: the findings ledger and the regression manifest must stay consistent.

Investigation found NO duplicate FND IDs; the real risk is status drift between
quality/findings.md (uses `verify-pinned`) and tests/regression/manifest.yaml
(uses `open`). These pins enforce: no duplicate IDs, every ID present in both
files, and a documented status mapping (verify-pinned/open ⇔ no test yet;
pinned ⇔ pinned) so the two records cannot silently contradict each other.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).parent.parent
_FINDINGS = _ROOT / "quality" / "findings.md"
_MANIFEST = _ROOT / "tests" / "regression" / "manifest.yaml"


def _findings_rows() -> dict[str, str]:
    """Parse the findings.md markdown table -> {FND-id: status}."""
    rows: dict[str, str] = {}
    for line in _FINDINGS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(FND-\d{3,})\s*\|", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows[m.group(1)] = cells[-1]  # last column is Status
    return rows


def _manifest_rows() -> dict[str, str]:
    data = yaml.safe_load(_MANIFEST.read_text(encoding="utf-8")) or {}
    return {f["id"]: f["status"] for f in data.get("findings", [])}


@pytest.mark.unit
def test_no_duplicate_fnd_ids_in_findings_ledger():
    ids = [
        m.group(1)
        for line in _FINDINGS.read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"\|\s*(FND-\d{3,})\s*\|", line))
    ]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate FND IDs in findings.md: {sorted(dupes)}"


@pytest.mark.unit
def test_every_manifest_finding_is_in_the_ledger_and_vice_versa():
    findings = set(_findings_rows())
    manifest = set(_manifest_rows())
    assert findings == manifest, (
        f"ledger/manifest ID mismatch — only in findings.md: {findings - manifest}; "
        f"only in manifest: {manifest - findings}"
    )


@pytest.mark.unit
def test_status_mapping_is_consistent():
    """findings.md `pinned` <-> manifest `pinned`; `verify-pinned`/`open` <-> manifest `open`."""
    frows = _findings_rows()
    mrows = _manifest_rows()
    no_test = {"verify-pinned", "open"}
    contradictions = []
    for fid, fstatus in frows.items():
        mstatus = mrows.get(fid)
        if fstatus == "pinned" and mstatus != "pinned":
            contradictions.append(f"{fid}: ledger=pinned but manifest={mstatus}")
        if fstatus in no_test and mstatus not in no_test:
            contradictions.append(f"{fid}: ledger={fstatus} but manifest={mstatus} (expected open)")
    assert not contradictions, f"status drift: {contradictions}"


@pytest.mark.unit
def test_ledger_legend_documents_the_manifest_mapping():
    """The findings.md legend must explain the cross-file status mapping so it can't drift."""
    text = _FINDINGS.read_text(encoding="utf-8").lower()
    assert "appears as `status: open`" in text or "appear as `status: open`" in text, (
        "findings.md legend must explicitly document that verify-pinned maps to "
        "manifest `status: open`"
    )
