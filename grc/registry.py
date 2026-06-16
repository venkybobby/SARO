"""STORY-301 — AI system & agent registry (schemas + persistence service).

The registry is the single source of truth for every AI system and agent in the
portfolio. This module holds:

* the canonical in-memory representation (:class:`RegistryEntryData`) that the
  pure-logic stories — completeness (STORY-302) and tiering (STORY-303) — read,
  so they never need a database;
* the API request/response models;
* the persistence service (create / update / get / list) which writes an
  immutable audit-trail row on every create and update.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from models import GRCRegistryAudit, GRCRegistryEntry, User

ENTRY_TYPES = ("system", "agent")

# Fields that participate in the immutable audit-trail diff and in the
# completeness check. Kept here next to the model so the three stay aligned.
_GOVERNANCE_FIELDS = (
    "entry_type",
    "name",
    "version",
    "owner",
    "purpose",
    "data_sources",
    "model_version",
    "lifecycle_stage",
    "deployment_status",
    "domain",
    "interacts_with_humans",
    "makes_autonomous_decisions",
    "affects_individuals",
)


class RegistryEntryData(BaseModel):
    """DB-agnostic view of a registry entry consumed by 302/303."""

    id: uuid.UUID | None = None
    entry_type: str = "system"
    name: str | None = None
    version: str | None = None
    owner: str | None = None
    purpose: str | None = None
    data_sources: list[str] | None = None
    model_version: str | None = None
    lifecycle_stage: str | None = None
    deployment_status: str | None = None
    domain: str | None = None
    interacts_with_humans: bool | None = None
    makes_autonomous_decisions: bool | None = None
    affects_individuals: bool | None = None
    internal_tier: str | None = None
    eu_ai_act_category: str | None = None
    nist_impact_level: str | None = None

    model_config = {"from_attributes": True}


class RegistryEntryCreate(BaseModel):
    """Create payload. ``owner`` must be a non-empty named human (AC)."""

    entry_type: str = "system"
    name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    version: str | None = None
    purpose: str | None = None
    data_sources: list[str] | None = None
    model_version: str | None = None
    lifecycle_stage: str | None = None
    deployment_status: str | None = None
    domain: str | None = None
    interacts_with_humans: bool | None = None
    makes_autonomous_decisions: bool | None = None
    affects_individuals: bool | None = None

    @field_validator("owner", "name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be a non-empty value")
        return v.strip()

    @field_validator("entry_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in ENTRY_TYPES:
            raise ValueError(f"entry_type must be one of {ENTRY_TYPES}")
        return v


class RegistryEntryUpdate(BaseModel):
    """Partial update; every field optional but ``owner``/``name`` non-blank."""

    name: str | None = None
    owner: str | None = None
    version: str | None = None
    purpose: str | None = None
    data_sources: list[str] | None = None
    model_version: str | None = None
    lifecycle_stage: str | None = None
    deployment_status: str | None = None
    domain: str | None = None
    interacts_with_humans: bool | None = None
    makes_autonomous_decisions: bool | None = None
    affects_individuals: bool | None = None

    @field_validator("owner", "name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v.strip() if v is not None else v


class RegistryEntryOut(BaseModel):
    id: uuid.UUID
    entry_type: str
    name: str
    version: str | None
    owner: str | None
    purpose: str | None
    data_sources: list[str] | None
    model_version: str | None
    lifecycle_stage: str | None
    deployment_status: str | None
    domain: str | None
    interacts_with_humans: bool | None
    makes_autonomous_decisions: bool | None
    affects_individuals: bool | None
    internal_tier: str | None
    eu_ai_act_category: str | None
    nist_impact_level: str | None
    tiering_rationale: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


def to_data(entry: GRCRegistryEntry) -> RegistryEntryData:
    """ORM → DB-agnostic representation for the pure-logic stories."""
    return RegistryEntryData.model_validate(entry)


def _snapshot(entry: GRCRegistryEntry) -> dict[str, Any]:
    return {f: getattr(entry, f) for f in _GOVERNANCE_FIELDS}


def _write_audit(
    db: Session,
    *,
    entry: GRCRegistryEntry,
    action: str,
    actor: User | None,
    changes: dict[str, Any],
) -> None:
    """Append one immutable audit-trail row (never updated/deleted)."""
    db.add(
        GRCRegistryAudit(
            tenant_id=entry.tenant_id,
            entry_id=entry.id,
            action=action,
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            changes_json=changes,
        )
    )


def create_entry(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    payload: RegistryEntryCreate,
    actor: User | None,
) -> GRCRegistryEntry:
    """Persist a new entry and record a 'create' audit row."""
    entry = GRCRegistryEntry(
        tenant_id=tenant_id,
        created_by_id=getattr(actor, "id", None),
        **payload.model_dump(),
    )
    db.add(entry)
    db.flush()  # assign entry.id before writing the audit row
    _write_audit(
        db,
        entry=entry,
        action="create",
        actor=actor,
        changes={
            f: {"old": None, "new": getattr(entry, f)} for f in _GOVERNANCE_FIELDS
        },
    )
    db.commit()
    db.refresh(entry)
    return entry


def update_entry(
    db: Session,
    *,
    entry: GRCRegistryEntry,
    payload: RegistryEntryUpdate,
    actor: User | None,
) -> GRCRegistryEntry:
    """Apply a partial update and record an 'update' audit row with the diff."""
    before = _snapshot(entry)
    data = payload.model_dump(exclude_unset=True)
    changes: dict[str, Any] = {}
    for field, new in data.items():
        old = before.get(field)
        if old != new:
            setattr(entry, field, new)
            changes[field] = {"old": old, "new": new}
    if changes:
        entry.updated_by_id = getattr(actor, "id", None)
        entry.updated_at = datetime.now(tz=timezone.utc)
        _write_audit(db, entry=entry, action="update", actor=actor, changes=changes)
    db.commit()
    db.refresh(entry)
    return entry


def get_entry(
    db: Session, *, tenant_id: uuid.UUID, entry_id: uuid.UUID
) -> GRCRegistryEntry | None:
    return (
        db.query(GRCRegistryEntry)
        .filter(
            GRCRegistryEntry.id == entry_id,
            GRCRegistryEntry.tenant_id == tenant_id,
        )
        .first()
    )


def list_entries(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    tier: str | None = None,
    owner: str | None = None,
    lifecycle_stage: str | None = None,
) -> list[GRCRegistryEntry]:
    """List a tenant's active entries, filterable by tier/owner/lifecycle."""
    q = db.query(GRCRegistryEntry).filter(
        GRCRegistryEntry.tenant_id == tenant_id,
        GRCRegistryEntry.is_active.is_(True),
    )
    if tier is not None:
        q = q.filter(GRCRegistryEntry.internal_tier == tier)
    if owner is not None:
        q = q.filter(GRCRegistryEntry.owner == owner)
    if lifecycle_stage is not None:
        q = q.filter(GRCRegistryEntry.lifecycle_stage == lifecycle_stage)
    return q.order_by(GRCRegistryEntry.created_at.desc()).all()
