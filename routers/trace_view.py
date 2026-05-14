"""TRACE view and evidence export endpoints."""
import json
import hmac
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/{audit_id}/trace")
def get_trace(
    audit_id: int,
    executive_mode: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the 6-step TRACE timeline for an audit."""
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_id).all()
    trace_dicts = [
        {
            "id": t.id,
            "audit_id": t.audit_id,
            "gate_id": t.gate_id,
            "gate_name": t.gate_name,
            "check_type": t.check_type,
            "result": t.result,
            "reason": t.reason,
            "remediation_hint": t.remediation_hint,
            "confidence": getattr(t, "confidence", 0.85),
            "created_at": str(t.created_at),
        }
        for t in traces
    ]
    return build_trace_timeline(trace_dicts, executive_mode=executive_mode)


@router.get("/{audit_id}/export/json")
def export_trace_json(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export a signed JSON evidence pack for an audit."""
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_id).all()
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_id).first()

    timeline = build_trace_timeline([
        {"id": t.id, "audit_id": t.audit_id, "gate_id": t.gate_id,
         "gate_name": t.gate_name, "result": t.result, "reason": t.reason,
         "confidence": 0.85}
        for t in traces
    ])

    export = {
        "export_version": "2.0",
        "audit_id": audit_id,
        "exported_at": datetime.utcnow().isoformat(),
        "audit_metadata": {
            "status": audit.status,
            "created_at": str(audit.created_at),
        },
        "trace_timeline": timeline,
        "risk_score": getattr(report, "risk_score", None) if report else None,
        "confidence": getattr(report, "confidence", None) if report else None,
    }

    # HMAC-SHA256 signature
    canonical = json.dumps(export, sort_keys=True)
    sig = hmac.new(HMAC_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    export["_signature"] = sig

    # RFC 3161 timestamp
    export = attach_timestamp_to_export(export)

    return export


@router.get("/{audit_id}/export/pdf")
def export_trace_pdf(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a PDF evidence pack for an audit."""
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail=f"Audit {audit_id} not found")

    traces = db.query(AuditTrace).filter(AuditTrace.audit_id == audit_id).all()
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_id).first()

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph("SARO Evidence Pack", styles["Title"]))
        story.append(Paragraph(f"Audit ID: {audit_id}", styles["Normal"]))
        story.append(Paragraph(f"Generated: {datetime.utcnow().isoformat()}", styles["Normal"]))
        story.append(Spacer(1, 12))

        # TRACE Timeline
        story.append(Paragraph("TRACE Analysis Timeline", styles["Heading1"]))
        for t in traces:
            story.append(Paragraph(
                f"<b>{t.gate_name or t.gate_id}</b>: {t.result} — {t.reason or ''}",
                styles["Normal"]
            ))
        story.append(Spacer(1, 12))

        # Risk Score
        if report:
            story.append(Paragraph("Risk Assessment", styles["Heading1"]))
            story.append(Paragraph(f"Risk Score: {report.risk_score}", styles["Normal"]))
            story.append(Paragraph(f"Confidence: {report.confidence}", styles["Normal"]))
        story.append(Spacer(1, 12))

        # Verification
        canonical = json.dumps({"audit_id": audit_id}, sort_keys=True)
        sig = hmac.new(HMAC_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        story.append(Paragraph("Verification", styles["Heading1"]))
        story.append(Paragraph(f"HMAC-SHA256: {sig[:16]}...", styles["Normal"]))

        doc.build(story)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=saro-evidence-{audit_id}.pdf"}
        )
    except ImportError:
        # ReportLab not installed — return a plain text fallback
        content = f"SARO Evidence Pack\nAudit ID: {audit_id}\nGenerated: {datetime.utcnow().isoformat()}\n"
        for t in traces:
            content += f"\n{t.gate_name}: {t.result} — {t.reason or ''}"
        return StreamingResponse(
            io.StringIO(content),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=saro-evidence-{audit_id}.txt"}
        )
