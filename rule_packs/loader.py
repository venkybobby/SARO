"""
SARO Rule Pack Loader — CF-02
==============================
Loads, validates, and caches versioned YAML rule packs from rule_packs/.

Directory layout expected:
  rule_packs/{framework-slug}/{version}/rules.yaml

YAML schema per pack:
  name:    str       (e.g. "eu-ai-act")
  version: str       (semver, e.g. "1.0.0")
  rules:
    - rule_id:        str
      title:          str
      domain_trigger: str   (must match a MIT_DOMAINS value)
      obligation:     str
      fixtures:
        positive_text: str
        negative_text: str
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PACK_DIR = Path(__file__).parent

REQUIRED_PACK_FIELDS = {"name", "version", "rules"}
REQUIRED_RULE_FIELDS = ("rule_id", "title", "domain_trigger", "obligation")


class RulePackLoadError(ValueError):
    """Raised when a YAML rule pack fails validation."""

    def __init__(self, pack_path: str, field_name: str, detail: str = "") -> None:
        self.pack_path = pack_path
        self.field_name = field_name
        super().__init__(
            f"RulePackLoadError: pack={pack_path!r} field={field_name!r}"
            + (f" — {detail}" if detail else "")
        )


@dataclass
class RuleFixture:
    positive_text: str
    negative_text: str


@dataclass
class Rule:
    rule_id: str
    title: str
    domain_trigger: str
    obligation: str
    fixture: RuleFixture | None = None


@dataclass
class RulePack:
    name: str
    version: str
    loaded_at: datetime
    path: str
    rules: list[Rule] = field(default_factory=list)

    @property
    def pack_ref(self) -> str:
        """Canonical reference string: e.g. 'eu-ai-act@1.0.0'."""
        return f"{self.name}@{self.version}"

    def rules_for_domain(self, domain: str) -> list[Rule]:
        return [r for r in self.rules if r.domain_trigger == domain]

    def to_version_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "loaded_at": self.loaded_at.isoformat(),
        }


def load_pack(path: str | Path) -> RulePack:
    """
    Load and validate a single rule pack YAML file.

    Raises RulePackLoadError if required fields are missing or invalid.
    The engine does NOT start with a partial pack.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    for req in REQUIRED_PACK_FIELDS:
        if req not in raw:
            raise RulePackLoadError(str(path), req, "required top-level field missing")

    rules: list[Rule] = []
    for i, rule_raw in enumerate(raw.get("rules", [])):
        for req in REQUIRED_RULE_FIELDS:
            if req not in rule_raw:
                raise RulePackLoadError(str(path), req, f"missing in rule index {i}")

        fixture = None
        if "fixtures" in rule_raw:
            fixture = RuleFixture(
                positive_text=rule_raw["fixtures"].get("positive_text", ""),
                negative_text=rule_raw["fixtures"].get("negative_text", ""),
            )

        rules.append(
            Rule(
                rule_id=rule_raw["rule_id"],
                title=rule_raw["title"],
                domain_trigger=rule_raw["domain_trigger"],
                obligation=str(rule_raw["obligation"]).strip(),
                fixture=fixture,
            )
        )

    return RulePack(
        name=raw["name"],
        version=str(raw["version"]),
        loaded_at=datetime.now(tz=timezone.utc),
        path=str(path),
        rules=rules,
    )


def validate_pack(pack: RulePack) -> None:
    """
    Validate a loaded pack's structure.

    Raises RulePackLoadError if any rule is missing required fields.
    """
    for rule in pack.rules:
        for attr in ("rule_id", "title", "domain_trigger", "obligation"):
            if not getattr(rule, attr, None):
                raise RulePackLoadError(pack.path, attr, f"empty value in rule {rule.rule_id!r}")


def list_packs(base_dir: str | Path | None = None) -> list[Path]:
    """Return all rules.yaml paths found under base_dir (default: rule_packs/)."""
    base = Path(base_dir) if base_dir else _PACK_DIR
    return sorted(base.rglob("rules.yaml"))


def load_all_packs(base_dir: str | Path | None = None) -> list[RulePack]:
    """
    Load every rules.yaml found under base_dir.

    Missing packs warn and continue (preserves existing engine.py behaviour on
    DB read failures).  A malformed pack raises RulePackLoadError immediately.
    """
    packs: list[RulePack] = []
    for yaml_path in list_packs(base_dir):
        try:
            pack = load_pack(yaml_path)
            validate_pack(pack)
            packs.append(pack)
            logger.info("Loaded rule pack %s from %s", pack.pack_ref, yaml_path)
        except RulePackLoadError:
            raise
        except Exception as exc:
            logger.warning("Could not load rule pack at %s: %s", yaml_path, exc)
    logger.info("Rule pack loader: %d packs loaded total", len(packs))
    return packs


def build_domain_trigger_map(
    packs: list[RulePack],
) -> dict[str, list[dict[str, Any]]]:
    """
    Build a mapping {domain_trigger → [trigger_dicts]} from all loaded packs.
    This is the drop-in replacement for the hardcoded _COMPLIANCE_TRIGGERS dict.
    Each trigger dict includes rule_pack metadata for AuditTrace.detail_json.
    """
    result: dict[str, list[dict[str, Any]]] = {}
    for pack in packs:
        for rule in pack.rules:
            entry = {
                "framework": _pack_name_to_framework(pack.name),
                "rule_id": rule.rule_id,
                "title": rule.title,
                "triggered_by": _triggered_by_label(rule.domain_trigger),
                "obligation": rule.obligation,
                "rule_pack": {
                    "name": pack.name,
                    "version": pack.version,
                    "loaded_at": pack.loaded_at.isoformat(),
                },
            }
            result.setdefault(rule.domain_trigger, []).append(entry)
    return result


def _pack_name_to_framework(name: str) -> str:
    mapping = {
        "eu-ai-act": "EU AI Act",
        "nist-ai-rmf": "NIST AI RMF",
        "aigp": "AIGP",
        "iso-42001": "ISO 42001",
    }
    return mapping.get(name, name)


def _triggered_by_label(domain: str) -> str:
    labels = {
        "Discrimination & Toxicity": "bias/discrimination detection",
        "Privacy & Security": "PII/sensitive data detected",
        "Misinformation": "misinformation/hallucination signals",
        "Malicious Use": "malicious use indicators",
        "AI System Safety": "safety failure indicators",
        "Human-Computer Interaction": "deceptive interaction patterns",
        "Socioeconomic & Environmental": "socioeconomic impact signals",
    }
    return labels.get(domain, domain.lower())
