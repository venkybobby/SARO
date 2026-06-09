"""
CF-04: AIMS Document Lifecycle — ISO 42001 Evidence Linking
============================================================
POST /api/v1/aims/documents              — create AIMS document
GET  /api/v1/aims/documents              — list documents for tenant
POST /api/v1/aims/documents/{doc_id}/link/{audit_id}   — link audit
DELETE /api/v1/aims/documents/{doc_id}/link/{audit_id} — unlink audit
GET  /api/v1/aims/documents/{doc_id}/evidence-pack     — evidence JSON
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import AIMSDocument, Audit, AuditTrace, ScanReport, User
from schemas import AIMSDocumentIn, AIMSDocumentOut, AIMSEvidencePackOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/aims", tags=["aims"])

# ---------------------------------------------------------------------------
# React frontend compat: GET /api/v1/aims/models
# The React AI Model Inventory tab calls this endpoint to list registered
# AI models/systems for a tenant.  We surface the same data that backs the
# AIMS document evidence pack — enriched with model-centric metadata.
# ---------------------------------------------------------------------------

@router.get(
    "/models",
    summary="AIMS: List AI model registry for a tenant",
)
def list_aims_models(
    tenant_id: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
) -> dict:
    """
    Return the AI model inventory for the authenticated tenant.

    Query param ``tenant_id`` is accepted for React frontend compatibility but
    the actual tenant is always derived from the JWT — cross-tenant requests
    are silently scoped to the caller's tenant.
    """
    # Derive tenant from JWT (ignore query-param tenant_id for security)
    effective_tenant = current_user.tenant_id

    # Pull AIMS documents as the canonical model registry entries
    docs = (
        db.query(AIMSDocument)
        .filter(AIMSDocument.tenant_id == effective_tenant)
        .order_by(AIMSDocument.created_at.desc())
        .all()
    )

    models_out = []
    for doc in docs:
        models_out.append({
            "model_id": str(doc.id),
            "name": doc.title,
            "version": doc.version,
            "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
            "owner_email": doc.owner_email,
            "linked_audit_count": len(doc.linked_audit_ids or []),
            "risk_tier": "high",          # default — override once risk_tier column added
            "lifecycle_stage": "production",
            "framework_coverage": ["ISO-42001", "EU-AI-ACT-2024"],
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        })

    return {
        "models": models_out,
        "total": len(models_out),
        "tenant_id": str(effective_tenant),
        "note": "Model registry derived from AIMS document lifecycle records. "
                "Evidence-based — human review required for classification decisions.",
    }

_ALLOWED_PERSONAS = {"compliance_lead", "ai_auditor"}


def _check_aims_permission(user: User) -> None:
    """Raise 403 if user persona is not allowed to create/modify AIMS docs."""
    persona = getattr(user, "persona_role", None)
    if user.role == "super_admin":
        return
    if not persona or persona not in _ALLOWED_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your persona role does not have create_aims_document permission.",
        )


def _get_doc_or_404(doc_id: uuid.UUID, tenant_id: uuid.UUID, db: Session) -> AIMSDocument:
    doc = db.get(AIMSDocument, doc_id)
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AIMS document not found")
    return doc


@router.post(
    "/documents",
    response_model=AIMSDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-04: Create an AIMS document",
)
def create_aims_document(
    payload: AIMSDocumentIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIMSDocumentOut:
    _check_aims_permission(current_user)
    doc = AIMSDocument(
        tenant_id=current_user.tenant_id,
        title=payload.title,
        version=payload.version,
        effective_date=payload.effective_date,
        owner_email=str(payload.owner_email),
        linked_audit_ids=[],
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info("AIMS document %s created by %s", doc.id, current_user.email)
    return AIMSDocumentOut.model_validate(doc)


@router.get(
    "/documents",
    response_model=list[AIMSDocumentOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-04: List AIMS documents for tenant",
)
def list_aims_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AIMSDocumentOut]:
    docs = (
        db.query(AIMSDocument)
        .filter(AIMSDocument.tenant_id == current_user.tenant_id)
        .order_by(AIMSDocument.created_at.desc())
        .all()
    )
    return [AIMSDocumentOut.model_validate(d) for d in docs]


@router.post(
    "/documents/{doc_id}/link/{audit_id}",
    response_model=AIMSDocumentOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-04: Link a completed audit to an AIMS document",
)
def link_audit(
    doc_id: uuid.UUID,
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIMSDocumentOut:
    _check_aims_permission(current_user)
    doc = _get_doc_or_404(doc_id, current_user.tenant_id, db)
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")

    audit_id_str = str(audit_id)
    existing = list(doc.linked_audit_ids or [])
    if audit_id_str not in existing:
        existing.append(audit_id_str)
        doc.linked_audit_ids = existing
        doc.updated_at = datetime.now(tz=timezone.utc)
        db.commit()
        db.refresh(doc)

    return AIMSDocumentOut.model_validate(doc)


@router.delete(
    "/documents/{doc_id}/link/{audit_id}",
    response_model=AIMSDocumentOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-04: Unlink an audit from an AIMS document",
)
def unlink_audit(
    doc_id: uuid.UUID,
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIMSDocumentOut:
    _check_aims_permission(current_user)
    doc = _get_doc_or_404(doc_id, current_user.tenant_id, db)
    audit_id_str = str(audit_id)
    existing = [a for a in (doc.linked_audit_ids or []) if a != audit_id_str]
    doc.linked_audit_ids = existing
    doc.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(doc)
    return AIMSDocumentOut.model_validate(doc)


@router.get(
    "/documents/{doc_id}/evidence-pack",
    response_model=AIMSEvidencePackOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-04: Generate ISO 42001 evidence pack JSON for an AIMS document",
)
def get_evidence_pack(
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AIMSEvidencePackOut:
    doc = _get_doc_or_404(doc_id, current_user.tenant_id, db)
    doc_out = AIMSDocumentOut.model_validate(doc)

    linked_audits: list[dict[str, Any]] = []
    for audit_id_str in (doc.linked_audit_ids or []):
        try:
            audit_id = uuid.UUID(audit_id_str)
        except ValueError:
            continue
        audit = db.get(Audit, audit_id)
        if not audit:
            continue

        report = db.query(ScanReport).filter(ScanReport.audit_id == audit_id).first()
        traces = (
            db.query(AuditTrace)
            .filter(AuditTrace.audit_id == audit_id)
            .all()
        )

        # Compliance rules with rule_pack_version
        applied_rules = [
            {
                "check_name": t.check_name,
                "result": t.result,
                "framework": (t.detail_json or {}).get("framework"),
                "rule_id": (t.detail_json or {}).get("rule_id"),
                "rule_pack": (t.detail_json or {}).get("rule_pack"),
            }
            for t in traces
            if t.check_type == "compliance_rule"
        ]

        linked_audits.append({
            "audit_id": audit_id_str,
            "dataset_name": audit.dataset_name,
            "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
            "status": audit.status,
            "overall_risk_score": report.overall_risk_score if report else None,
            "mit_coverage_score": report.mit_coverage_score if report else None,
            "confidence_score": report.confidence_score if report else None,
            "gate_summary": report.report_json.get("gates") if report and report.report_json else [],
            "applied_rules": applied_rules,
        })

    return AIMSEvidencePackOut(
        document=doc_out,
        linked_audits=linked_audits,
        generated_at=datetime.now(tz=timezone.utc),
    )
