"""Compliance matrix service — sort, filter, and aggregate framework rows.

Aggregates rows from EUAIActRule and NISTControl ORM tables plus static
AIGP/ISO 42001 entries.  All sort/filter logic lives here so the router
and the Streamlit tab stay thin.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from models import EUAIActRule, NISTControl

# ── Ordinal risk level map (Critical > High > Medium > Low > N/A) ─────────────

RISK_ORDINAL: dict[str, int] = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "N/A": 0,
}

_SEVERITY_TO_RISK: dict[int, str] = {5: "Critical", 4: "High", 3: "Medium", 2: "Low", 1: "Low"}

# Static rows for AIGP and ISO 42001 (not yet in DB tables)
_STATIC_ROWS: list[dict[str, Any]] = [
    {
        "id": "AIGP-001",
        "regulation_name": "AIGP Framework",
        "article_section": "Principle 1",
        "requirement_summary": "Human-in-the-loop oversight for high-risk AI decisions",
        "risk_level": "High",
        "status": "Compliant",
        "coverage_pct": 85,
        "last_updated": "2026-01-20",
        "assigned_owner": None,
        "notes": None,
    },
    {
        "id": "AIGP-002",
        "regulation_name": "AIGP Framework",
        "article_section": "Principle 3",
        "requirement_summary": "Transparency and explainability of AI outputs",
        "risk_level": "Medium",
        "status": "Compliant",
        "coverage_pct": 90,
        "last_updated": "2026-01-20",
        "assigned_owner": None,
        "notes": None,
    },
    {
        "id": "ISO-6.1",
        "regulation_name": "ISO 42001",
        "article_section": "§6.1",
        "requirement_summary": "Risk assessment and treatment planning for AI systems",
        "risk_level": "High",
        "status": "In Progress",
        "coverage_pct": 62,
        "last_updated": "2026-02-10",
        "assigned_owner": None,
        "notes": None,
    },
    {
        "id": "ISO-8.4",
        "regulation_name": "ISO 42001",
        "article_section": "§8.4",
        "requirement_summary": "Documented AI system objectives and performance criteria",
        "risk_level": "Medium",
        "status": "Gap",
        "coverage_pct": 35,
        "last_updated": None,
        "assigned_owner": None,
        "notes": "Pending SME review",
    },
    {
        "id": "ISO-9.1",
        "regulation_name": "ISO 42001",
        "article_section": "§9.1",
        "requirement_summary": "Performance evaluation and monitoring of AI systems",
        "risk_level": "Medium",
        "status": "Compliant",
        "coverage_pct": 88,
        "last_updated": "2026-01-10",
        "assigned_owner": None,
        "notes": None,
    },
]


def _nist_severity_to_risk(severity: int | None) -> str:
    return _SEVERITY_TO_RISK.get(severity or 0, "Low")


def get_matrix_rows(db: Session) -> list[dict[str, Any]]:
    """Return all compliance matrix rows aggregated from DB + static sources."""
    rows: list[dict[str, Any]] = []

    try:
        # EU AI Act rows — actual columns: article_number, title, risk_level (string)
        for rule in db.query(EUAIActRule).all():
            last_upd = rule.last_updated
            last_upd_str = last_upd.date().isoformat() if last_upd is not None else None
            risk = rule.risk_level if rule.risk_level in RISK_ORDINAL else "Medium"
            rows.append({
                "id": f"EUAI-{rule.id}",
                "regulation_name": "EU AI Act",
                "article_section": rule.article_number or "—",
                "requirement_summary": rule.title or "",
                "risk_level": risk,
                "status": "In Progress",
                "coverage_pct": None,
                "last_updated": last_upd_str,
                "assigned_owner": None,
                "notes": None,
            })
    except Exception:
        pass  # DB schema mismatch — skip DB rows, serve static-only

    try:
        # NIST RMF rows — actual columns: subcategory_id, function_name, description
        for ctrl in db.query(NISTControl).all():
            last_upd = ctrl.last_updated
            last_upd_str = last_upd.date().isoformat() if last_upd is not None else None
            rows.append({
                "id": ctrl.subcategory_id or f"NIST-{ctrl.id}",
                "regulation_name": "NIST AI RMF",
                "article_section": ctrl.function_name or "—",
                "requirement_summary": ctrl.description or "",
                "risk_level": "Medium",
                "status": "Compliant",
                "coverage_pct": None,
                "last_updated": last_upd_str,
                "assigned_owner": None,
                "notes": None,
            })
    except Exception:
        pass  # DB schema mismatch — skip DB rows, serve static-only

    rows.extend(_STATIC_ROWS)
    return rows


# ── Normalise string for case-insensitive / accent-insensitive sort ───────────

def _nfkd(s: str) -> str:
    return unicodedata.normalize("NFKD", s).casefold()


# ── Sort helpers ──────────────────────────────────────────────────────────────

def _sort_key_risk(row: dict[str, Any], asc: bool):
    rl = row.get("risk_level")
    # None and "N/A" both sort last regardless of direction
    is_last = rl is None or rl == "N/A"
    v = RISK_ORDINAL.get(rl or "", -1)
    return (1 if is_last else 0, v if asc else -v)


def _sort_key_regulation(row: dict[str, Any], asc: bool):
    v = _nfkd(row.get("regulation_name") or "")
    return (0, v) if asc else (0, tuple(-ord(c) for c in v))


def _sort_key_date(row: dict[str, Any], asc: bool):
    raw = row.get("last_updated")
    is_null = raw is None
    if raw:
        try:
            dt = datetime.fromisoformat(raw)
            ts = dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            ts = 0.0
            is_null = True
    else:
        ts = 0.0
    return (1 if is_null else 0, ts if asc else -ts)


_SORT_KEYS = {
    "risk_level": _sort_key_risk,
    "regulation_name": _sort_key_regulation,
    "last_updated": _sort_key_date,
}

VALID_SORT_COLUMNS = frozenset(_SORT_KEYS)
VALID_SORT_DIRS = frozenset({"asc", "desc"})


def sort_matrix_rows(
    rows: list[dict[str, Any]],
    sort_by: str | None,
    sort_dir: str = "asc",
) -> list[dict[str, Any]]:
    """Sort *rows* by *sort_by* column in *sort_dir* direction.

    Nulls always sort last regardless of direction.
    Returns the original list order when sort_by is None.
    """
    if not sort_by or sort_by not in _SORT_KEYS:
        return rows
    asc = sort_dir != "desc"
    key_fn = _SORT_KEYS[sort_by]
    return sorted(rows, key=lambda r: key_fn(r, asc))


def filter_matrix_rows(
    rows: list[dict[str, Any]],
    filter_regulation: str | None = None,
    filter_risk_level: str | None = None,
) -> list[dict[str, Any]]:
    """Filter rows by regulation name and/or risk level (case-insensitive exact match)."""
    result = rows
    if filter_regulation:
        needle = filter_regulation.casefold()
        result = [r for r in result if _nfkd(r.get("regulation_name") or "") == needle]
    if filter_risk_level:
        needle = filter_risk_level.casefold()
        result = [r for r in result if _nfkd(r.get("risk_level") or "") == needle]
    return result
