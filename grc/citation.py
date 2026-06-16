"""STORY-317 — Framework citation source-of-truth + verification.

A fabricated clause citation is the failure mode that burns auditor trust — it
bit SARO once already. Framework mappings must resolve against a maintained,
authoritative crosswalk and be flagged ``VERIFIED`` / ``UNVERIFIED``; the system
must never assert a clause it cannot resolve.

The crosswalk is human-maintainable, versioned seed data
(``grc/data/framework_crosswalk.json``). Each entry carries a framework, an
identifier, a plain-language description and (via ``sources``) a source
reference. We deliberately do **not** hand-author clause numbers we cannot
source — the seed contains only identifiers traceable to the framework texts.

Consumed by STORY-309's regulatory-claim check (and later STORY-316's crosswalk).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from grc.contract import VERIFICATION_STATUSES

VERIFIED, UNVERIFIED = VERIFICATION_STATUSES  # ("VERIFIED", "UNVERIFIED")

_CROSSWALK_PATH = Path(__file__).parent / "data" / "framework_crosswalk.json"


class CrosswalkEntry(BaseModel):
    framework: str
    identifier: str
    description: str
    source_reference: str | None = None


class CitationResult(BaseModel):
    framework: str
    identifier: str | None
    status: str
    description: str | None = None
    source_reference: str | None = None


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    with open(_CROSSWALK_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def crosswalk_version() -> str:
    return _raw()["version"]


@lru_cache(maxsize=1)
def _index() -> dict[tuple[str, str], CrosswalkEntry]:
    raw = _raw()
    sources = raw.get("sources", {})
    idx: dict[tuple[str, str], CrosswalkEntry] = {}
    for e in raw["entries"]:
        fw = e["framework"]
        ident = e["identifier"]
        idx[(_norm_fw(fw), _norm_id(ident))] = CrosswalkEntry(
            framework=fw,
            identifier=ident,
            description=e["description"],
            source_reference=sources.get(fw),
        )
    return idx


def _norm_fw(framework: str) -> str:
    return framework.strip().upper().replace(" ", "_").replace("-", "_")


def _norm_id(identifier: str) -> str:
    return identifier.strip().upper().replace(" ", "")


def load_crosswalk() -> list[CrosswalkEntry]:
    """Return all crosswalk entries (for reporting / data tests)."""
    return list(_index().values())


def frameworks_covered() -> set[str]:
    return {e.framework for e in _index().values()}


def resolve(framework: str, identifier: str) -> CrosswalkEntry | None:
    return _index().get((_norm_fw(framework), _norm_id(identifier)))


def verify_citation(framework: str, identifier: str | None) -> CitationResult:
    """Resolve a citation against the crosswalk.

    Returns ``VERIFIED`` with the entry's description/source when the
    framework+identifier resolves; otherwise ``UNVERIFIED`` — which must never
    be emitted as confident fact by a consumer.
    """
    if identifier:
        entry = resolve(framework, identifier)
        if entry is not None:
            return CitationResult(
                framework=entry.framework,
                identifier=entry.identifier,
                status=VERIFIED,
                description=entry.description,
                source_reference=entry.source_reference,
            )
    return CitationResult(framework=framework, identifier=identifier, status=UNVERIFIED)
