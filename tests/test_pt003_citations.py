"""PT-003: framework citation correction & verification pass.

- The citation inventory exists and covers every rule-pack rule_id.
- The 50-sample minimum is never attributed to EU AI Act Art. 10 / NIST MAP 2.3.
- The lint discriminates an attribution from a disclaimer.
"""
import re
from pathlib import Path

import pytest

from scripts.check_citations import (
    _DISCLAIMER,
    _FORBIDDEN_SAMPLE_CITATION,
    _rule_ids,
    main,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent


def test_citation_lint_passes():
    assert main() == 0


def test_inventory_covers_every_rule_id():
    inv = (ROOT / "docs" / "CITATION_INVENTORY.md").read_text(encoding="utf-8")
    missing = [rid for rid, _ in _rule_ids() if rid not in inv]
    assert not missing, f"rule_ids missing from inventory: {missing}"


def test_sample_floor_not_attributed_to_regulation_in_engine():
    text = (ROOT / "engine.py").read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if _FORBIDDEN_SAMPLE_CITATION.search(line) and not _DISCLAIMER.search(line):
            pytest.fail(f"engine.py:{i} attributes sample floor to a regulation: {line.strip()}")


def test_lint_flags_misattribution_but_not_disclaimer():
    bad = "Enforce minimum 50 samples (EU AI Act Art. 10, NIST MAP 2.3)"
    good = "EU AI Act Art. 10 and NIST MAP 2.3 set no batch-audit sample threshold"
    assert _FORBIDDEN_SAMPLE_CITATION.search(bad) and not _DISCLAIMER.search(bad)
    assert not (_FORBIDDEN_SAMPLE_CITATION.search(good) and not _DISCLAIMER.search(good))


def test_method_001_entry_present():
    inv = (ROOT / "docs" / "CITATION_INVENTORY.md").read_text(encoding="utf-8")
    assert "SARO-METHOD-001" in inv
    assert re.search(r"NOT.{0,40}EU AI Act Art\.?\s*10", inv)
