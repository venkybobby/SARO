"""MITRE ATLAS technique registry loader (STORY-AISEC-002).

Single source of truth for the ATLAS technique ids SARO references as evidence.
Every id is verified against upstream ATLAS data (see the pack header); the
registry lets the rest of the codebase resolve an id to its exact technique name
and validate that an id is real — so no finding can cite an invented technique
(AC-3). Evidence-only, Tier-3: this maps ids to names, it never asserts ATLAS
conformance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_ROOT = Path(__file__).parent


@dataclass(frozen=True)
class AtlasRegistry:
    name: str
    version: str
    source: str
    pack_hash: str
    _by_id: dict[str, str]

    def is_valid(self, technique_id: str | None) -> bool:
        """True if ``technique_id`` is a registered (verified-real) ATLAS id."""
        return bool(technique_id) and technique_id in self._by_id

    def resolve(self, technique_id: str | None) -> str | None:
        """Exact ATLAS technique name for ``technique_id``, or None if unknown.

        Never guesses: an unregistered id returns None rather than a fabricated
        name (AC-1 / AC-3 discipline)."""
        if not technique_id:
            return None
        return self._by_id.get(technique_id)

    def label(self, technique_id: str | None) -> str | None:
        """Evidence-shaped label, e.g. "MITRE ATLAS AML.T0054 (LLM Jailbreak)".

        Returns None for an unregistered id so callers never emit an unverified
        reference."""
        name = self.resolve(technique_id)
        if name is None:
            return None
        return f"MITRE ATLAS {technique_id} ({name})"


def _registry_hash(name: str, version: str, techniques: list[dict[str, Any]]) -> str:
    payload = {
        "name": name,
        "version": version,
        "techniques": sorted(
            ({"id": t["id"], "name": t["name"]} for t in techniques),
            key=lambda t: t["id"],
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_atlas_registry(version: str = "1.0.0") -> AtlasRegistry:
    """Load and index the verified ATLAS technique registry."""
    path = _REGISTRY_ROOT / version / "atlas_techniques.yaml"
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    techniques: list[dict[str, Any]] = raw.get("techniques", []) or []
    by_id = {t["id"]: t["name"] for t in techniques}
    return AtlasRegistry(
        name=raw.get("name", "ATLAS-REGISTRY"),
        version=str(raw.get("version", version)),
        source=raw.get("source", ""),
        pack_hash=_registry_hash(
            raw.get("name", "ATLAS-REGISTRY"),
            str(raw.get("version", version)),
            techniques,
        ),
        _by_id=by_id,
    )
