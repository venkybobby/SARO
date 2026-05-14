"""SSO SAML 2.0 endpoints — Assertion Consumer Service (ACS) and metadata."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from services.saml_service import parse_saml_assertion, provision_user_from_saml, map_persona_from_claims

router = APIRouter(prefix="/api/v1/auth/saml", tags=["sso"])


class SSOConfig(BaseModel):
    tenant_id: int
    idp_entity_id: str
    idp_sso_url: str
    idp_certificate: str
    sp_entity_id: str = "https://saro.ai/sp"


@router.post("/acs")
async def saml_acs(
    SAMLResponse: str = Form(...),
    RelayState: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """SAML 2.0 Assertion Consumer Service endpoint.

    Receives the IdP POST-binding assertion, validates it, provisions the
    user, and returns a session token.
    """
    import base64
    try:
        assertion_xml = base64.b64decode(SAMLResponse).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid SAMLResponse encoding")

    claims = parse_saml_assertion(assertion_xml)

    if not claims["valid"]:
        raise HTTPException(
            status_code=401,
            detail=f"SAML assertion invalid: {claims.get('error', 'unknown')}",
        )

    # Provision user (in production: upsert to Supabase)
    tenant_id = 1  # derive from RelayState or IdP config in production
    user_data = provision_user_from_saml(claims, tenant_id)
    persona = map_persona_from_claims(claims)

    # Return session info (in production: generate JWT)
    return {
        "status": "authenticated",
        "email": user_data["email"],
        "persona": persona,
        "tenant_id": tenant_id,
        "sso_provider": "saml",
        "session_created": datetime.now(timezone.utc).isoformat(),
        "relay_state": RelayState,
    }


@router.get("/metadata")
def sp_metadata():
    """Return SARO Service Provider SAML metadata."""
    return {
        "entity_id": "https://saro.ai/sp",
        "acs_url": "https://saro.ai/api/v1/auth/saml/acs",
        "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
    }


@router.post("/config")
def set_sso_config(
    config: SSOConfig,
    db: Session = Depends(get_db),
):
    """Store SSO configuration for a tenant."""
    # In production: store in Supabase sso_configs table
    return {
        "tenant_id": config.tenant_id,
        "idp_entity_id": config.idp_entity_id,
        "status": "configured",
        "configured_at": datetime.now(timezone.utc).isoformat(),
    }
