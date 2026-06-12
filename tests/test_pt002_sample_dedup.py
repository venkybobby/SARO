"""PT-002: sample-finding persistence de-duplicates at the signal level.

One row per (sample_id, domain, matched_signal); identical re-matches collapse,
distinct samples are preserved, first-seen order retained.
"""
import pytest

from routers.scan import _dedupe_findings

pytestmark = pytest.mark.unit


def _f(sample_id, domain, signal, frag="x", weight=0.5):
    return {
        "sample_id": sample_id,
        "domain": domain,
        "matched_signal": signal,
        "matched_text_fragment": frag,
        "weight": weight,
    }


def test_identical_signal_matches_collapse():
    findings = [
        _f("s1", "Privacy & Security", "keyword:ssn"),
        _f("s1", "Privacy & Security", "keyword:ssn"),  # duplicate
        _f("s1", "Privacy & Security", "keyword:ssn", frag="other"),  # still same key
    ]
    out = _dedupe_findings(findings)
    assert len(out) == 1


def test_distinct_samples_preserved():
    findings = [
        _f("s1", "Privacy & Security", "keyword:ssn"),
        _f("s2", "Privacy & Security", "keyword:ssn"),
        _f("s1", "Misinformation", "keyword:hallucination"),
    ]
    out = _dedupe_findings(findings)
    assert len(out) == 3
    assert {f["sample_id"] for f in out} == {"s1", "s2"}


def test_first_seen_order_retained():
    findings = [
        _f("s2", "D", "sig"),
        _f("s1", "D", "sig"),
        _f("s2", "D", "sig"),  # dup of first
    ]
    out = _dedupe_findings(findings)
    assert [f["sample_id"] for f in out] == ["s2", "s1"]


def test_empty():
    assert _dedupe_findings([]) == []
