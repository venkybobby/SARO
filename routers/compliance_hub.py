"""
Compliance Hub API.

GET /api/v1/compliance/hub — aggregated compliance status for the authenticated tenant.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Audit, User
from services.evf_validation_status_service import get_all_framework_statuses
from services.persona_service import persona_required

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance-hub"])

_READINESS_ITEMS = [
    {"id": "audit_trail", "label": "Hash-chained audit trail exists"},
    {"id": "trace_export", "label": "TRACE export functional"},
    {"id": "claims_matrix", "label": "Claims matrix published"},
    {"id": "dpa_complete", "label": "DPA template complete"},
    {"id": "how_saro_reasons", "label": "How SARO Reasons published"},
]

_GOVERNANCE_LINKS: dict[str, str] = {
    "dpa_template": "/docs/dpa-template.md",
    "sub_processors": "/docs/sub-processors.md",
    "retention_policy": "/api/v1/governance/retention-policy",
}


def _claims_status(audits: list[Audit]) -> dict[str, str]:
    """Derive RAG compliance status per framework from completed audit data."""
    completed = [a for a in audits if a.status == "completed"]
    count = len(completed)
    if count >= 5:
        nist = eu = aigp = iso = "GREEN"
    elif count >= 2:
        nist = aigp = iso = "GREEN"
        eu = "AMBER"
    elif count == 1:
        nist = "GREEN"
        eu = aigp = iso = "AMBER"
    else:
        nist = "AMBER"
        eu = aigp = iso = "AMBER"
    return {
        "nist_rmf": nist,
        "eu_ai_act": eu,
        "aigp": aigp,
        "iso_42001": iso,
    }


def _readiness_checklist(audits: list[Audit]) -> list[dict[str, Any]]:
    """Compute readiness checklist based on tenant audit history."""
    has_completed = any(a.status == "completed" for a in audits)
    result = []
    for item in _READINESS_ITEMS:
        complete = has_completed
        result.append({"id": item["id"], "label": item["label"], "complete": complete})
    return result


def _recent_audit_summaries(audits: list[Audit]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(a.id),
            "dataset_name": a.dataset_name,
            "status": a.status,
            "sample_count": a.sample_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in audits
    ]


@router.get(
    "/hub",
    dependencies=[Depends(persona_required(["compliance_lead", "admin"]))],
    summary="Aggregated compliance hub status for the authenticated tenant",
)
def get_compliance_hub(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """
    Returns recent audits, per-framework compliance status, governance doc links,
    and a readiness checklist for the authenticated tenant.
    """
    recent_audits = (
        db.query(Audit)
        .filter(Audit.tenant_id == current_user.tenant_id)
        .order_by(Audit.created_at.desc())
        .limit(10)
        .all()
    )

    # FR-EVF-11: stamp live EVF validation tier alongside claims_status so the
    # hub never shows a compliance RAG colour without the corresponding tier label.
    evf_statuses = get_all_framework_statuses(db)

    return {
        "recent_audits": _recent_audit_summaries(recent_audits),
        "claims_status": _claims_status(recent_audits),
        "governance_links": _GOVERNANCE_LINKS,
        "readiness_checklist": _readiness_checklist(recent_audits),
        # EVF validation tier per framework — Tier 1/2/3 per FR-EVF-16
        "evf_validation_status": {
            s["framework"]: {
                "tier":          s["tier"],
                "label":         s["label"],
                "qco_reference": s["qco_reference"],
                "expires_in_days": s["expires_in_days"],
            }
            for s in evf_statuses
        },
    }
