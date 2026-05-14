"""Board-level risk dashboard API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from models import Audit, ScanReport
from services.risk_service import build_risk_summary, aggregate_vendor_risk

router = APIRouter(prefix="/api/v1/risk", tags=["risk-dashboard"])


def _get_audit_records(db: Session, tenant_id: int) -> list[dict]:
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
            "source_model": None,  # populated below if AuditMetadata exists
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
        "total_vendors": len(set(r.get("source_model", "Unknown") for r in records)),
    }
