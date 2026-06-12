"""
Risk Register routes.

GET    /api/v1/risks          — list risk items derived from completed audit scans
GET    /api/v1/risks/{id}     — fetch a single risk item by its R-XXXXXX id
PATCH  /api/v1/risks/{id}     — update owner / status override for a risk
DELETE /api/v1/risks/{id}     — soft-delete (dismiss) a risk
POST   /api/v1/risks/bulk     — apply a bulk action (assign owner / change status / delete)
"""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from auth import get_current_user, require_write_persona
from database import get_db
from models import Audit, RiskMetadata, ScanReport, User
from schemas import RiskBulkActionIn, RiskUpdateIn

router = APIRouter(prefix="/api/v1/risks", tags=["risks"])

# PT-009 (FND-010): audit UUID prefixes are hex only. Validating the stripped
# prefix prevents LIKE wildcard injection (%, _ match arbitrary same-tenant rows).
_HEX_PREFIX = re.compile(r"[0-9a-f]{1,32}")

_SEV_THRESHOLDS = [(70, "critical"), (50, "high"), (30, "medium"), (0, "low")]


def _score_to_severity(score: float | None) -> str:
    if score is None:
        return "medium"
    pct = round(score * 100) if score <= 1 else round(score)
    for threshold, label in _SEV_THRESHOLDS:
        if pct >= threshold:
            return label
    return "low"


def _risk_id(audit: Audit) -> str:
    return f"R-{str(audit.id)[:6].upper()}"


def _build_risk_dict(audit: Audit, report: ScanReport | None, meta: RiskMetadata | None) -> dict:
    score = report.overall_risk_score if report else None
    title = (
        audit.dataset_name
        or (audit.prompt_text[:80] + "…" if audit.prompt_text and len(audit.prompt_text) > 80 else audit.prompt_text)
        or f"Scan {str(audit.id)[:8]}"
    )
    due = (audit.created_at.date() + timedelta(days=30)).isoformat() if audit.created_at else None
    return {
        "id": _risk_id(audit),
        "audit_id": str(audit.id),
        "title": title,
        "category": "AI Quality",
        "severity": _score_to_severity(score),
        "owner": (meta.owner if meta and meta.owner else "—"),
        "dueDate": due,
        "status": (meta.status_override if meta and meta.status_override else (audit.status.capitalize() if audit.status else "Open")),
        "risk_score": round(score * 100) if score is not None and score <= 1 else (round(score) if score is not None else None),
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
    }


def _find_audit_with_meta(
    db: Session, tenant_id, risk_id: str
) -> tuple[Audit, ScanReport | None, RiskMetadata | None] | None:
    prefix = risk_id.removeprefix("R-").removeprefix("r-").lower()
    if not _HEX_PREFIX.fullmatch(prefix):
        return None
    row = (
        db.query(Audit, ScanReport, RiskMetadata)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .outerjoin(RiskMetadata, RiskMetadata.audit_id == Audit.id)
        .filter(Audit.tenant_id == tenant_id)
        .filter(cast(Audit.id, String).like(f"{prefix}%"))
        .first()
    )
    return row  # type: ignore[return-value]


def _get_or_create_meta(db: Session, audit_id) -> RiskMetadata:
    meta = db.query(RiskMetadata).filter(RiskMetadata.audit_id == audit_id).first()
    if meta is None:
        meta = RiskMetadata(audit_id=audit_id)
        db.add(meta)
    return meta


@router.get("")
def list_risks(
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, le=500),
    skip: int = Query(default=0, ge=0),
) -> list[dict]:
    """
    Return completed audit scans mapped to risk register items.
    Scoped to the caller's tenant. Risks dismissed via DELETE are excluded.
    """
    rows = (
        db.query(Audit, ScanReport, RiskMetadata)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .outerjoin(RiskMetadata, RiskMetadata.audit_id == Audit.id)
        .filter(Audit.tenant_id == current.tenant_id)
        .order_by(Audit.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        _build_risk_dict(audit, report, meta)
        for audit, report, meta in rows
        if not (meta and meta.dismissed)
    ]


@router.get("/{risk_id}")
def get_risk(
    risk_id: str,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Fetch a single risk register item by its R-XXXXXX id."""
    found = _find_audit_with_meta(db, current.tenant_id, risk_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    audit, report, meta = found
    if meta and meta.dismissed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    return _build_risk_dict(audit, report, meta)


@router.patch("/{risk_id}")
def update_risk(
    risk_id: str,
    payload: RiskUpdateIn,
    current: Annotated[User, Depends(require_write_persona)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Update the owner and/or status override for a risk register item.

    PT-009 (FND-009): mutation requires a write persona (allowlist); ai_auditor 403.
    """
    found = _find_audit_with_meta(db, current.tenant_id, risk_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    audit, report, meta = found

    meta = _get_or_create_meta(db, audit.id)
    if payload.owner is not None:
        meta.owner = payload.owner or None
    if payload.status is not None:
        meta.status_override = payload.status or None
    db.commit()
    db.refresh(meta)

    return _build_risk_dict(audit, report, meta)


@router.delete("/{risk_id}")
def delete_risk(
    risk_id: str,
    current: Annotated[User, Depends(require_write_persona)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Soft-delete (dismiss) a risk register item.

    The underlying audit/scan record is preserved for audit-trail integrity
    (read-only audit posture) — only the risk register entry is hidden.
    """
    found = _find_audit_with_meta(db, current.tenant_id, risk_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    audit, _report, _meta = found

    meta = _get_or_create_meta(db, audit.id)
    meta.dismissed = True
    db.commit()

    return {"id": _risk_id(audit), "dismissed": True}


@router.post("/bulk")
def bulk_action(
    payload: RiskBulkActionIn,
    current: Annotated[User, Depends(require_write_persona)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Apply a bulk action (assign owner / change status / delete) to multiple risks.

    PT-009 (FND-009): mutation requires a write persona (allowlist); ai_auditor 403.
    """
    if payload.action == "assign_owner" and not payload.owner:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="owner is required for assign_owner")
    if payload.action == "change_status" and not payload.status:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="status is required for change_status")

    updated: list[str] = []
    not_found: list[str] = []

    for risk_id in payload.ids:
        found = _find_audit_with_meta(db, current.tenant_id, risk_id)
        if found is None:
            not_found.append(risk_id)
            continue
        audit, _report, _meta = found
        meta = _get_or_create_meta(db, audit.id)

        if payload.action == "assign_owner":
            meta.owner = payload.owner
        elif payload.action == "change_status":
            meta.status_override = payload.status
        elif payload.action == "delete":
            meta.dismissed = True

        updated.append(_risk_id(audit))

    db.commit()

    return {"action": payload.action, "updated": updated, "not_found": not_found}
