"""
SARO Persona RBAC service.

Four personas gate access to tabs and actions:
  compliance_lead — executive TRACE, evidence export, claims matrix, DPA, onboarding
  risk_officer    — risk summary, vendor risk, IR plan, read-only TRACE
  ai_auditor      — technical TRACE, rule packs, coverage gap, remediation, drift alerts
  admin           — all actions
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status

from auth import get_current_user

if TYPE_CHECKING:
    from models import User

# ── Permission matrix ─────────────────────────────────────────────────────────

PERSONA_PERMISSIONS: dict[str, dict] = {
    "compliance_lead": {
        "tabs": [
            "dashboard", "compliance_hub", "trace_view", "evidence_export",
            "claims_matrix", "how_saro_reasons", "dpa_governance", "ir_plan",
            "onboarding", "upload",
        ],
        "allowed_actions": [
            "evidence_export", "verify_chain", "onboarding",
            "trace_executive", "claims_matrix", "dpa",
        ],
        "denied_actions": [
            "rule_pack_admin", "gdpr_erasure", "admin_settings",
            "rule_packs", "coverage_gap", "remediation",
        ],
        "trace_mode": "executive",
    },
    "risk_officer": {
        "tabs": ["dashboard", "risk_summary", "vendor_risk", "ir_plan", "trace_view"],
        "allowed_actions": [
            "risk_summary", "vendor_risk", "board_pdf_export",
            "ir_plan", "trace_executive",
        ],
        "denied_actions": [
            "rule_pack_admin", "gdpr_erasure", "admin_settings",
            "remediation", "claims_matrix",
        ],
        "trace_mode": "executive",
    },
    "ai_auditor": {
        "tabs": [
            "dashboard", "trace_view", "evidence_export", "rule_packs",
            "coverage_gap", "remediation", "drift_alerts", "upload",
        ],
        "allowed_actions": [
            "trace_technical", "rule_packs", "coverage_gap",
            "remediation", "drift_alerts", "audit_crud",
        ],
        "denied_actions": [
            "gdpr_erasure", "risk_summary_board", "claims_matrix", "admin_settings",
        ],
        "trace_mode": "technical",
    },
    "admin": {
        "tabs": [
            "dashboard", "compliance_hub", "trace_view", "evidence_export",
            "risk_summary", "vendor_risk", "claims_matrix", "how_saro_reasons",
            "dpa_governance", "ir_plan", "rule_packs", "coverage_gap",
            "remediation", "drift_alerts", "onboarding", "upload", "admin_settings",
        ],
        "allowed_actions": ["*"],
        "denied_actions": [],
        "trace_mode": "technical",
    },
}

# Fallback mapping from legacy role field to persona
_ROLE_TO_PERSONA: dict[str, str] = {
    "super_admin": "admin",
    "operator": "compliance_lead",
}


# ── Core helpers ──────────────────────────────────────────────────────────────


def get_persona_role(user: "User | dict") -> str:
    """Return the persona role for a user object or dict.

    Checks the `persona_role` attribute/key first; falls back to mapping the
    legacy `role` field via _ROLE_TO_PERSONA.
    """
    if isinstance(user, dict):
        persona = user.get("persona_role")
        role = user.get("role", "operator")
    else:
        persona = getattr(user, "persona_role", None)
        role = getattr(user, "role", "operator")

    if persona and persona in PERSONA_PERMISSIONS:
        return persona
    return _ROLE_TO_PERSONA.get(role, "compliance_lead")


def get_allowed_tabs(persona_role: str) -> list[str]:
    """Return the list of tab IDs accessible to the given persona."""
    config = PERSONA_PERMISSIONS.get(persona_role, PERSONA_PERMISSIONS["compliance_lead"])
    return config["tabs"]


def check_permission(persona_role: str, action: str) -> bool:
    """Return True if the persona is allowed to perform the given action."""
    config = PERSONA_PERMISSIONS.get(persona_role)
    if not config:
        return False
    if action in config["denied_actions"]:
        return False
    allowed = config["allowed_actions"]
    return "*" in allowed or action in allowed


def get_trace_mode(persona_role: str) -> str:
    """Return 'executive' or 'technical' TRACE mode for the persona."""
    config = PERSONA_PERMISSIONS.get(persona_role, PERSONA_PERMISSIONS["compliance_lead"])
    return config["trace_mode"]


# ── Identity-provider helpers ─────────────────────────────────────────────────


def detect_persona_from_jwt(claims: dict) -> str:
    """Detect persona from decoded JWT claims.

    Checks `persona_role`, then `persona`, then falls back via `role`.
    """
    for key in ("persona_role", "persona"):
        value = claims.get(key)
        if value and value in PERSONA_PERMISSIONS:
            return value
    role = claims.get("role", "operator")
    return _ROLE_TO_PERSONA.get(role, "compliance_lead")


def detect_persona_from_saml(attributes: dict) -> str:
    """Detect persona from SAML attribute assertions.

    Checks `persona_role`, `role`, and the Microsoft WS-Federation role claim.
    """
    ms_role_claim = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
    for key in ("persona_role", "role", ms_role_claim):
        value = attributes.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if value:
            if value in PERSONA_PERMISSIONS:
                return value
            mapped = _ROLE_TO_PERSONA.get(value)
            if mapped:
                return mapped
    return "compliance_lead"


# ── FastAPI dependency factory ────────────────────────────────────────────────


def persona_required(roles: list[str]):
    """FastAPI dependency factory for persona-based access control."""

    def dependency(current_user=Depends(get_current_user)):
        persona = get_persona_role(current_user)
        if "admin" in roles or persona in roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for persona: {persona}",
        )

    return dependency
