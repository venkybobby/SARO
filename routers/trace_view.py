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
from auth import (
    get_current_user,
    require_role_or_persona,
    TRACE_READ_ROLES,
    TRACE_READ_PERSONAS,
)
from models import Audit, AuditTrace, ScanReport
from services.trace_service import build_trace_timeline
from services.rfc3161_service import attach_timestamp_to_export
import os
import io

router = APIRouter(prefix="/api/v1/audit", tags=["trace"])

# STORY-TRACE-003: read access to TRACE evidence for the audit/compliance
# personas (ai_auditor / compliance_lead) plus the legacy operator roles.
# Applied to the timeline + every signed-export variant (same evidence surface).
_require_trace_read = require_role_or_persona(TRACE_READ_ROLES, TRACE_READ_PERSONAS)

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


def _verify_integrity(audit, traces, enhanced, report) -> dict:
    """STORY-TRACE-004: an honest integrity verdict for the TRACE View banner.

    Recomputes the HMAC-SHA256 signature over the canonical export (the same
    mechanism that produced the recorded ``export_hash`` in ``trace_export.py``)
    and compares it to the stored value. The verdict is deliberately conservative:

      - ``verified``: the recomputed HMAC matches the recorded signature — the only
        state that yields a positive integrity claim.
      - ``unavailable``: no signed export on record, verification cannot be run, OR
        the recorded signature does not match. A mismatch is NOT reported as a green
        "verified" and NOT asserted as "tampered", because ``export_hash`` may have
        been written by an alternate (plain-SHA-256) export path in this codebase
        (``output_audit.py``), so a mismatch alone cannot prove tampering. This keeps
        the banner from over- or under-claiming (ADR-004 anti-overclaiming lock).
    """
    if not enhanced or not getattr(enhanced, "export_hash", None) or not report:
        return {
            "status": "unavailable",
            "verified": False,
            "detail": "No signed export on record for this audit.",
        }
    try:
        from routers.trace_export import _build_signed_json

        _, recomputed, _ = _build_signed_json(audit, enhanced, traces, report)
    except Exception:
        return {
            "status": "unavailable",
            "verified": False,
            "detail": "Integrity verification could not be performed for this audit.",
        }
    if hmac.compare_digest(str(recomputed), str(enhanced.export_hash)):
        return {
            "status": "verified",
            "verified": True,
            "export_hash": str(enhanced.export_hash)[:12],
            "detail": "HMAC-SHA256 signature valid over the canonical export.",
        }
    return {
        "status": "unavailable",
        "verified": False,
        "detail": "Recorded export signature could not be confirmed for the current trace.",
    }


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


@router.get("/{audit_id}/trace", dependencies=[Depends(_require_trace_read)])
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

    # STORY-TRACE-001: surface the real risk score on the timeline so the TRACE
    # View header binds a real value (not a blank chip) from the primary fetch.
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_uuid).first()

    if isinstance(timeline, dict):
        timeline["model_version"] = model_version
        timeline["chain_of_thought"] = chain_of_thought
        timeline["audit_status"] = audit.status
        timeline["risk_score"] = report.overall_risk_score if report else None
        # STORY-TRACE-004: honest, server-computed integrity verdict.
        timeline["integrity"] = _verify_integrity(audit, traces, enhanced, report)
    return timeline


@router.get("/{audit_id}/trace/export", dependencies=[Depends(_require_trace_read)])
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


@router.get("/{audit_id}/export/json", dependencies=[Depends(_require_trace_read)])
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


@router.get("/{audit_id}/export/pdf", dependencies=[Depends(_require_trace_read)])
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
