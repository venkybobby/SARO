"""Enforces the regression-suite policy itself. If this fails, the process broke, not the code.

Checks:
1. Every manifest entry with status=pinned points to an existing test file.
2. Every test_fnd_*.py file in this directory has a manifest entry.
3. Quarantined entries have an expiry date that has not passed (max 14 days out).
4. No pytest skip markers in regression tests unless the finding is quarantined.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest
import yaml

REG_DIR = Path(__file__).parent
MANIFEST = REG_DIR / "manifest.yaml"
VALID_STATUSES = {"open", "pinned", "quarantined"}


def _load() -> list[dict]:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    return data.get("findings", [])


def test_manifest_parses_and_statuses_valid():
    findings = _load()
    assert findings, "manifest.yaml has no findings list"
    for f in findings:
        assert re.fullmatch(r"FND-\d{3,}", f["id"]), f"bad id: {f.get('id')}"
        assert f["status"] in VALID_STATUSES, f"{f['id']}: bad status {f['status']}"


def test_pinned_entries_have_existing_test_files():
    missing = [
        f["id"]
        for f in _load()
        if f["status"] == "pinned" and not (REG_DIR.parent.parent / f["test"]).exists()
    ]
    assert not missing, f"pinned findings missing test files: {missing}"


def test_every_regression_test_file_is_in_manifest():
    manifest_files = {Path(f["test"]).name for f in _load()}
    on_disk = {
        p.name
        for p in REG_DIR.glob("test_fnd_*.py")
    }
    orphans = on_disk - manifest_files
    assert not orphans, f"regression tests not registered in manifest.yaml: {sorted(orphans)}"


def test_quarantine_not_expired():
    today = dt.date.today()
    expired, malformed = [], []
    for f in _load():
        if f["status"] != "quarantined":
            continue
        exp = f.get("quarantine_expires")
        if not exp:
            malformed.append(f["id"])
            continue
        exp_date = dt.date.fromisoformat(str(exp))
        if exp_date < today:
            expired.append(f["id"])
        if (exp_date - today).days > 14:
            malformed.append(f["id"])
    assert not malformed, f"quarantine without valid <=14-day expiry: {malformed}"
    assert not expired, f"quarantine expired — fix or get human approval to remove: {expired}"


def test_no_unapproved_skips_in_regression_dir():
    quarantined_files = {
        Path(f["test"]).name for f in _load() if f["status"] == "quarantined"
    }
    offenders = []
    for p in REG_DIR.glob("test_fnd_*.py"):
        src = p.read_text(encoding="utf-8")
        if re.search(r"pytest\.mark\.skip|pytest\.skip\(", src) and p.name not in quarantined_files:
            offenders.append(p.name)
    assert not offenders, f"skip marker without quarantined status in manifest: {offenders}"


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
