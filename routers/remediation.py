"""Remediation and coverage gap API endpoints."""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
from services.remediation_service import generate_remediation_steps, validate_remediation_step
from services.coverage_service import build_coverage_report, DEFAULT_OVERDUE_DAYS

router = APIRouter(prefix="/api/v1", tags=["remediation"])


class Finding(BaseModel):
    rule_id: str
    severity: str = "MEDIUM"
    description: str = ""
    check_type: str = "rule"


class AISystem(BaseModel):
    name: str
    vendor: str
    owner: str
    last_audit_date: Optional[str] = None


@router.post("/remediation/steps")
def get_remediation_steps(
    finding: Finding,
    current_user=Depends(get_current_user),
):
    """Get structured remediation steps for a finding."""
    steps = generate_remediation_steps(finding.dict())
    return {
        "finding": finding.dict(),
        "remediation_steps": steps,
        "step_count": len(steps),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.post("/coverage/systems")
def register_ai_system(
    system: AISystem,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Register an AI system for coverage tracking."""
    return {
        "name": system.name,
        "vendor": system.vendor,
        "owner": system.owner,
        "registered_at": datetime.utcnow().isoformat(),
        "status": "registered",
    }


@router.get("/coverage")
def get_coverage(
    overdue_days: int = DEFAULT_OVERDUE_DAYS,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get coverage status for all registered AI systems."""
    # In production, query Supabase registered_ai_systems table
    # Return empty list for now (no systems registered yet)
    systems = []
    report = build_coverage_report(systems, overdue_threshold_days=overdue_days)
    return {
        "systems": report,
        "total": len(report),
        "overdue_count": sum(1 for s in report if s["is_overdue"]),
        "overdue_threshold_days": overdue_days,
        "generated_at": datetime.utcnow().isoformat(),
    }
