"""CHUB-004: Compliance Hub readiness checklist service.

The item *catalog* is code-defined here (Out of Scope: editing the catalog via UI).
Two item kinds:

  - manual   : user-toggled; ``completed`` persisted per-tenant in
               ``compliance_readiness_items`` and survives reload.
  - derived  : read-only; ``completed`` is computed from a real source at read
               time (never written). If the source is unavailable, the item
               resolves to ``unknown`` (completed=None) — never silently checked.

All reads/writes are scoped to a tenant via the ``tenant_id`` filter.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from models import AIMSDocument, ComplianceReadinessItem

# ── Code-defined catalog ──────────────────────────────────────────────────────

# kind: "manual" | "derived". Derived items carry a `source` resolver key and a
# human-readable `source_label` shown as a tooltip in the UI.
READINESS_ITEMS: list[dict[str, Any]] = [
    {
        "key": "dpa_in_place",
        "label": "Data processing agreements in place",
        "kind": "manual",
    },
    {
        "key": "ai_systems_registered",
        "label": "AI systems registered in inventory",
        "kind": "derived",
        "source": "aims_inventory",
        "source_label": "Derived from AIMS inventory records (ISO 42001 evidence)",
    },
    {
        "key": "risk_assessments_completed",
        "label": "Risk assessments completed for high-risk systems",
        "kind": "manual",
    },
    {
        "key": "human_oversight_documented",
        "label": "Human oversight controls documented",
        "kind": "manual",
    },
    # NOTE: "Incident response plan reviewed" ↔ ADR-004 critical-gap status is a
    # planned derived mapping; kept manual until a tenant-scoped gap source exists.
    {
        "key": "incident_response_reviewed",
        "label": "Incident response plan reviewed",
        "kind": "manual",
    },
    {
        "key": "annual_review_scheduled",
        "label": "Annual compliance review scheduled",
        "kind": "manual",
    },
]

_ITEMS_BY_KEY = {it["key"]: it for it in READINESS_ITEMS}

MANUAL_KEYS = frozenset(it["key"] for it in READINESS_ITEMS if it["kind"] == "manual")


def is_manual_item(item_key: str) -> bool:
    it = _ITEMS_BY_KEY.get(item_key)
    return bool(it) and it["kind"] == "manual"


def item_exists(item_key: str) -> bool:
    return item_key in _ITEMS_BY_KEY


# ── Derived resolvers ─────────────────────────────────────────────────────────


def _resolve_aims_inventory(db: Session, tenant_id: uuid.UUID) -> bool | None:
    """completed=True if the tenant has ≥1 AIMS inventory record; None if the
    source can't be read (never default to checked)."""
    try:
        count = (
            db.query(AIMSDocument).filter(AIMSDocument.tenant_id == tenant_id).count()
        )
        return count > 0
    except Exception:
        return None


_DERIVED_RESOLVERS = {
    "aims_inventory": _resolve_aims_inventory,
}


def _resolve_derived(
    db: Session, tenant_id: uuid.UUID, item: dict[str, Any]
) -> bool | None:
    resolver = _DERIVED_RESOLVERS.get(item.get("source", ""))
    if resolver is None:
        return None
    return resolver(db, tenant_id)


# ── Public API ────────────────────────────────────────────────────────────────


def get_readiness(db: Session, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return the full checklist for a tenant: manual items from the store
    (default unchecked), derived items computed from their source."""
    stored = {
        row.item_key: row.completed
        for row in db.query(ComplianceReadinessItem)
        .filter(ComplianceReadinessItem.tenant_id == tenant_id)
        .all()
    }

    result: list[dict[str, Any]] = []
    for item in READINESS_ITEMS:
        if item["kind"] == "derived":
            completed = _resolve_derived(db, tenant_id, item)
            result.append(
                {
                    "key": item["key"],
                    "label": item["label"],
                    "kind": "derived",
                    "completed": completed,
                    "editable": False,
                    "source": item.get("source_label"),
                }
            )
        else:
            result.append(
                {
                    "key": item["key"],
                    "label": item["label"],
                    "kind": "manual",
                    "completed": bool(stored.get(item["key"], False)),
                    "editable": True,
                    "source": None,
                }
            )
    return result


def set_readiness(
    db: Session, tenant_id: uuid.UUID, item_key: str, completed: bool
) -> dict[str, Any]:
    """Upsert a manual item's completed state for a tenant. Raises ValueError for
    unknown keys or attempts to toggle a derived (read-only) item."""
    if not item_exists(item_key):
        raise ValueError(f"Unknown readiness item '{item_key}'")
    if not is_manual_item(item_key):
        raise ValueError(f"Item '{item_key}' is derived and cannot be toggled manually")

    row = (
        db.query(ComplianceReadinessItem)
        .filter(
            ComplianceReadinessItem.tenant_id == tenant_id,
            ComplianceReadinessItem.item_key == item_key,
        )
        .first()
    )
    if row is None:
        row = ComplianceReadinessItem(
            tenant_id=tenant_id, item_key=item_key, completed=bool(completed)
        )
        db.add(row)
    else:
        row.completed = bool(completed)
    db.commit()

    return {
        "key": item_key,
        "label": _ITEMS_BY_KEY[item_key]["label"],
        "kind": "manual",
        "completed": bool(completed),
        "editable": True,
        "source": None,
    }
