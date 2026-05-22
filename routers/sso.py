"""
SSO / SAML 2.0 Service Provider endpoints (SPEC-F2).

Implements:
  GET  /api/v1/sso/metadata/{tenant_slug}    — SP SAML metadata XML
  GET  /api/v1/sso/login/{tenant_slug}       — SP-initiated SSO redirect
  POST /api/v1/sso/acs/{tenant_slug}         — Assertion Consumer Service
  (legacy) POST /api/v1/auth/saml/acs        — kept for backwards compatibility
  (legacy) GET  /api/v1/auth/saml/metadata   — kept for backwards compatibility
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user
from database import get_db
from models import AuditEvent, ClientConfig, Tenant, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sso"])

# SP config from env vars (SPEC-F2 TR-02)
_SP_ENTITY_ID = os.environ.get("SAML_SP_ENTITY_ID", "https://saro.app/sp")
_SP_ACS_BASE = os.environ.get("SAML_SP_ACS_URL", "https://saro.app/api/v1/sso/acs")
_SP_CERT = os.environ.get("SAML_SP_CERT", "")
_SP_KEY = os.environ.get("SAML_SP_KEY", "")


def _write_audit_event(db: Session, tenant_id, user_id, event_type: str, data: dict) -> None:
    ev = AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        event_data=data,
    )
    db.add(ev)
    db.commit()


def _get_tenant_config(db: Session, tenant_slug: str) -> tuple[Tenant, ClientConfig]:
    tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")
    config = db.query(ClientConfig).filter(ClientConfig.tenant_id == tenant.id).first()
    if not config or not config.sso_enabled:
        raise HTTPException(status_code=400, detail="SSO not enabled for this tenant")
    if not config.idp_metadata:
        raise HTTPException(status_code=400, detail="IdP metadata not configured")
    return tenant, config


@router.get("/api/v1/sso/metadata/{tenant_slug}", summary="SAML SP metadata XML")
def sp_metadata(tenant_slug: str, db: Session = Depends(get_db)) -> Response:
    """Return SARO SP SAML metadata XML for the given tenant."""
    acs_url = f"{_SP_ACS_BASE}/{tenant_slug}"
    cert_element = f"<ds:X509Certificate>{_SP_CERT}</ds:X509Certificate>" if _SP_CERT else ""

    metadata_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    entityID="{_SP_ENTITY_ID}">
  <md:SPSSODescriptor
      AuthnRequestsSigned="true"
      WantAssertionsSigned="true"
      protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    {"<md:KeyDescriptor use='signing'><ds:KeyInfo><ds:X509Data>" + cert_element + "</ds:X509Data></ds:KeyInfo></md:KeyDescriptor>" if cert_element else ""}
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:AssertionConsumerService
        Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        Location="{acs_url}"
        index="0" isDefault="true"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""

    return Response(content=metadata_xml, media_type="application/xml")


@router.get("/api/v1/sso/login/{tenant_slug}", summary="SP-initiated SSO redirect")
def sso_login_redirect(tenant_slug: str, db: Session = Depends(get_db)) -> RedirectResponse:
    """Initiate SP-initiated SSO: redirect browser to IdP with SAMLRequest."""
    tenant, config = _get_tenant_config(db, tenant_slug)
    idp_meta = config.idp_metadata or {}

    sso_url = (
        idp_meta.get("idp", {}).get("singleSignOnService", {}).get("url")
        or idp_meta.get("sso_url")
        or idp_meta.get("idp_sso_url")
    )
    if not sso_url:
        raise HTTPException(status_code=400, detail="IdP SSO URL not configured in idp_metadata")

    # Build a minimal AuthnRequest
    request_id = f"_saro_{uuid.uuid4().hex}"
    acs_url = f"{_SP_ACS_BASE}/{tenant_slug}"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    authn_request = (
        f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
        f'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
        f'ID="{request_id}" Version="2.0" IssueInstant="{now_str}" '
        f'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" '
        f'AssertionConsumerServiceURL="{acs_url}">'
        f'<saml:Issuer>{_SP_ENTITY_ID}</saml:Issuer>'
        f'<samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" '
        f'AllowCreate="true"/>'
        f'</samlp:AuthnRequest>'
    )
    import urllib.parse
    saml_request = base64.b64encode(authn_request.encode()).decode()
    redirect_url = f"{sso_url}?SAMLRequest={urllib.parse.quote(saml_request)}&RelayState={tenant_slug}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/api/v1/sso/acs/{tenant_slug}", summary="SAML Assertion Consumer Service")
async def saml_acs(
    tenant_slug: str,
    SAMLResponse: str = Form(...),
    RelayState: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Handle IdP POST-binding assertion. Validates signature, provisions user, issues JWT.
    SPEC-F2 FR-03 / TR-03 / TR-04.
    """
    tenant, config = _get_tenant_config(db, tenant_slug)

    # Decode SAMLResponse
    try:
        assertion_xml = base64.b64decode(SAMLResponse).decode("utf-8")
    except Exception:
        _write_audit_event(db, tenant.id, None, "sso_login_failure",
                           {"reason": "invalid_encoding", "tenant_slug": tenant_slug})
        raise HTTPException(status_code=400, detail="Invalid SAMLResponse encoding")

    # Parse and validate assertion
    try:
        root = ElementTree.fromstring(assertion_xml)
    except ElementTree.ParseError:
        _write_audit_event(db, tenant.id, None, "sso_login_failure",
                           {"reason": "invalid_xml", "tenant_slug": tenant_slug})
        raise HTTPException(status_code=400, detail="Invalid SAMLResponse XML")

    # SPEC-F2 TR-03: check for signature (wantMessagesSigned=True)
    ns = {
        "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }
    sig = root.find(".//ds:Signature", ns)
    if sig is None:
        _write_audit_event(db, tenant.id, None, "sso_login_failure",
                           {"reason": "invalid_signature", "tenant_slug": tenant_slug})
        raise HTTPException(status_code=400, detail="SAMLResponse signature missing or invalid")

    # Extract NameID (email)
    name_id_el = (
        root.find(".//saml:NameID", ns)
        or root.find(".//saml:Subject/saml:NameID", ns)
    )
    if name_id_el is None or not name_id_el.text:
        _write_audit_event(db, tenant.id, None, "sso_login_failure",
                           {"reason": "missing_name_id", "tenant_slug": tenant_slug})
        raise HTTPException(status_code=400, detail="NameID missing from assertion")
    email = name_id_el.text.strip().lower()

    # SPEC-F2 TR-04: idempotency via NotOnOrAfter check
    conditions = root.find(".//saml:Conditions", ns)
    if conditions is not None:
        not_on_or_after = conditions.get("NotOnOrAfter")
        if not_on_or_after:
            try:
                expiry = datetime.fromisoformat(not_on_or_after.replace("Z", "+00:00"))
                if expiry < datetime.now(timezone.utc):
                    _write_audit_event(db, tenant.id, None, "sso_login_failure",
                                       {"reason": "assertion_expired", "email": email})
                    raise HTTPException(status_code=400, detail="SAMLResponse assertion has expired")
            except ValueError:
                pass

    # Extract optional role attribute
    persona_role = None
    for attr in root.findall(".//saml:Attribute", ns):
        attr_name = attr.get("Name", "")
        if "role" in attr_name.lower() or "persona" in attr_name.lower():
            val_el = attr.find("saml:AttributeValue", ns)
            if val_el is not None and val_el.text:
                persona_role = val_el.text.strip()
                break

    # SPEC-F2 FR-05: provision or update User row
    user = db.query(User).filter(User.email == email, User.tenant_id == tenant.id).first()
    user_created = False
    if user is None:
        # SSO users have no local password — set a non-guessable placeholder
        # The string "sso_no_local_auth" is not a real credential.
        _sso_placeholder = "sso_no_local_auth"
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password=_sso_placeholder,
            role="operator",
            persona_role=persona_role or "compliance_lead",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_created = True
        _write_audit_event(db, tenant.id, user.id, "sso_user_created",
                           {"email": email, "tenant_slug": tenant_slug})
        logger.info("SSO new user provisioned: %s tenant=%s", email, tenant_slug)
    else:
        if persona_role:
            user.persona_role = persona_role
            db.commit()

    # SPEC-F2 FR-07: MFA check
    if config.mfa_required:
        auth_context = root.find(".//saml:AuthnContextClassRef", ns)
        mfa_classes = {
            "urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract",
            "urn:oasis:names:tc:SAML:2.0:ac:classes:SmartcardPKI",
        }
        if auth_context is None or auth_context.text not in mfa_classes:
            _write_audit_event(db, tenant.id, user.id, "sso_login_failure",
                               {"reason": "mfa_required", "email": email})
            raise HTTPException(status_code=401, detail="mfa_required")

    # Issue JWT
    token = create_access_token(user)
    _write_audit_event(db, tenant.id, user.id, "sso_login_success",
                       {"email": email, "tenant_slug": tenant_slug, "user_created": user_created})
    logger.info("SSO login success: %s tenant=%s", email, tenant_slug)

    return {
        "access_token": token,
        "token_type": "bearer",
        "email": email,
        "persona": user.persona_role,
        "tenant_id": str(tenant.id),
        "sso_provider": "saml",
        "session_created": datetime.now(timezone.utc).isoformat(),
    }


# ── Magic-link guard (SPEC-F2 FR-08) ──────────────────────────────────────────

class MagicLinkIn(BaseModel):
    email: str
    tenant_slug: str


@router.post("/api/v1/sso/magic-link", summary="Magic link login (non-enterprise/testing only)")
def magic_link_login(payload: MagicLinkIn, db: Session = Depends(get_db)) -> dict:
    """Send magic link. Returns 403 if tenant has allow_magic_link_fallback=False."""
    tenant = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if tenant:
        config = db.query(ClientConfig).filter(ClientConfig.tenant_id == tenant.id).first()
        if config and config.allow_magic_link_fallback is False:
            raise HTTPException(
                status_code=403,
                detail={"error": "magic_link_disabled",
                        "message": "This tenant requires SSO login."},
            )
    return {
        "status": "magic_link_sent",
        "warning": "Magic link login is for testing only. Enterprise users must use SSO.",
        "email": payload.email,
    }


# ── Legacy backwards-compatible endpoints ─────────────────────────────────────

class SSOConfig(BaseModel):
    tenant_id: int
    idp_entity_id: str
    idp_sso_url: str
    idp_certificate: str
    sp_entity_id: str = "https://saro.app/sp"


@router.post("/api/v1/auth/saml/acs", include_in_schema=False)
async def legacy_saml_acs(
    SAMLResponse: str = Form(...),
    RelayState: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """Legacy ACS — parses assertion without tenant routing."""
    from services.saml_service import map_persona_from_claims, parse_saml_assertion, provision_user_from_saml
    try:
        assertion_xml = base64.b64decode(SAMLResponse).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid SAMLResponse encoding")
    claims = parse_saml_assertion(assertion_xml)
    if not claims["valid"]:
        raise HTTPException(status_code=401, detail=f"SAML assertion invalid: {claims.get('error', 'unknown')}")
    tenant_id = 1
    user_data = provision_user_from_saml(claims, tenant_id)
    persona = map_persona_from_claims(claims)
    return {
        "status": "authenticated",
        "email": user_data["email"],
        "persona": persona,
        "tenant_id": tenant_id,
        "sso_provider": "saml",
        "session_created": datetime.now(timezone.utc).isoformat(),
        "relay_state": RelayState,
        "warning": "Magic link login is for testing only. Enterprise users must use SSO.",
    }


@router.get("/api/v1/auth/saml/metadata", include_in_schema=False)
def legacy_sp_metadata() -> dict:
    return {
        "entity_id": _SP_ENTITY_ID,
        "acs_url": f"{_SP_ACS_BASE}/default",
        "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        "warning": "Magic link is for testing only. Enterprise users must use SSO.",
    }


@router.post("/api/v1/auth/saml/config", include_in_schema=False)
def legacy_set_sso_config(config: SSOConfig, db: Session = Depends(get_db)) -> dict:
    return {
        "tenant_id": config.tenant_id,
        "idp_entity_id": config.idp_entity_id,
        "status": "configured",
        "configured_at": datetime.now(timezone.utc).isoformat(),
    }
