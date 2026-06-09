"""
Risk Register routes.

GET /api/v1/risks   — list risk items derived from completed audit scans
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Audit, ScanReport, User

router = APIRouter(prefix="/api/v1/risks", tags=["risks"])

_SEV_THRESHOLDS = [(70, "critical"), (50, "high"), (30, "medium"), (0, "low")]


def _score_to_severity(score: float | None) -> str:
    if score is None:
        return "medium"
    pct = round(score * 100) if score <= 1 else round(score)
    for threshold, label in _SEV_THRESHOLDS:
        if pct >= threshold:
            return label
    return "low"


@router.get("")
def list_risks(
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, le=500),
    skip: int = Query(default=0, ge=0),
) -> list[dict]:
    """
    Return completed audit scans mapped to risk register items.
    Scoped to the caller's tenant.
    """
    rows = (
        db.query(Audit, ScanReport)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .filter(Audit.tenant_id == current.tenant_id)
        .order_by(Audit.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    risks = []
    for i, (audit, report) in enumerate(rows):
        score = report.overall_risk_score if report else None
        title = (
            audit.dataset_name
            or (audit.prompt_text[:80] + "…" if audit.prompt_text and len(audit.prompt_text) > 80 else audit.prompt_text)
            or f"Scan {str(audit.id)[:8]}"
        )
        due = (audit.created_at.date() + timedelta(days=30)).isoformat() if audit.created_at else None
        risks.append({
            "id": f"R-{str(audit.id)[:6].upper()}",
            "audit_id": str(audit.id),
            "title": title,
            "category": "AI Quality",
            "severity": _score_to_severity(score),
            "owner": "—",
            "dueDate": due,
            "status": audit.status.capitalize() if audit.status else "Open",
            "risk_score": round(score * 100) if score is not None and score <= 1 else (round(score) if score is not None else None),
            "created_at": audit.created_at.isoformat() if audit.created_at else None,
        })
    return risks
