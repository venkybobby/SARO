"""Envelope-level rule pack loader (STORY-411).

Distinct from ``rule_packs/loader.py`` (compliance-citation rules attached to an
already-content-triggered MIT domain, no field for a model-ID list). This loads
``rule_packs/envelope/{version}/envelope_allowlist.yaml`` — a single rule
detecting a condition from the log ENVELOPE alone (``modelId``), never a body.

Directory layout expected:
  rule_packs/envelope/{version}/envelope_allowlist.yaml

YAML schema:
  name:            str
  version:         str
  rule_id:         str
  domain_trigger:  str   (must match a MIT_DOMAINS value)
  title:           str
  obligation:      str
  allowed_model_ids:          list[str]  (exact match)
  allowed_model_id_prefixes:  list[str]  (prefix match, checked only if no exact
                                          match; no regex)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

REQUIRED_FIELDS = (
    "name",
    "version",
    "rule_id",
    "domain_trigger",
    "title",
    "obligation",
)

_DEFAULT_PACK_PATH = (
    Path(__file__).parent / "envelope" / "1.0.0" / "envelope_allowlist.yaml"
)


class EnvelopeAllowlistLoadError(ValueError):
    """Raised when the envelope allowlist YAML fails validation."""

    def __init__(self, pack_path: str, field_name: str, detail: str = "") -> None:
        self.pack_path = pack_path
        self.field_name = field_name
        super().__init__(
            f"EnvelopeAllowlistLoadError: pack={pack_path!r} field={field_name!r}"
            + (f" — {detail}" if detail else "")
        )


@dataclass(frozen=True)
class EnvelopeAllowlistRule:
    rule_id: str
    title: str
    domain_trigger: str
    obligation: str
    version: str
    allowed_model_ids: list[str] = field(default_factory=list)
    allowed_model_id_prefixes: list[str] = field(default_factory=list)


def load_envelope_allowlist(
    path: str | Path = _DEFAULT_PACK_PATH,
) -> EnvelopeAllowlistRule:
    """Load and validate the envelope allowlist rule pack YAML.

    Raises EnvelopeAllowlistLoadError if required fields are missing — mirrors
    rule_packs/loader.py's "the engine does NOT start with a partial pack".
    """
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    for req in REQUIRED_FIELDS:
        if req not in raw:
            raise EnvelopeAllowlistLoadError(str(path), req, "required field missing")

    return EnvelopeAllowlistRule(
        rule_id=str(raw["rule_id"]),
        title=str(raw["title"]),
        domain_trigger=str(raw["domain_trigger"]),
        obligation=str(raw["obligation"]).strip(),
        version=str(raw["version"]),
        allowed_model_ids=list(raw.get("allowed_model_ids") or []),
        allowed_model_id_prefixes=list(raw.get("allowed_model_id_prefixes") or []),
    )


def is_model_allowed(rule: EnvelopeAllowlistRule, model_id: Optional[str]) -> bool:
    """Exact-then-prefix match (AC-2.1). No regex."""
    if not model_id:
        return False
    if model_id in rule.allowed_model_ids:
        return True
    return any(model_id.startswith(p) for p in rule.allowed_model_id_prefixes)


def envelope_pack_hash(rule: EnvelopeAllowlistRule) -> str:
    """Deterministic SHA-256 of the pack's content — matches engine.py's existing
    hash-attribution style (SARO-006), kept separate from the content-scan
    rule_pack_hash so no other audit's existing hash-chain evidence changes
    meaning."""
    payload = {
        "rule_id": rule.rule_id,
        "version": rule.version,
        "domain_trigger": rule.domain_trigger,
        "allowed_model_ids": sorted(rule.allowed_model_ids),
        "allowed_model_id_prefixes": sorted(rule.allowed_model_id_prefixes),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
