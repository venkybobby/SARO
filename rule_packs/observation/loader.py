"""Observation rule-pack loader (PREREQ-RP).

Third loader in the repo, and the split is deliberate — each serves a different
input shape and merging them would force one to fake the other's fields:

* ``rule_packs/loader.py``          — compliance-citation rules keyed to an
  already-content-triggered MIT domain.
* ``rule_packs/envelope_loader.py`` — the single model-ID allowlist rule (STORY-411).
* **this module**                   — multi-rule packs evaluated over
  :class:`adapters.contract.NormalizedInvocationRecord`, i.e. observation
  evidence from any adapter.

Layout: ``rule_packs/observation/{pack_dir}/{version}/pack.yaml``.

Packs are content-hashed so an attestation can name the exact pack version+hash
it was produced under (INV-7: published snapshots are immutable; a changed pack
is a new version, never an edit).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

_PACK_ROOT = Path(__file__).parent

REQUIRED_PACK_FIELDS = ("name", "version", "title", "domain_trigger", "obligation", "rules")
REQUIRED_RULE_FIELDS = ("rule_id", "title", "severity", "check")

# Checks this loader knows how to validate. A pack naming an unknown check is a
# load error, not a silently-skipped rule — a rule that never runs is worse than
# a pack that refuses to load, because it looks like coverage.
KNOWN_CHECKS = frozenset(
    {
        "required_fields",
        "truncation_is_incomplete",
        "error_present",
        "tool_not_in_allowlist",
        "tool_offered_not_allowed",
        "tool_policy_absent",
    }
)

SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


class ObservationPackLoadError(ValueError):
    """A pack failed validation — the engine does NOT start with a partial pack."""

    def __init__(self, pack_path: str, field_name: str, detail: str = "") -> None:
        self.pack_path = pack_path
        self.field_name = field_name
        super().__init__(
            f"ObservationPackLoadError: pack={pack_path!r} field={field_name!r}"
            + (f" — {detail}" if detail else "")
        )


@dataclass(frozen=True)
class ObservationRule:
    rule_id: str
    title: str
    severity: str
    check: str
    remediation: str = ""
    required_fields: tuple[str, ...] = ()
    unavailable_severity: Optional[str] = None


@dataclass(frozen=True)
class ObservationPack:
    name: str
    version: str
    title: str
    domain_trigger: str
    obligation: str
    rules: tuple[ObservationRule, ...]
    allowed_tools: tuple[str, ...] = ()
    path: str = ""
    _hash: str = field(default="", repr=False)

    @property
    def pack_ref(self) -> str:
        """Canonical reference, e.g. 'RP-OBS-COMPLETE@1.0.0'."""
        return f"{self.name}@{self.version}"

    @property
    def content_hash(self) -> str:
        return self._hash

    def with_allowed_tools(self, tools: list[str] | tuple[str, ...]) -> "ObservationPack":
        """Bind tenant tool policy for evaluation.

        Returns a NEW pack: the loaded pack is immutable, and tenant config must
        never mutate shared pack state (INV-3 — one tenant's policy leaking into
        another's evaluation would be a cross-tenant defect). The content hash is
        deliberately unchanged: the PACK is the same published artifact; the
        allowed-tool set is tenant input to it, recorded separately in evidence.
        """
        return ObservationPack(
            name=self.name,
            version=self.version,
            title=self.title,
            domain_trigger=self.domain_trigger,
            obligation=self.obligation,
            rules=self.rules,
            allowed_tools=tuple(tools),
            path=self.path,
            _hash=self._hash,
        )


def _pack_hash(raw: dict[str, Any]) -> str:
    """Deterministic SHA-256 over the pack's rule content.

    Excludes ``allowed_tools`` (tenant input, not pack content) so the same
    published pack hashes identically for every tenant.
    """
    payload = {
        "name": raw.get("name"),
        "version": raw.get("version"),
        "domain_trigger": raw.get("domain_trigger"),
        "rules": [
            {
                "rule_id": r.get("rule_id"),
                "check": r.get("check"),
                "severity": r.get("severity"),
                "required_fields": sorted(r.get("required_fields") or []),
                "unavailable_severity": r.get("unavailable_severity"),
            }
            for r in (raw.get("rules") or [])
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_pack(path: str | Path) -> ObservationPack:
    """Load and validate one observation pack YAML."""
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    for req in REQUIRED_PACK_FIELDS:
        if req not in raw:
            raise ObservationPackLoadError(str(path), req, "required field missing")

    rules: list[ObservationRule] = []
    seen_ids: set[str] = set()
    for entry in raw["rules"] or []:
        for req in REQUIRED_RULE_FIELDS:
            if req not in entry:
                raise ObservationPackLoadError(str(path), req, "required rule field missing")
        rule_id = str(entry["rule_id"])
        if rule_id in seen_ids:
            raise ObservationPackLoadError(str(path), "rule_id", f"duplicate {rule_id!r}")
        seen_ids.add(rule_id)

        check = str(entry["check"])
        if check not in KNOWN_CHECKS:
            raise ObservationPackLoadError(
                str(path), "check", f"unknown check {check!r} (known: {sorted(KNOWN_CHECKS)})"
            )
        severity = str(entry["severity"]).upper()
        if severity not in SEVERITIES:
            raise ObservationPackLoadError(str(path), "severity", f"unknown severity {severity!r}")
        unavailable_severity = entry.get("unavailable_severity")
        if unavailable_severity is not None:
            unavailable_severity = str(unavailable_severity).upper()
            if unavailable_severity not in SEVERITIES:
                raise ObservationPackLoadError(
                    str(path), "unavailable_severity", f"unknown severity {unavailable_severity!r}"
                )
        if check == "required_fields" and not entry.get("required_fields"):
            raise ObservationPackLoadError(
                str(path), "required_fields", f"rule {rule_id!r} uses required_fields but lists none"
            )

        rules.append(
            ObservationRule(
                rule_id=rule_id,
                title=str(entry["title"]),
                severity=severity,
                check=check,
                remediation=str(entry.get("remediation", "")).strip(),
                required_fields=tuple(entry.get("required_fields") or []),
                unavailable_severity=unavailable_severity,
            )
        )

    if not rules:
        raise ObservationPackLoadError(str(path), "rules", "pack contains no rules")

    return ObservationPack(
        name=str(raw["name"]),
        version=str(raw["version"]),
        title=str(raw["title"]),
        domain_trigger=str(raw["domain_trigger"]),
        obligation=str(raw["obligation"]).strip(),
        rules=tuple(rules),
        allowed_tools=tuple(raw.get("allowed_tools") or []),
        path=str(path),
        _hash=_pack_hash(raw),
    )


def load_genesis_packs() -> dict[str, ObservationPack]:
    """Load the shipped genesis packs, keyed by ``pack_ref``."""
    packs: dict[str, ObservationPack] = {}
    for pack_yaml in sorted(_PACK_ROOT.glob("*/*/pack.yaml")):
        pack = load_pack(pack_yaml)
        packs[pack.pack_ref] = pack
    return packs
