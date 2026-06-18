"""TRACE view and evidence export endpoints."""

import json
import uuid
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from models import Audit, AuditTrace, ScanReport
from services.trace_service import build_trace_timeline
from services.rfc3161_service import attach_timestamp_to_export
import os
import io

router = APIRouter(prefix="/api/v1/audit", tags=["trace"])

HMAC_SECRET = os.environ.get("SARO_EXPORT_SECRET", "saro-default-export-secret")


def _parse_audit_uuid(raw: str) -> uuid.UUID:
    """Parse and validate a UUID string, returning 422 with a clear message on failure."""
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_audit_id",
                "message": (
                    f"'{raw}' is not a valid audit ID. "
                    "Audit IDs are UUIDs (e.g. 3f2a1b4c-…). "
                    "Find your audit ID on the Dashboard or Audits list."
                ),
            },
        )


def _get_audit_or_404(
    db: Session, audit_uuid: uuid.UUID, tenant_id: uuid.UUID
) -> Audit:
    """Return the audit or 404 if not found / wrong tenant.

    STORY-TRACE-002: scoped to the caller's tenant. The 404 detail is generic
    ("Audit not found") so a foreign-tenant audit is indistinguishable from a
    nonexistent one (no existence oracle), matching ``routers/traces.py``.
    """
    audit = (
        db.query(Audit)
        .filter(Audit.id == audit_uuid, Audit.tenant_id == tenant_id)
        .first()
    )
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return audit


