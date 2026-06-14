"""PT-007: NIST AI RMF coverage is mechanically derived, not asserted.

The 'mapped' claim must equal the set of subcategories the engine actually triggers
(_COMPLIANCE_TRIGGERS). If a rule-pack trigger is added/removed, the curated map must
move with it or this test fails — coverage can never silently over-claim.
"""
import re
from pathlib import Path

import pytest

from routers.reports import (
    NIST_COVERAGE_MAP_VERSION,
    _NIST_COVERAGE_MAP,
    _engine_mapped_subcategories,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent


def test_curated_mapped_equals_engine_derived():
    """The only subcategories marked 'mapped' are exactly those the engine triggers."""
    curated_mapped = {k for k, v in _NIST_COVERAGE_MAP.items() if v == "mapped"}
    derived = _engine_mapped_subcategories()
    assert curated_mapped == derived, (
        "NIST coverage drift: curated 'mapped' set != engine-derived set. "
        f"only-in-curated={curated_mapped - derived}, only-in-engine={derived - curated_mapped}"
    )


def test_engine_derived_set_is_nonempty_and_known():
    derived = _engine_mapped_subcategories()
    assert derived, "engine must map at least one NIST subcategory"
    # Anchor subcategories the buyer-facing coverage claim depends on.
    for anchor in ("GOVERN 4.2", "MAP 2.3", "MEASURE 2.5", "MANAGE 4.1"):
        assert anchor in derived


def test_map_is_complete_68():
    assert len(_NIST_COVERAGE_MAP) == 68


def test_partial_entries_have_rubric_basis():
    rubric = (ROOT / "docs" / "nist-coverage-rubric.md").read_text(encoding="utf-8")
    for sub_id, status in _NIST_COVERAGE_MAP.items():
        if status == "partial":
            assert sub_id in rubric, f"'partial' status for {sub_id} lacks a rubric basis row"


def test_no_unqualified_nist_aligned_claims_in_product_copy():
    pat = re.compile(r"NIST AI RMF[- ]?aligned", re.IGNORECASE)
    for path in [ROOT / "routers" / "reports.py", ROOT / "schemas.py"]:
        assert not pat.search(path.read_text(encoding="utf-8")), f"unqualified NIST-aligned claim in {path.name}"


def test_map_version_constant():
    assert NIST_COVERAGE_MAP_VERSION == "v1.0"
