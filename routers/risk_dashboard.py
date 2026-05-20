"""Board-level risk dashboard API endpoints."""
import hashlib
import hmac
import io
import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Audit, ScanReport
from services.risk_service import (
    aggregate_vendor_risk,
    build_risk_summary,
    calculate_rag_status,
)

router = APIRouter(prefix="/api/v1/risk", tags=["risk-dashboard"])

_HMAC_SECRET = os.environ.get("SARO_EXPORT_SECRET", "saro-default-export-secret")


def _get_audit_records(db: Session, tenant_id) -> list[dict]:
    """Fetch audit records with risk scores for a tenant."""
    rows = (
        db.query(Audit, ScanReport)
        .join(ScanReport, ScanReport.audit_id == Audit.id, isouter=True)
        .filter(Audit.tenant_id == tenant_id)
        .all()
    )
    records = []
    for audit, report in rows:
        records.append({
            "audit_id": audit.id,
            "created_at": str(audit.created_at),
            "status": audit.status,
            "risk_score": getattr(report, "risk_score", None) if report else None,
            "confidence": getattr(report, "confidence", None) if report else None,
            "source_model": getattr(audit, "source_model", None),
        })
    return records


@router.get("/summary")
def get_risk_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return aggregated risk summary for the board dashboard."""
    records = _get_audit_records(db, current_user.tenant_id)
    return build_risk_summary(records, findings=[])


@router.get("/vendors")
def get_vendor_risk(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return risk breakdown by AI vendor/model."""
    records = _get_audit_records(db, current_user.tenant_id)
    return {
        "vendors": aggregate_vendor_risk(records),
        "total_vendors": len(set(r.get("source_model") or "Unknown" for r in records)),
    }


@router.get("/whats-changed")
def get_whats_changed(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return 7-day risk delta: score change, new audits, new findings vs. prior 7 days."""
    all_records = _get_audit_records(db, current_user.tenant_id)
    now = datetime.utcnow()
    cutoff_7 = now - timedelta(days=7)
    cutoff_14 = now - timedelta(days=14)

    def _score(records: list[dict]) -> float:
        scores = [r["risk_score"] for r in records if r.get("risk_score") is not None]
        return round(sum(scores) / len(scores), 2) if scores else 0.0

    def _in_window(r: dict, start: datetime, end: datetime) -> bool:
        try:
            dt = datetime.fromisoformat(str(r["created_at"]).split(".")[0].rstrip("Z"))
            return start <= dt <= end
        except Exception:
            return False

    recent = [r for r in all_records if _in_window(r, cutoff_7, now)]
    prior = [r for r in all_records if _in_window(r, cutoff_14, cutoff_7)]

    recent_score = _score(recent)
    prior_score = _score(prior)
    delta = round(recent_score - prior_score, 2)

    return {
        "period_days": 7,
        "current_avg_score": recent_score,
        "prior_avg_score": prior_score,
        "score_delta": delta,
        "delta_direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
        "new_audits_count": len(recent),
        "prior_audits_count": len(prior),
        "current_rag": calculate_rag_status(recent_score),
        "prior_rag": calculate_rag_status(prior_score),
        "generated_at": now.isoformat(),
    }


@router.get("/board-export")
def export_board_pdf(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a board-ready one-page risk summary PDF with vendor risk section."""
    records = _get_audit_records(db, current_user.tenant_id)
    summary = build_risk_summary(records, findings=[])
    vendors = aggregate_vendor_risk(records)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter,
                                leftMargin=inch, rightMargin=inch,
                                topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        story = []

        # ── Header ───────────────────────────────────────────────────────────
        story.append(Paragraph("SARO Board Risk Summary", styles["Title"]))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%d %B %Y')} | "
            f"Audits analysed: {summary['audit_count']}",
            styles["Normal"],
        ))
        story.append(Spacer(1, 12))

        # ── RAG Status ───────────────────────────────────────────────────────
        rag = summary["rag_status"]
        rag_color = {"GREEN": colors.green, "AMBER": colors.orange, "RED": colors.red}.get(rag, colors.grey)
        rag_table = Table([[f"Overall Risk Status: {rag}  |  Score: {summary['overall_risk_score']}"]])
        rag_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), rag_color),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 14),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(rag_table)
        story.append(Spacer(1, 16))

        # ── Vendor Risk ──────────────────────────────────────────────────────
        story.append(Paragraph("AI Vendor Risk Breakdown", styles["Heading2"]))
        if vendors:
            vdata = [["Vendor / Model", "Audits", "Avg Score", "Status", "New?"]]
            for v in vendors:
                vdata.append([
                    v["vendor"],
                    str(v["audit_count"]),
                    str(v["avg_risk_score"]),
                    v["rag_status"],
                    "⚠️ New" if v.get("is_new") else "—",
                ])
            vtable = Table(vdata, colWidths=[2.5 * inch, 0.8 * inch, 1 * inch, 1 * inch, 0.8 * inch])
            vtable.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(vtable)
        else:
            story.append(Paragraph("No vendor data available.", styles["Normal"]))
        story.append(Spacer(1, 16))

        # ── Remediation % ────────────────────────────────────────────────────
        story.append(Paragraph(
            f"Remediation Progress: {summary['remediation_pct']}%", styles["Heading3"],
        ))
        story.append(Spacer(1, 12))

        # ── Verification hash ────────────────────────────────────────────────
        canonical = json.dumps(
            {"tenant_id": str(current_user.tenant_id), "generated_at": summary["generated_at"]},
            sort_keys=True,
        )
        sig = hmac.new(_HMAC_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        story.append(Paragraph(f"Verification hash: {sig[:24]}…", styles["Normal"]))

        doc.build(story)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=saro-board-risk-report.pdf"},
        )

    except ImportError:
        # ReportLab not installed — return JSON summary instead
        return {
            **summary,
            "vendors": vendors,
            "note": "Install reportlab for PDF export: pip install reportlab",
        }
