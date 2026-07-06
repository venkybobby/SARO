"""Rule-pack version snapshot API (STORY-RPV-001).

Publish freezes the working-copy rule tables into an immutable, hash-chained
snapshot; reads expose the version list, diff, and chain verification as evidence
for an examiner ("which rule version did this attestation use?").

Auth posture:
  * publish — privileged admin action (super_admin | operator)
  * reads   — examiner/auditor evidence access (roles OR ai_auditor/compliance_lead
    personas), mirroring TRACE read access. Read-only; never grants write.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user, require_role, require_role_or_persona
import services.rule_pack_snapshot_service as snap_svc
from database import get_db
from models import RulePackSnapshot

router = APIRouter(prefix="/api/v1/rules/versions", tags=["rule-pack-versions"])

_require_read = require_role_or_persona(
    ("super_admin", "operator"), ("ai_auditor", "compliance_lead")
)


class PublishVersionRequest(BaseModel):
    version: Optional[str] = Field(
        default=None,
        description="Target semver (MAJOR.MINOR.PATCH). Omit to auto-increment the patch.",
    )
    include_legacy: Optional[bool] = Field(
        default=None,
        description="Include LEGACY_UNREVIEWED/status-less rows with a caveat. "
        "Defaults to the SARO_SNAPSHOT_INCLUDE_LEGACY server setting.",
    )


def _serialize(snap: RulePackSnapshot) -> dict:
    return {
        "id": str(snap.id),
        "version": snap.version,
        "content_hash": snap.content_hash,
        "prev_hash": snap.prev_hash,
        "record_hash": snap.record_hash,
        "framework_counts": snap.framework_counts,
        "includes_legacy": snap.includes_legacy,
        "caveat": snap.caveat,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Publish an immutable rule-pack version snapshot",
)
def publish_version(
    payload: PublishVersionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Freeze the current working copy into a new immutable snapshot (AC-1/AC-3)."""
    try:
        snap = snap_svc.publish_snapshot(
            db,
            version=payload.version,
            publisher_user_id=getattr(current_user, "id", None),
            include_legacy=payload.include_legacy,
        )
    except snap_svc.DraftRowsPresentError as exc:
        # AC-3: refuse with the listing of blocking rows.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "unvalidated_rows_block_publish",
                "blocking": exc.blocking,
            },
        )
    except snap_svc.EmptyPublishError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except snap_svc.InvalidVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return _serialize(snap)


@router.get(
    "", dependencies=[Depends(_require_read)], summary="List published snapshots"
)
def list_versions(db: Session = Depends(get_db)):
    snaps = snap_svc.list_snapshots(db)
    return {"versions": [_serialize(s) for s in snaps], "total": len(snaps)}


@router.get(
    "/latest",
    dependencies=[Depends(_require_read)],
    summary="Latest published snapshot",
)
def latest_version(db: Session = Depends(get_db)):
    snap = snap_svc.get_latest_snapshot(db)
    if snap is None:
        raise HTTPException(status_code=404, detail="no published rule-pack version")
    return _serialize(snap)


@router.get(
    "/diff",
    dependencies=[Depends(_require_read)],
    summary="Changelog: working copy vs latest snapshot",
)
def diff_versions(db: Session = Depends(get_db)):
    """Machine-readable added/updated/retired per framework (AC-4)."""
    return {"diff": snap_svc.diff_against_latest(db)}


@router.get(
    "/verify",
    dependencies=[Depends(_require_read)],
    summary="Verify the snapshot hash chain from genesis",
)
def verify_versions(db: Session = Depends(get_db)):
    """Recompute the chain; identify any tampered version by id (AC-5)."""
    return snap_svc.verify_chain(db)


@router.get(
    "/{version}",
    dependencies=[Depends(_require_read)],
    summary="Get one snapshot by version",
)
def get_version(version: str, db: Session = Depends(get_db)):
    snap = (
        db.query(RulePackSnapshot).filter(RulePackSnapshot.version == version).first()
    )
    if snap is None:
        raise HTTPException(status_code=404, detail=f"version {version} not found")
    return _serialize(snap)
