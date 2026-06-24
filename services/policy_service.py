"""STORY-401 (Epic 14): persistence + validation service for governance policies.

Tenant isolation is enforced app-layer here exactly as the rest of SARO does it
(every read/write filters by tenant_id) — see tests/test_tenant_isolation.py and
the STORY-400 recon findings. The `policies` table also carries an RLS policy
(migration 027) for parity with the rest of the schema, but — like every other
SARO table — that policy is inert at runtime (nothing sets app.current_tenant);
the app-layer filter is the real enforcement.

Cross-field validation reuses schemas.validate_trigger_config so the model layer
and the API schema never drift (STORY-401 AC-9). policy_version bumps by exactly
1 whenever a trigger-config field changes, and not otherwise (AC-7).

Invariant guard (Epic 14): deterministic, schema-only. No network or external
model call on any path in this module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Policy
from schemas import PolicyCreate, PolicyUpdate, validate_trigger_config

# The fields whose change bumps policy_version (STORY-401 AC-7).
TRIGGER_CONFIG_FIELDS: tuple[str, ...] = (
    "trigger_mode",
    "latency_budget_ms",
    "on_timeout",
    "sample_rate",
)


class PolicyNotFoundError(Exception):
    """Raised when a policy does not exist for the given tenant (incl. cross-tenant access)."""


def create_policy(db: Session, tenant_id: uuid.UUID, payload: PolicyCreate) -> Policy:
    """Persist a new policy for ``tenant_id``. policy_version starts at 1."""
    # Schema already validated the combo; re-assert defensively (single source of truth).
    validate_trigger_config(
        payload.trigger_mode,
        payload.latency_budget_ms,
        payload.on_timeout,
        payload.sample_rate,
    )
    policy = Policy(
        tenant_id=tenant_id,
        name=payload.name,
        trigger_mode=payload.trigger_mode,
        latency_budget_ms=payload.latency_budget_ms,
        on_timeout=payload.on_timeout,
        sample_rate=payload.sample_rate,
        policy_version=1,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_policy(
    db: Session, tenant_id: uuid.UUID, policy_id: uuid.UUID
) -> Policy | None:
    """Return the policy iff it belongs to ``tenant_id`` (cross-tenant reads return None)."""
    return (
        db.query(Policy)
        .filter(Policy.tenant_id == tenant_id, Policy.id == policy_id)
        .first()
    )


def list_policies(db: Session, tenant_id: uuid.UUID) -> list[Policy]:
    """All policies for ``tenant_id`` only."""
    return (
        db.query(Policy)
        .filter(Policy.tenant_id == tenant_id)
        .order_by(Policy.created_at)
        .all()
    )


def update_policy(
    db: Session, tenant_id: uuid.UUID, policy_id: uuid.UUID, payload: PolicyUpdate
) -> Policy:
    """Apply a partial update within ``tenant_id``.

    Unset fields keep their current value. The merged trigger-config is validated
    as a whole (so e.g. block→mirror without clearing budget/timeout is rejected —
    no silent misconfig). policy_version increments by 1 iff a trigger-config field
    actually changed value.
    """
    policy = get_policy(db, tenant_id, policy_id)
    if policy is None:
        raise PolicyNotFoundError(
            f"policy {policy_id} not found for tenant {tenant_id}"
        )

    changes = payload.model_dump(exclude_unset=True)

    # name is NOT NULL: an explicit null in a partial update is a misconfig, not a clear.
    if "name" in changes and changes["name"] is None:
        raise ValueError("name must not be set to null")

    # Resolve the post-update trigger-config from changes merged over current state.
    merged = {f: getattr(policy, f) for f in TRIGGER_CONFIG_FIELDS}
    merged.update({k: v for k, v in changes.items() if k in TRIGGER_CONFIG_FIELDS})
    validate_trigger_config(
        merged["trigger_mode"],
        merged["latency_budget_ms"],
        merged["on_timeout"],
        merged["sample_rate"],
    )

    trigger_changed = any(
        f in changes and changes[f] != getattr(policy, f) for f in TRIGGER_CONFIG_FIELDS
    )

    for field, value in changes.items():
        setattr(policy, field, value)
    if trigger_changed:
        policy.policy_version += 1
    policy.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(policy)
    return policy