@router.get("/{audit_id}/trace")
async def get_trace(
    audit_id: str = Path(..., description="Audit UUID"),
    executive_mode: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the 6-step TRACE timeline for an audit, with model_version and chain_of_thought."""
    audit_uuid = _parse_audit_uuid(audit_id)
    audit = _get_audit_or_404(db, audit_uuid, current_user.tenant_id)

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_uuid).all()
    trace_dicts = [
        {
            "id": str(t.id),
            "audit_id": str(t.audit_id),
            "gate_id": t.gate_id,
            "gate_name": t.gate_name,
            "check_type": t.check_type,
            "check_name": t.check_name,
            "result": t.result,
            "reason": t.reason,
            "remediation_hint": t.remediation_hint,
            "confidence": getattr(t, "confidence", 0.85),
            "created_at": str(t.created_at),
        }
        for t in traces
    ]
    timeline = build_trace_timeline(trace_dicts, executive_mode=executive_mode)

    # S-202: attach model_version and chain_of_thought from EnhancedTrace if available
    from models import EnhancedTrace as _EnhancedTrace

    enhanced = (
        db.query(_EnhancedTrace).filter(_EnhancedTrace.audit_id == audit_uuid).first()
    )
    model_version = "saro-engine-1.0"
    chain_of_thought: list = []
    if enhanced:
        model_version = enhanced.model_version or model_version
        cot = enhanced.chain_of_thought or {}
        chain_of_thought = cot.get("steps", []) if isinstance(cot, dict) else []

    if isinstance(timeline, dict):
        timeline["model_version"] = model_version
        timeline["chain_of_thought"] = chain_of_thought
        timeline["audit_status"] = audit.status
    return timeline


@router.get("/{audit_id}/trace/export")
async def export_trace_extended(
    audit_id: str = Path(..., description="Audit UUID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export a full signed TRACE evidence pack with model_version and chain_of_thought."""
    audit_uuid = _parse_audit_uuid(audit_id)
    audit = _get_audit_or_404(db, audit_uuid, current_user.tenant_id)

    from models import EnhancedTrace as _EnhancedTrace, ScanReport as _ScanReport

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_uuid).all()
    report = db.query(_ScanReport).filter(_ScanReport.audit_id == audit_uuid).first()
    enhanced = (
        db.query(_EnhancedTrace).filter(_EnhancedTrace.audit_id == audit_uuid).first()
    )

    timeline = build_trace_timeline(
        [
            {
                "id": str(t.id),
                "audit_id": str(t.audit_id),
                "gate_id": t.gate_id,
                "gate_name": t.gate_name,
                "result": t.result,
                "reason": t.reason,
                "confidence": 0.85,
            }
            for t in traces
        ]
    )

    model_version = "saro-engine-1.0"
    chain_of_thought: list = []
    if enhanced:
        model_version = enhanced.model_version or model_version
        cot = enhanced.chain_of_thought or {}
        chain_of_thought = cot.get("steps", []) if isinstance(cot, dict) else []

    export = {
        "export_version": "2.0",
        "audit_id": str(audit_uuid),
        "exported_at": datetime.utcnow().isoformat(),
        "model_version": model_version,
        "chain_of_thought": chain_of_thought,
        "audit_metadata": {
            "status": audit.status,
            "created_at": str(audit.created_at),
        },
        "trace_timeline": timeline,
        "risk_score": report.overall_risk_score if report else None,
        "confidence": report.confidence_score if report else None,
        "export_hash": enhanced.export_hash if enhanced else None,
    }

    canonical = json.dumps(export, sort_keys=True)
    sig = hmac.new(HMAC_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    export["_signature"] = sig
    export = attach_timestamp_to_export(export)
    return export


@router.get("/{audit_id}/export/json")
async def export_trace_json(
    audit_id: str = Path(..., description="Audit UUID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export a signed JSON evidence pack for an audit."""
    audit_uuid = _parse_audit_uuid(audit_id)
    audit = _get_audit_or_404(db, audit_uuid, current_user.tenant_id)

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_uuid).all()
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_uuid).first()

    timeline = build_trace_timeline(
        [
            {
                "id": str(t.id),
                "audit_id": str(t.audit_id),
                "gate_id": t.gate_id,
                "gate_name": t.gate_name,
                "result": t.result,
                "reason": t.reason,
                "confidence": 0.85,
            }
            for t in traces
        ]
    )

    export = {
        "export_version": "2.0",
        "audit_id": str(audit_uuid),
        "exported_at": datetime.utcnow().isoformat(),
        "audit_metadata": {
            "status": audit.status,
            "created_at": str(audit.created_at),
        },
        "trace_timeline": timeline,
        "risk_score": getattr(report, "risk_score", None) if report else None,
        "confidence": getattr(report, "confidence", None) if report else None,
    }

    canonical = json.dumps(export, sort_keys=True)
    sig = hmac.new(HMAC_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    export["_signature"] = sig
    export = attach_timestamp_to_export(export)

    return export


@router.get("/{audit_id}/export/pdf")
async def export_trace_pdf(
    audit_id: str = Path(..., description="Audit UUID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a PDF evidence pack for an audit."""
    audit_uuid = _parse_audit_uuid(audit_id)
    _get_audit_or_404(db, audit_uuid, current_user.tenant_id)

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_uuid).all()
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_uuid).first()

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer  # noqa: F401

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("SARO Evidence Pack", styles["Title"]))
        story.append(Paragraph(f"Audit ID: {audit_uuid}", styles["Normal"]))
        story.append(
            Paragraph(f"Generated: {datetime.utcnow().isoformat()}", styles["Normal"])
        )
        story.append(Spacer(1, 12))

        story.append(Paragraph("TRACE Analysis Timeline", styles["Heading1"]))
        for t in traces:
            story.append(
                Paragraph(
                    f"<b>{t.gate_name or t.gate_id}</b>: {t.result} — {t.reason or ''}",
                    styles["Normal"],
                )
            )
        story.append(Spacer(1, 12))

        if report:
            story.append(Paragraph("Risk Assessment", styles["Heading1"]))
            story.append(
                Paragraph(f"Risk Score: {report.risk_score}", styles["Normal"])
            )
            story.append(
                Paragraph(f"Confidence: {report.confidence}", styles["Normal"])
            )
        story.append(Spacer(1, 12))

        canonical = json.dumps({"audit_id": str(audit_uuid)}, sort_keys=True)
        sig = hmac.new(
            HMAC_SECRET.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()
        story.append(Paragraph("Verification", styles["Heading1"]))
        story.append(Paragraph(f"HMAC-SHA256: {sig[:16]}...", styles["Normal"]))

        doc.build(story)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=saro-evidence-{str(audit_uuid)[:8]}.pdf"
            },
        )
    except ImportError:
        content = f"SARO Evidence Pack\nAudit ID: {audit_uuid}\nGenerated: {datetime.utcnow().isoformat()}\n"
        for t in traces:
            content += f"\n{t.gate_name}: {t.result} — {t.reason or ''}"
        return StreamingResponse(
            io.StringIO(content),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=saro-evidence-{str(audit_uuid)[:8]}.txt"
            },
        )
