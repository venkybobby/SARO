"""
Remediation workflow and Jira Cloud OAuth2 integration endpoints (SPEC-F3).

PATCH /api/v1/remediation/traces/{id}/remediate          — mark trace as remediated
POST  /api/v1/remediation/traces/{id}/create-jira-issue  — create Jira issue
GET   /api/v1/remediation/audits/{audit_id}/progress     — remediation progress
GET   /api/v1/remediation/oauth/jira/start               — initiate Jira OAuth2
GET   /api/v1/remediation/oauth/jira/callback            — Jira OAuth2 callback
GET   /api/v1/remediation/audits/{audit_id}/traces        — list fail/warn traces
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Audit, AuditEvent, AuditTrace, User
from services.coverage_service import DEFAULT_OVERDUE_DAYS, build_coverage_report
from services.remediation_service import generate_remediation_steps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["remediation"])

_SEVERITY_TO_EFFORT: dict[str, Literal["Low", "Medium", "High"]] = {
    "CRITICAL": "High",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
    "critical": "High",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

_DOMAIN_TO_EFFORT: dict[str, Literal["Low", "Medium", "High"]] = {
    "Discrimination & Toxicity": "High",
    "Privacy & Security": "High",
    "Malicious Use": "High",
    "AI System Safety": "High",
    "Misinformation": "High",
    "Human-Computer Interaction": "Medium",
    "Socioeconomic & Environmental": "Medium",
}

_JIRA_PRIORITY_MAP = {"High": "High", "Medium": "Medium", "Low": "Low"}

_JIRA_CLIENT_ID = os.environ.get("JIRA_CLIENT_ID", "")
_JIRA_CLIENT_SECRET = os.environ.get("JIRA_CLIENT_SECRET", "")
_JIRA_REDIRECT_URI = os.environ.get(
    "JIRA_REDIRECT_URI",
    "https://saro.app/api/v1/remediation/oauth/jira/callback",
)


# ── Pydantic models ───────────────────────────────────────────────────────────


class RemediateTraceIn(BaseModel):
    remediation_note: str


class CreateJiraIssueIn(BaseModel):
    project_key: str


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


# ── Trace remediation endpoints ───────────────────────────────────────────────


@router.patch("/remediation/traces/{trace_id}/remediate")
def remediate_trace(
    trace_id: uuid.UUID,
    payload: RemediateTraceIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Mark an AuditTrace as remediated with a required note."""
    if not payload.remediation_note or not payload.remediation_note.strip():
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body", "remediation_note"],
                    "msg": "Remediation note is required.",
                    "type": "value_error",
                }
            ],
        )

    trace = db.query(AuditTrace).filter(AuditTrace.id == trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="AuditTrace not found")

    # Verify trace belongs to tenant
    audit = db.query(Audit).filter(
        Audit.id == trace.audit_id,
        Audit.tenant_id == current_user.tenant_id,
    ).first()
    if not audit:
        raise HTTPException(status_code=403, detail="Access denied")

    trace.is_remediated = True
    trace.remediated_at = datetime.now(timezone.utc)
    trace.remediated_by_id = current_user.id

    # Add remediation_note — store in detail_json as fallback if column doesn't exist
    try:
        trace.remediation_note = payload.remediation_note.strip()  # type: ignore[attr-defined]
    except AttributeError:
        detail = trace.detail_json or {}
        detail["remediation_note"] = payload.remediation_note.strip()
        trace.detail_json = detail

    db.commit()
    db.refresh(trace)

    # Write AuditEvent
    ev = AuditEvent(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="trace_remediated",
        event_data={"trace_id": str(trace_id), "audit_id": str(trace.audit_id)},
    )
    db.add(ev)
    db.commit()

    return {
        "id": str(trace.id),
        "is_remediated": trace.is_remediated,
        "remediated_at": trace.remediated_at.isoformat() if trace.remediated_at else None,
        "remediated_by_id": str(trace.remediated_by_id) if trace.remediated_by_id else None,
        "remediation_note": payload.remediation_note.strip(),
    }


