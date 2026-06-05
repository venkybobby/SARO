"""
Compliance label governance service (SAR-002 / FR-EVF-16).

Single source of truth for all compliance framework labels.
All UI components must call get_label() — never hardcode framework strings.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "compliance_label_registry.json"
_registry: dict | None = None


def _load() -> dict:
    global _registry
    if _registry is None:
        with open(_REGISTRY_PATH) as f:
            _registry = json.load(f)
    return _registry


def get_label(framework: str) -> dict:
    """Return the full label config for a framework key (EU_AI_ACT, NIST_AI_RMF, AIGP, ISO_42001)."""
    reg = _load()
    fw = reg["frameworks"].get(framework)
    if not fw:
        raise ValueError(f"Unknown framework: {framework!r}. Valid: {list(reg['frameworks'])}")
    tier = fw["tier"]
    if tier == 1:
        text = fw.get("tier1_text") or f"Externally Reviewed — QCO {fw.get('qco_reference')} | {fw.get('sme_firm')} | {fw.get('qco_expiry')}"
    elif tier == 2:
        text = fw["tier2_text"]
    else:
        text = fw["tier3_text"]
    return {
        "framework": framework,
        "display_name": fw["display_name"],
        "tier": tier,
        "label_text": text,
        "qco_reference": fw.get("qco_reference"),
        "qco_expiry": fw.get("qco_expiry"),
        "badge_color": {1: "#16a34a", 2: "#ca8a04", 3: "#64748b"}.get(tier, "#64748b"),
        "badge_icon": {1: "✅", 2: "⏳", 3: "🔒"}.get(tier, "🔒"),
        "badge_short": {1: "EXTERNALLY REVIEWED", 2: "UNDER REVIEW", 3: "INTERNAL ONLY"}.get(tier, "INTERNAL ONLY"),
    }


def get_all_labels() -> list[dict]:
    """Return label config for all 4 frameworks."""
    reg = _load()
    return [get_label(k) for k in reg["frameworks"]]


def get_disclaimer() -> str:
    """Return the global disclaimer text for PDF exports and reports."""
    return _load()["global_disclaimer"]


def get_claims_matrix_header() -> str:
    return "These mappings reflect SARO's internal assessment. Independent SME validation is in progress."


def upgrade_to_tier1(
    framework: str,
    qco_reference: str,
    sme_firm: str,
    qco_expiry: str,
    *,
    write_to_disk: bool = True,
) -> None:
    """
    Upgrade a framework label to Tier 1 when a QCO is issued.

    When called from the EVF QCO publish cascade, pass ``write_to_disk=False``
    so the in-memory cache is updated immediately but the registry file is NOT
    modified as a side effect of a DB transaction. A separate admin action or
    deploy step should persist the tier upgrade to disk.

    When called directly via the admin API or a manual upgrade command, leave
    ``write_to_disk=True`` (the default) to persist the change to the JSON file.
    """
    global _registry
    reg = _load()
    if framework not in reg["frameworks"]:
        raise ValueError(f"Unknown framework: {framework!r}")
    reg["frameworks"][framework].update({
        "tier": 1,
        "qco_reference": qco_reference,
        "sme_firm": sme_firm,
        "qco_expiry": qco_expiry,
        "tier1_text": f"Externally Reviewed — QCO {qco_reference} | {sme_firm} | {qco_expiry}",
    })
    _registry = reg
    if write_to_disk:
        with open(_REGISTRY_PATH, "w") as f:
            json.dump(reg, f, indent=2)
        logger.info("Tier 1 upgrade persisted to disk: framework=%s qco=%s", framework, qco_reference)
    else:
        logger.info("Tier 1 upgrade applied in-memory only: framework=%s qco=%s", framework, qco_reference)
