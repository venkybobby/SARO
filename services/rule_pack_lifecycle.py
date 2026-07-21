"""Rule-pack draft → validate → publish lifecycle (STORY-376).

A DELTA on RPV-001/002, which already provide immutable, hash-chained,
publish-on-create snapshots and attestation pinning. This module adds the two
lifecycle pieces those did not cover:

* **Validation** — an explicit stage between an editable working copy and an
  immutable publish, reporting whether the candidate is fit to publish.
* **Version pinning** — a subscribing tenant binds to a published version;
  deprecation and rollback are re-pinning, never deletion.

Honesty about the validation stage: the pack's acceptance criterion asks
validation to report FP/FN against the Epic 18 completion bar. **That bar is
STORY-377 (a human-gated product decision) and its harness is STORY-378 —
neither is built.** Rather than fabricate an FP/FN number, ``validate_working_copy``
reports the *structural* readiness it can compute now (rows that would block a
publish, framework counts) and marks the FP/FN verdict explicitly
``bar_pending`` so a caller cannot mistake "not yet measured" for "passed".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import services.rule_pack_snapshot_service as snap_svc
import services.self_audit as self_audit
from config import settings

# Lifecycle states, in order.
DRAFT = "draft"
VALIDATION = "validation"
PUBLISHED = "published"
STATES = (DRAFT, VALIDATION, PUBLISHED)

# The FP/FN bar is not defined until STORY-377 is signed off. Validation reports
# this verdict for the FP/FN dimension so it is never confused with a pass.
BAR_PENDING = "bar_pending:STORY-377"


class LifecycleError(RuntimeError):
    pass


class PinTargetNotPublished(LifecycleError):
    """Refusing to pin a tenant to a version that was never published."""


def validate_working_copy(db: Any, include_legacy: Optional[bool] = None) -> dict:
    """Report whether the current working copy is fit to publish.

    Non-mutating: it inspects, it does not freeze anything. A publish is what
    freezes (``snap_svc.publish_snapshot``); this is the stage that tells a
    customer's compliance lead whether that publish would succeed and what it
    would contain, *before* they commit to an immutable version.
    """
    if include_legacy is None:
        include_legacy = settings.saro_snapshot_include_legacy

    manifest, counts, blocking, legacy_included, _content = snap_svc._build_manifest(
        db, include_legacy
    )
    latest = snap_svc.get_latest_snapshot(db)
    content_hash = snap_svc._content_hash(manifest)
    is_noop = latest is not None and latest.content_hash == content_hash

    structural_ok = not blocking and not is_noop

    return {
        "state": VALIDATION,
        "publishable": structural_ok,
        "framework_counts": counts,
        # Rows that would block a publish (DRAFT_UNVALIDATED / NULL status).
        "blocking_rows": blocking,
        "includes_legacy": legacy_included,
        "is_identical_to_latest": is_noop,
        # The FP/FN dimension cannot be evaluated yet — do not fabricate it.
        "fp_fn_verdict": BAR_PENDING,
        "fp_fn_note": (
            "False-positive/false-negative validation requires the completion "
            "bar (STORY-377, awaiting sign-off) and the confusion-matrix harness "
            "(STORY-378, not yet built). Structural readiness is reported; the "
            "FP/FN verdict is deferred, not passed."
        ),
        "content_hash_preview": content_hash,
    }


def pin_tenant_version(
    db: Any,
    *,
    tenant_id: uuid.UUID,
    version: str,
    actor: str,
    user_id: Optional[uuid.UUID] = None,
) -> dict:
    """Pin a tenant to a published rule-pack version. Audited (RULE_PACK_CHANGE).

    Refuses a version that was never published — a pin must reference an
    immutable snapshot that exists, or attestations produced under it could not
    be reproduced.
    """
    from models import RulePackSnapshot, TenantRulePackPin

    target = (
        db.query(RulePackSnapshot).filter(RulePackSnapshot.version == version).first()
    )
    if target is None:
        raise PinTargetNotPublished(
            f"rule-pack version {version!r} is not a published snapshot — "
            "pin only to a version that exists"
        )

    pin = (
        db.query(TenantRulePackPin)
        .filter(TenantRulePackPin.tenant_id == tenant_id)
        .first()
    )
    previous = pin.version if pin is not None else None
    if pin is None:
        pin = TenantRulePackPin(
            tenant_id=tenant_id, version=version, pinned_by_user_id=user_id
        )
        db.add(pin)
    else:
        pin.version = version
        pin.pinned_by_user_id = user_id
        pin.updated_at = datetime.now(tz=timezone.utc)

    # Audited: a version change alters which rules evaluate a tenant's evidence.
    # record_privileged commits, so the pin and its audit row land together.
    self_audit.record_privileged(
        db,
        tenant_id=self_audit.SYSTEM_TENANT_ID,
        actor=actor,
        action_class=self_audit.RULE_PACK_CHANGE,
        user_id=user_id,
        target_type="tenant_rule_pack_pin",
        target_id=str(tenant_id),
        metadata={
            "operation": "pin",
            "from_version": previous,
            "to_version": version,
            "content_hash": target.content_hash,
        },
    )
    return {"tenant_id": str(tenant_id), "version": version, "previous_version": previous}


def resolve_tenant_version(db: Any, tenant_id: uuid.UUID) -> Optional[str]:
    """The version a tenant evaluates against: its pin, else the latest published."""
    from models import TenantRulePackPin

    pin = (
        db.query(TenantRulePackPin)
        .filter(TenantRulePackPin.tenant_id == tenant_id)
        .first()
    )
    if pin is not None:
        return pin.version
    latest = snap_svc.get_latest_snapshot(db)
    return latest.version if latest is not None else None
