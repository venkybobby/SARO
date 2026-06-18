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
from models import User
from services.compliance_matrix_service import (
    VALID_SORT_COLUMNS,
    VALID_SORT_DIRS,
    filter_matrix_rows,
    get_matrix_rows,
    sort_matrix_rows,
)

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


@router.get("/coverage", summary="Per-framework compliance coverage summary")
async def get_coverage_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """
    Returns per-framework compliance coverage percentages computed from
    the global compliance matrix rows (shared regulatory reference data —
    tenant-agnostic by design; see CHUB-010 note below).

    Each framework entry includes:
      - framework: framework name
      - total_rules: total rules in the matrix for this framework
      - covered: rules with status 'covered' or 'partial'
      - coverage_pct: percentage covered (0–100)
      - last_updated: most recent last_updated date for this framework
    """
    # CHUB-010: intentionally NOT tenant-scoped. get_matrix_rows() aggregates the
    # shared text of the regulations themselves — EUAIActRule (models.py:323) and
    # NISTControl (models.py:340), neither of which declares a tenant_id column —
    # plus static AIGP/ISO reference rows. Coverage is global-by-design reference
    # data, identical for every tenant; there is no per-tenant row here to leak.
    # Pinned by tests/test_chub010_tenant_scoping.py.
    rows = get_matrix_rows(db)

    # Group by regulation_name
    by_framework: dict[str, dict[str, Any]] = {}
    for row in rows:
        fw = row.get("regulation_name") or "Unknown"
        if fw not in by_framework:
            by_framework[fw] = {
                "framework": fw,
                "total_rules": 0,
                "covered": 0,
                "partial": 0,
                "not_covered": 0,
                "last_updated": None,
            }
        entry = by_framework[fw]
        entry["total_rules"] += 1

        row_status = (row.get("status") or "").lower()
        if row_status in ("covered", "compliant", "pass", "met"):
            entry["covered"] += 1
        elif row_status in ("partial", "partial_coverage", "in_progress", "warn"):
            entry["partial"] += 1
        else:
            entry["not_covered"] += 1

        lu = row.get("last_updated")
        if lu and (entry["last_updated"] is None or str(lu) > str(entry["last_updated"])):
            entry["last_updated"] = lu

    coverage_items = []
    for fw_entry in by_framework.values():
        total = fw_entry["total_rules"]
        covered = fw_entry["covered"] + fw_entry["partial"] * 0.5
        pct = round((covered / total * 100) if total else 0.0, 1)
        coverage_items.append({
            "framework": fw_entry["framework"],
            "total_rules": total,
            "covered": fw_entry["covered"],
            "partial": fw_entry["partial"],
            "not_covered": fw_entry["not_covered"],
            "coverage_pct": pct,
            "last_updated": str(fw_entry["last_updated"]) if fw_entry["last_updated"] else None,
        })

    # Sort by coverage_pct descending
    coverage_items.sort(key=lambda x: x["coverage_pct"], reverse=True)

    overall_total = sum(c["total_rules"] for c in coverage_items)
    overall_covered = sum(c["covered"] + c["partial"] * 0.5 for c in coverage_items)
    overall_pct = round((overall_covered / overall_total * 100) if overall_total else 0.0, 1)

    return {
        "frameworks": coverage_items,
        "overall_coverage_pct": overall_pct,
        "framework_count": len(coverage_items),
        "total_rules": overall_total,
    }


@router.get("", summary="List compliance matrix rows with optional sort and filter")
async def list_matrix(
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
async def export_matrix_csv(
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

    logger.info(
        "compliance_matrix_export actor=%s filter_regulation=%s filter_risk_level=%s rows=%d",
        current_user.email, filter_regulation, filter_risk_level, len(rows),
    )

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




@router.get("/summary", summary="Compliance matrix summary — alias for /coverage (React compat)")
async def get_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Alias of /coverage for React frontend compatibility."""
    return await get_coverage_summary(current_user, db)
