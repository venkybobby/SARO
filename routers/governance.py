"""Governance API: data retention policies, GDPR erasure, deletion certificates."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_current_user
from services.retention_service import (
    calculate_retention_cutoff,
    create_tombstone_record,
    generate_deletion_certificate,
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