@router.post("/remediation/traces/{trace_id}/create-jira-issue")
def create_jira_issue(
    trace_id: uuid.UUID,
    payload: CreateJiraIssueIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Create a Jira issue pre-filled from an AuditTrace finding."""
    trace = db.query(AuditTrace).filter(AuditTrace.id == trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="AuditTrace not found")

    audit = db.query(Audit).filter(
        Audit.id == trace.audit_id,
        Audit.tenant_id == current_user.tenant_id,
    ).first()
    if not audit:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get Jira config from tenant settings
    from models import ClientConfig

    config = db.query(ClientConfig).filter(
        ClientConfig.tenant_id == current_user.tenant_id
    ).first()

    if not config or not config.settings_json or "jira_access_token_enc" not in (
        config.settings_json or {}
    ):
        raise HTTPException(
            status_code=400, detail="Jira Cloud not configured for this tenant"
        )

    from services.jira import create_issue as jira_create_issue, decrypt_token

    try:
        access_token = decrypt_token(config.settings_json["jira_access_token_enc"])
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Jira token decryption failed — please re-authorise",
        )

    domain = (trace.check_name or "").split(":")[0].strip()
    effort = _DOMAIN_TO_EFFORT.get(domain, "Medium")
    jira_priority = _JIRA_PRIORITY_MAP.get(effort, "Medium")

    summary = f"[SARO] {trace.check_name or trace.check_type}"
    description = (
        f"Finding: {trace.reason or trace.result}\n\n"
        f"Remediation: {trace.remediation_hint or 'See SARO dashboard'}"
    )

    try:
        issue = jira_create_issue(
            access_token, payload.project_key, summary, description, jira_priority
        )
    except Exception as exc:
        logger.error("Jira issue creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Jira API error: {exc}")

    # Store issue key in detail_json
    detail = trace.detail_json or {}
    detail["jira_issue_key"] = issue.get("key")
    trace.detail_json = detail
    db.commit()

    ev = AuditEvent(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="jira_issue_created",
        event_data={"trace_id": str(trace_id), "jira_key": issue.get("key")},
    )
    db.add(ev)
    db.commit()

    return {
        "jira_issue_key": issue.get("key"),
        "jira_issue_url": issue.get("url"),
        "trace_id": str(trace_id),
    }


@router.get("/remediation/audits/{audit_id}/progress")
def get_remediation_progress(
    audit_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return remediation progress for an audit."""
    audit = db.query(Audit).filter(
        Audit.id == audit_id,
        Audit.tenant_id == current_user.tenant_id,
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    traces = db.query(AuditTrace).filter(
        AuditTrace.audit_id == audit_id,
        AuditTrace.result.in_(["fail", "warn", "flagged", "triggered"]),
    ).all()

    total = len(traces)
    remediated = sum(1 for t in traces if t.is_remediated)
    pct = round(remediated / total * 100, 1) if total else 0.0

    return {
        "audit_id": str(audit_id),
        "total": total,
        "remediated": remediated,
        "percentage": pct,
    }


@router.get("/remediation/audits/{audit_id}/traces")
def list_audit_traces(
    audit_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """List fail/warn traces for an audit grouped by domain with effort estimates."""
    audit = db.query(Audit).filter(
        Audit.id == audit_id,
        Audit.tenant_id == current_user.tenant_id,
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    traces = db.query(AuditTrace).filter(
        AuditTrace.audit_id == audit_id,
        AuditTrace.result.in_(["fail", "warn", "flagged", "triggered"]),
    ).order_by(AuditTrace.gate_id).all()

    def _serialize(t: AuditTrace) -> dict:
        domain = (t.check_name or "").split(":")[0].strip() or t.check_type
        effort = _DOMAIN_TO_EFFORT.get(domain, "Medium")
        detail = t.detail_json or {}
        return {
            "id": str(t.id),
            "check_name": t.check_name,
            "result": t.result,
            "reason": t.reason,
            "remediation_hint": t.remediation_hint,
            "effort_estimate": effort,
            "is_remediated": t.is_remediated,
            "remediated_at": t.remediated_at.isoformat() if t.remediated_at else None,
            "jira_issue_key": detail.get("jira_issue_key"),
            "domain": domain,
        }

    return {
        "audit_id": str(audit_id),
        "traces": [_serialize(t) for t in traces],
        "total": len(traces),
    }


# ── Jira OAuth2 endpoints ─────────────────────────────────────────────────────


@router.get("/remediation/oauth/jira/start")
def jira_oauth_start(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Initiate Jira Cloud OAuth2 (3LO) flow."""
    if not _JIRA_CLIENT_ID:
        raise HTTPException(
            status_code=400,
            detail="Jira OAuth not configured (missing JIRA_CLIENT_ID)",
        )
    import urllib.parse

    params = urllib.parse.urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": _JIRA_CLIENT_ID,
            "scope": "write:issue:jira read:me",
            "redirect_uri": _JIRA_REDIRECT_URI,
            "response_type": "code",
            "prompt": "consent",
            "state": str(current_user.tenant_id),
        }
    )
    return {"oauth_url": f"https://auth.atlassian.com/authorize?{params}"}


@router.get("/remediation/oauth/jira/callback")
def jira_oauth_callback(
    code: str,
    state: Optional[str] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> dict:
    """Handle Jira OAuth2 callback — exchange code for tokens and store encrypted."""
    import httpx

    from services.jira import encrypt_token

    try:
        resp = httpx.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": _JIRA_CLIENT_ID,
                "client_secret": _JIRA_CLIENT_SECRET,
                "code": code,
                "redirect_uri": _JIRA_REDIRECT_URI,
            },
            timeout=30,
        )
        resp.raise_for_status()
        tokens = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Jira token exchange failed: {exc}")

    if state and db:
        try:
            tenant_id = uuid.UUID(state)
            from models import ClientConfig

            config = db.query(ClientConfig).filter(
                ClientConfig.tenant_id == tenant_id
            ).first()
            if config:
                settings = config.settings_json or {}
                settings["jira_access_token_enc"] = encrypt_token(
                    tokens.get("access_token", "")
                )
                settings["jira_refresh_token_enc"] = encrypt_token(
                    tokens.get("refresh_token", "")
                )
                config.settings_json = settings
                db.commit()
        except Exception as exc:
            logger.warning("Failed to store Jira tokens: %s", exc)

    return {"status": "jira_connected", "scope": tokens.get("scope")}


# ── Legacy endpoints (kept for backwards compat) ──────────────────────────────


@router.post("/remediation/steps")
def get_remediation_steps(
    finding: Finding,
    current_user=Depends(get_current_user),
) -> dict:
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
) -> dict:
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
) -> dict:
    systems: list = []
    report = build_coverage_report(systems, overdue_threshold_days=overdue_days)
    return {
        "systems": report,
        "total": len(report),
        "overdue_count": sum(1 for s in report if s["is_overdue"]),
        "overdue_threshold_days": overdue_days,
        "generated_at": datetime.utcnow().isoformat(),
    }
