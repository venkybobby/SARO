"""Criteria-reproduction for a historical evidence record (STORY-RPV-002 AC-3/AC-4).

Given an attestation's evidence record, return the exact rule content of the
rule-pack version it was pinned to — the only link between an attestation and its
criteria under zero-payload retention. Records captured before versioning carry a
NULL pin and are reported verbatim as "PRE-VERSIONING" (never a guessed version).
Tenant-scoped: a caller only ever reaches its own tenant's evidence.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_role_or_persona
from database import get_db
from grc.evidence import get_evidence
import services.rule_pack_snapshot_service as snap_svc

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence-criteria"])

_require_read = require_role_or_persona(
    ("super_admin", "operator"), ("ai_auditor", "compliance_lead")
)


@router.get(
    "/{evidence_id}/criteria",
    dependencies=[Depends(_require_read)],
    summary="Reproduce the rule-pack criteria a historical evidence record was pinned to",
)
def evidence_criteria(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    tenant_id: uuid.UUID = current_user.tenant_id
    record = get_evidence(db, tenant_id=tenant_id, evidence_id=evidence_id)
    if record is None:
        # Generic 404 — no existence oracle across tenants.
        raise HTTPException(status_code=404, detail="evidence record not found")

    if record.rule_pack_version_id is None:
        # AC-4: honest-gap disclosure, stated verbatim, never backfilled.
        return {
            "evidence_id": str(record.id),
            "rule_pack_version_id": snap_svc.PRE_VERSIONING,
            "reproduction_available": False,
            "limitation": "This evidence record predates rule-pack versioning "
            "(PRE-VERSIONING); the exact criteria in force cannot be reproduced and "
            "are not backfilled with a guessed version.",
        }

    reproduction = snap_svc.reproduce_criteria(db, record.rule_pack_version_id)
    # Flag whether the snapshot's current content_hash still matches the value pinned
    # onto the record at capture time (tamper cross-check).
    reproduction["rule_pack_version_id"] = record.rule_pack_version_id
    reproduction["pinned_content_hash"] = record.rule_pack_content_hash
    reproduction["pin_matches_snapshot"] = (
        record.rule_pack_content_hash == reproduction["content_hash"]
    )
    reproduction["evidence_id"] = str(record.id)
    return reproduction
