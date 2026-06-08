"""
Compliance Hub API.

GET /api/v1/compliance/hub — aggregated compliance status for the authenticated tenant.
GET /api/v1/compliance/dpa  — download GDPR Art. 28 DPA as PDF (compliance_lead / admin only).
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Audit, AuditEvent, AuditTrace, EnhancedTrace, Tenant, User
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
    """
    Derive internal RAG readiness indicator per framework from completed audit data.

    SAR-002 / COMPLIANCE_CLAIMS_MATRIX: these colours are INTERNAL dashboard
    indicators only (Green = audit evidence present, Amber = partial/no evidence).
    They must never be rendered as external compliance certifications.
    Use the framework_labels field (from compliance_label_service) for any
    externally-visible badge or claim text.
    """
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


def _readiness_checklist(
    audits: list[Audit],
    db: Session,
    tenant_id: Any,
) -> list[dict[str, Any]]:
    """
    Compute a 5-item readiness checklist dynamically from DB and static assets.

    Each item is evaluated independently (SAR-007 / PER-003 compliance_service spec):
      1. audit_trail     — tenant has at least one completed audit with hash-chained traces
      2. trace_export    — at least one EnhancedTrace record exists for tenant
      3. claims_matrix   — compliance label registry is loaded (always available)
      4. dpa_complete    — GDPR Art. 28 DPA template file is present on disk
      5. how_saro_reasons — static documentation is accessible (always available)
    """
    from pathlib import Path

    completed_audit_ids = {a.id for a in audits if a.status == "completed"}

    # Item 1: tamper-evident audit trail — any AuditTrace with event_hash present
    has_audit_trail = bool(completed_audit_ids) and db.query(AuditTrace).filter(
        AuditTrace.audit_id.in_(completed_audit_ids),
        AuditTrace.event_hash.isnot(None),
    ).first() is not None

    # Item 2: TRACE export — at least one EnhancedTrace for the tenant
    has_trace_export = (
        bool(completed_audit_ids)
        and db.query(EnhancedTrace)
        .filter(EnhancedTrace.audit_id.in_(completed_audit_ids))
        .first() is not None
    )

    # Item 3: claims matrix — compliance label registry file exists
    registry_path = Path(__file__).parent.parent / "data" / "compliance_label_registry.json"
    has_claims_matrix = registry_path.exists()

    # Item 4: DPA complete — DPA template file exists on disk
    dpa_path = Path(__file__).parent.parent / "docs" / "legal" / "saro-dpa-template-v1.0.md"
    has_dpa = dpa_path.exists()

    # Item 5: How SARO Reasons — static documentation always present
    how_path = Path(__file__).parent.parent / "frontend" / "tabs" / "how_saro_reasons.py"
    has_how_saro = how_path.exists()

    return [
        {"id": "audit_trail",      "label": "Hash-chained audit trail exists",   "complete": has_audit_trail},
        {"id": "trace_export",     "label": "TRACE export functional",            "complete": has_trace_export},
        {"id": "claims_matrix",    "label": "Claims matrix published",            "complete": has_claims_matrix},
        {"id": "dpa_complete",     "label": "DPA template complete",              "complete": has_dpa},
        {"id": "how_saro_reasons", "label": "How SARO Reasons published",         "complete": has_how_saro},
    ]


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

    # SAR-002: surface Tier 2 label text for each framework so the frontend
    # renders the correct EVF-approved badge rather than raw RAG colours.
    from services.compliance_label_service import get_all_labels
    try:
        framework_labels = get_all_labels()
    except Exception:
        framework_labels = []

    return {
        "recent_audits": _recent_audit_summaries(recent_audits),
        "claims_status": _claims_status(recent_audits),
        "framework_labels": framework_labels,
        "governance_links": _GOVERNANCE_LINKS,
        "readiness_checklist": _readiness_checklist(recent_audits, db, current_user.tenant_id),
    }


@router.get(
    "/dpa",
    summary="Download the SARO GDPR Art. 28 DPA as PDF (compliance_lead / admin only)",
)
def download_dpa(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FastAPIResponse:
    """
    Download the SARO GDPR Art. 28 DPA as PDF for the authenticated tenant.

    Restricted to compliance_lead, admin, and super_admin personas.
    Logs a dpa_downloaded AuditEvent on each successful download.

    Returns the DPA as application/pdf. If WeasyPrint is unavailable the
    fallback is an equivalent text/html document.
    """
    if current_user.persona_role not in ("compliance_lead", "admin", "super_admin"):
        raise HTTPException(
            status_code=403,
            detail="compliance_lead or admin persona required",
        )

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from services.dpa_service import _DPA_VERSION, generate_dpa_pdf

    pdf_bytes = generate_dpa_pdf(
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
    )

    ev = AuditEvent(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="dpa_downloaded",
        event_data={
            "dpa_version": _DPA_VERSION,
            "tenant_id": str(current_user.tenant_id),
            "user_id": str(current_user.id),
        },
    )
    db.add(ev)
    db.commit()

    content_type = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/html"
    filename = f"SARO_DPA_v{_DPA_VERSION}_{tenant.slug}.pdf"

    return FastAPIResponse(
        content=pdf_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename!r}"},
    )
