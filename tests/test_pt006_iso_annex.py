"""PT-006: ISO 42001 annex generator — NOT-COVERED section, provenance, markers."""
import re

import pytest

from routers.reports import _ISO_ANNEX_TEMPLATE

pytestmark = pytest.mark.unit


def test_has_not_covered_section():
    assert "NOT COVERED BY SARO" in _ISO_ANNEX_TEMPLATE
    # Names the management-system clauses SARO does not evidence.
    for clause in ("Clause 4", "Clause 9", "Clause 10"):
        assert clause in _ISO_ANNEX_TEMPLATE


def test_has_both_marker_types():
    assert "[AUTO]" in _ISO_ANNEX_TEMPLATE
    assert "[HUMAN REVIEW REQUIRED]" in _ISO_ANNEX_TEMPLATE


def test_has_provenance_placeholders():
    keys = set(re.findall(r"{(\w+)}", _ISO_ANNEX_TEMPLATE))
    assert {"engine_version", "rule_pack_hash"} <= keys


def test_renders_with_provenance():
    fields = {k: "x" for k in re.findall(r"{(\w+)}", _ISO_ANNEX_TEMPLATE)}
    fields["rule_pack_hash"] = "a" * 64
    rendered = _ISO_ANNEX_TEMPLATE.format(**fields)
    assert "a" * 64 in rendered
    assert "NOT COVERED BY SARO" in rendered
