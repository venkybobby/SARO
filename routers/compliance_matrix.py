"""Compliance matrix API — sortable, filterable rows + CSV streaming export.

Endpoints:
    GET  /api/v1/compliance-matrix          list rows (sort + filter)
    GET  /api/v1/compliance-matrix/export   stream CSV (same filter/sort params)
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import AuditTrace, User
from services.compliance_matrix_service import (
    VALID_SORT_COLUMNS,
    VALID_SORT_DIRS,
    filter_matrix_rows,
    get_matrix_rows,
    sort_matrix_rows,
)
from services.hash_chain_service import compute_event_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance-matrix", tags=["compliance-matrix"])

_EXPORT_MAX_ROWS = 50_000

_CSV_COLUMNS = [
    "Regulation Name",
    "Article/Section",
    "Requirement Summary",
    "Risk Level",
    "Status",
    "Coverage %",
    "Last Updated",
    "Assigned Owner",
    "Notes",
]

_ROW_FIELD_MAP = [
    "regulation_name",
    "article_section",
    "requirement_summary",
    "risk_level",
    "status",
    "coverage_pct",
    "last_updated",
    "assigned_owner",
    "notes",
]


def _resolve_rows(
    db: Session,
    sort_by: str | None,
    sort_dir: str,
    filter_regulation: str | None,
    filter_risk_level: str | None,
) -> list[dict[str, Any]]:
    rows = get_matrix_rows(db)
    rows = filter_matrix_rows(rows, filter_regulation, filter_risk_level)
    rows = sort_matrix_rows(rows, sort_by, sort_dir)
    return rows


def _validate_sort_params(sort_by: str | None, sort_dir: str) -> None:
    if sort_by and sort_by not in VALID_SORT_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail={
                "field": "sort_by",
                "error": f"Invalid sort_by '{sort_by}'. Valid values: {sorted(VALID_SORT_COLUMNS)}",
            },
        )
    if sort_dir not in VALID_SORT_DIRS:
        raise HTTPException(
            status_code=400,
            detail={
                "field": "sort_dir",
                "error": f"Invalid sort_dir '{sort_dir}'. Valid values: asc, desc",
            },
        )


@router.get("", summary="List compliance matrix rows with optional sort and filter")
def list_matrix(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    sort_by: str | None = Query(default=None, description="risk_level | regulation_name | last_updated"),
    sort_dir: str = Query(default="asc", description="asc | desc"),
    filter_regulation: str | None = Query(default=None, alias="filter_regulation"),
    filter_risk_level: str | None = Query(default=None, alias="filter_risk_level"),
) -> dict[str, Any]:
    _validate_sort_params(sort_by, sort_dir)
    rows = _resolve_rows(db, sort_by, sort_dir, filter_regulation, filter_risk_level)
    return {"items": rows, "total": len(rows)}


@router.get("/export", summary="Export compliance matrix as CSV")
def export_matrix_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="asc"),
    filter_regulation: str | None = Query(default=None, alias="filter_regulation"),
    filter_risk_level: str | None = Query(default=None, alias="filter_risk_level"),
) -> StreamingResponse:
    _validate_sort_params(sort_by, sort_dir)
    rows = _resolve_rows(db, sort_by, sort_dir, filter_regulation, filter_risk_level)

    if len(rows) > _EXPORT_MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "export_too_large",
                "message": (
                    f"Export exceeds the {_EXPORT_MAX_ROWS:,} row limit. "
                    "Apply filters to reduce the dataset."
                ),
                "row_count": len(rows),
                "limit": _EXPORT_MAX_ROWS,
            },
        )

    # Log export action to audit chain
    try:
        _log_export_event(db, current_user, filter_regulation, filter_risk_level)
    except Exception as exc:
        logger.warning("Failed to log export audit event: %s", exc)

    today = date.today().isoformat()
    filename = f"saro-compliance-matrix-{today}.csv"

    def _generate():
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(_CSV_COLUMNS)
        yield buf.getvalue()

        for row in rows:
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator="\r\n")
            writer.writerow([
                row.get(field) if row.get(field) is not None else ""
                for field in _ROW_FIELD_MAP
            ])
            yield buf.getvalue()

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _log_export_event(
    db: Session,
    user: User,
    filter_regulation: str | None,
    filter_risk_level: str | None,
) -> None:
    """Append a MATRIX_EXPORT_CSV event to the tenant's audit trace chain."""
    import uuid as _uuid

    last = (
        db.query(AuditTrace)
        .filter(AuditTrace.audit_id.isnot(None))
        .order_by(AuditTrace.created_at.desc())
        .first()
    )
    prev_hash = last.event_hash if last and hasattr(last, "event_hash") else None

    event_data: dict[str, Any] = {
        "id": str(_uuid.uuid4()),
        "audit_id": "matrix_export",
        "gate_id": 0,
        "result": "MATRIX_EXPORT_CSV",
        "reason": (
            f"actor={user.email} "
            f"filter_regulation={filter_regulation} "
            f"filter_risk_level={filter_risk_level}"
        ),
        "created_at": str(__import__("datetime").datetime.utcnow().isoformat()),
    }
    event_hash = compute_event_hash(event_data, prev_hash)

    trace = AuditTrace(
        id=_uuid.UUID(event_data["id"]),
        audit_id=None,
        gate_id=0,
        gate_name="matrix_export",
        check_type="MATRIX_EXPORT_CSV",
        check_name="CSV Export",
        result="info",
        reason=event_data["reason"],
    )
    if hasattr(trace, "event_hash"):
        trace.event_hash = event_hash
    if hasattr(trace, "prev_hash"):
        trace.prev_hash = prev_hash
    db.add(trace)
    db.commit()
