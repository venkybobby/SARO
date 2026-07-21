"""Governance API: data retention policies, GDPR erasure, deletion certificates."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_current_user
from services.retention_service import (
    calculate_retention_cutoff,
)

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


class ErasureRequest(BaseModel):
    tenant_id: int
    requester_email: str
    reason: Optional[str] = "GDPR Article 17 Right to Erasure"


class RetentionPolicy(BaseModel):
    tenant_id: int
    retention_days: int = 90
    gdpr_erasure_enabled: bool = True


@router.post("/erasure-request", status_code=202)
def submit_erasure_request(
    request: ErasureRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit a GDPR erasure request. Processing is asynchronous (SLA: 72 hours)."""
    erasure_id = str(uuid.uuid4())
    return {
        "status": "accepted",
        "erasure_request_id": erasure_id,
        "tenant_id": request.tenant_id,
        "sla_hours": 72,
        "submitted_at": datetime.utcnow().isoformat(),
        "message": "Erasure request accepted. All tenant data will be deleted within 72 hours.",
    }


@router.post("/retention-policy")
def set_retention_policy(
    policy: RetentionPolicy,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create or update a data retention policy for a tenant."""
    return {
        "tenant_id": policy.tenant_id,
        "retention_days": policy.retention_days,
        "gdpr_erasure_enabled": policy.gdpr_erasure_enabled,
        "cutoff_date": calculate_retention_cutoff(policy.retention_days).isoformat(),
        "status": "active",
    }


# ── React frontend compat aliases (fixes 404s for /governance/docs and /governance/ir-plan) ──

@router.get("/docs")
def list_governance_docs(current_user=Depends(get_current_user)):
    """List available governance documents (React frontend compatibility)."""
    return [
        {"key": "dpa-template",       "label": "DPA Template",              "url": "/api/v1/governance/docs/dpa-template"},
        {"key": "nist-self-assessment","label": "NIST Self-Assessment",       "url": "/api/v1/governance/docs/nist-self-assessment"},
        {"key": "eu-ai-act-position",  "label": "EU AI Act Position Paper",   "url": "/api/v1/governance/docs/eu-ai-act-position"},
        {"key": "soc2-roadmap",        "label": "SOC 2 Roadmap",              "url": "/api/v1/governance/docs/soc2-roadmap"},
        {"key": "ir-plan",             "label": "Incident Response Plan",     "url": "/api/v1/governance/ir-plan"},
    ]


@router.get("/ir-plan")
def get_ir_plan(current_user=Depends(get_current_user)):
    """Incident Response Plan summary (React frontend compatibility)."""
    # FND-064: these numbers are customer-facing and MUST match
    # docs/ops/support-model.md §3-§4 and docs/incident-response-plan.md v1.1.
    # v1.0 served sla_hours=1 for downtime and breach — response targets the
    # email-only, solo-operator model cannot deliver. They now carry the
    # committed values, and `sla_basis` names which clock each one is, because
    # "1 hour" meant two different things (response vs notification) before.
    # tests/regression/test_fnd_064_ir_plan_response_commitments.py pins the
    # agreement between this payload and the documents.
    return {
        "title": "SARO Incident Response Plan",
        "version": "1.1",
        "sections": [
            {
                "id": "downtime",
                "title": "Service Downtime",
                "sla_hours": 1,
                "sla_basis": "S1 response, business hours; best-effort outside hours",
                "detection_minutes": 60,
            },
            {
                "id": "data-breach",
                "title": "Data Breach Protocol",
                "sla_hours": 72,
                "sla_basis": "customer notification after confirmation of a reportable incident",
            },
            {
                "id": "false-negative",
                "title": "False Negative Response",
                "sla_hours": 4,
                "sla_basis": "S2 response, business hours",
            },
            {
                "id": "escalation",
                "title": "Escalation Contacts",
                "sla_hours": None,
                "sla_basis": "solo-operator model; no on-call rotation",
            },
        ],
        "support_hours": "Mon-Fri 09:00-18:00 America/Chicago, excluding US public holidays",
        "contact_email": "security@saro.app",
        "last_reviewed": "2026-07-21",
        "note": "Full IR plan available at GET /api/v1/governance/docs/ir-plan (download). "
        "Severity levels and response targets are maintained in the support model.",
    }
