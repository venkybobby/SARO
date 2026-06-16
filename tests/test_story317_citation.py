"""STORY-317 — Framework citation source-of-truth tests.

AC coverage:
- The crosswalk is seeded and queryable for all three frameworks.
- A known clause/control resolves to VERIFIED.
- An unknown/invented clause resolves to UNVERIFIED (never confident fact).
- The verification function is callable by the audit pipeline.
"""

from __future__ import annotations

import pytest

from grc.citation import (
    UNVERIFIED,
    VERIFIED,
    crosswalk_version,
    frameworks_covered,
    load_crosswalk,
    verify_citation,
)

pytestmark = pytest.mark.unit


def test_seed_loads_and_covers_three_frameworks() -> None:
    assert crosswalk_version()
    assert len(load_crosswalk()) > 0
    assert frameworks_covered() >= {"NIST_AI_RMF", "EU_AI_ACT", "ISO_42001"}


@pytest.mark.parametrize(
    "framework,identifier",
    [
        ("NIST_AI_RMF", "GOVERN"),
        ("NIST_AI_RMF", "MEASURE-2.11"),
        ("EU_AI_ACT", "Art.9"),
        ("EU_AI_ACT", "Art.13"),
        ("ISO_42001", "Cl.9"),
        ("ISO_42001", "A.7"),
    ],
)
def test_known_citations_verified(framework, identifier) -> None:
    r = verify_citation(framework, identifier)
    assert r.status == VERIFIED
    assert r.description
    assert r.source_reference


def test_citation_lookup_is_normalized() -> None:
    # Case / spacing / dash variations still resolve.
    assert verify_citation("eu ai act", "art.9").status == VERIFIED
    assert verify_citation("nist-ai-rmf", "govern").status == VERIFIED


@pytest.mark.parametrize(
    "framework,identifier",
    [
        ("EU_AI_ACT", "Art.99"),  # invented article
        ("NIST_AI_RMF", "GOVERN-9.9"),  # invented subcategory
        ("ISO_42001", "Cl.42"),  # no such clause
        ("EU_AI_ACT", None),  # no identifier
        ("MADE_UP_FRAMEWORK", "X.1"),
    ],
)
def test_unknown_citations_unverified(framework, identifier) -> None:
    assert verify_citation(framework, identifier).status == UNVERIFIED


def test_callable_by_pipeline_returns_structured_result() -> None:
    r = verify_citation("EU_AI_ACT", "Art.10")
    assert r.framework and r.status in (VERIFIED, UNVERIFIED)
