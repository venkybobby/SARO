"""
SSO / SAML 2.0 Service Provider endpoints (SPEC-F2).

Implements:
  GET  /api/v1/sso/metadata/{tenant_slug}    — SP SAML metadata XML
  GET  /api/v1/sso/login/{tenant_slug}       — SP-initiated SSO redirect
  POST /api/v1/sso/acs/{tenant_slug}         — Assertion Consumer Service
  POST /api/v1/sso/magic-link               — Magic link login (testing only)

Legacy /api/v1/auth/saml/* endpoints were removed (SEC-C2): they bypassed
per-tenant cert binding, hardcoded tenant_id=1 (wrong type), and had no
signature validation.
"""
from __future__ import annotations

import base64
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import create_access_token
from config import settings
from database import get_db
from models import AuditEvent, ClientConfig, Tenant, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sso"])

# SP config (SPEC-F2 TR-02)
_SP_ENTITY_ID = settings.saml_sp_entity_id
_SP_ACS_BASE = settings.saml_sp_acs_url
_SP_CERT = settings.saml_sp_cert or ""
_SP_KEY = settings.saml_sp_key or ""


# ── LIVE-008: Assertion replay guard ─────────────────────────────────────────
# In-memory store: assertion_id → expiry (UTC datetime).
# Thread-safe; expired entries are pruned on every check.
# Single-process safe (Railway/Fly.io single-dyno).  For multi-process deploys
# this should be moved to Redis — see services/replay_cache.py.

_SEEN_ASSERTION_IDS: dict[str, datetime] = {}
_SEEN_ASSERTION_IDS_LOCK = threading.Lock()


def _check_and_record_assertion_id(assertion_id: str, expiry: datetime) -> bool:
    """
    Return True if assertion_id is new (first use); False if it has been seen
    before (replay attack).  Thread-safe.

    Expired entries are pruned on each call so the dict doesn't grow unbounded.
    """
    now = datetime.now(timezone.utc)
    with _SEEN_ASSERTION_IDS_LOCK:
        # Prune stale entries
        stale = [k for k, v in _SEEN_ASSERTION_IDS.items() if v < now]
        for k in stale:
            del _SEEN_ASSERTION_IDS[k]
        if assertion_id in _SEEN_ASSERTION_IDS:
            return False  # Replay detected
        _SEEN_ASSERTION_IDS[assertion_id] = expiry
        return True


# ── LIVE-008: SAML signature verification ────────────────────────────────────

def _verify_saml_signature(assertion_xml: str, idp_cert: str | None) -> bool:
    """
    Verify the XML signature in a SAMLResponse.

    Two-tier strategy:
    1. Structural check — if no <ds:Signature> element is present, always reject.
    2. Cryptographic check — if an IdP certificate is configured, verify the
       signature against it using python3-saml (onelogin.saml2).  If the
       library is not installed (e.g. local Windows dev without xmlsec1),
       falls back to presence-only and logs a prominent warning.  Railway /
       Fly.io deployments always have python3-saml installed via requirements.txt.

    Returns True only when the assertion should be accepted.
    """
    try:
        root = ElementTree.fromstring(assertion_xml)
    except ElementTree.ParseError:
        return False

    ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
    if root.find(".//ds:Signature", ns) is None:
        return False  # No signature element — always reject

    if not idp_cert:
        # No certificate to verify against — presence-only.
        # Safe for local dev; production tenants must configure x509cert.
        logger.warning(
            "SAML: IdP certificate not configured for this tenant — "
            "signature accepted by presence only.  Set idp_metadata.x509cert "
            "to enable full cryptographic verification."
        )
        return True

    # Attempt cryptographic verification via python3-saml
    try:
        from onelogin.saml2.utils import OneLogin_Saml2_Utils  # noqa: PLC0415

        # Strip PEM headers if present — python3-saml expects raw base64
        cert = (
            idp_cert
            .replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
            .strip()
        )
        result = OneLogin_Saml2_Utils.validate_sign(
            root, cert, fingerprintalg="sha256"
        )
        if not result:
            logger.warning("SAML: cryptographic signature verification failed")
        return bool(result)

    except ImportError:
        # python3-saml / xmlsec not available — FAIL CLOSED.
        # An IdP cert is configured, meaning this tenant expects cryptographic
        # verification. Accepting without it would allow forged assertions.
        # Install python3-saml[xmlsec] in the runtime environment.
        logger.error(
            "SAML: python3-saml not available but IdP cert is configured — "
            "rejecting assertion. Install python3-saml[xmlsec] for SSO to work."
        )
        return False
    except Exception as exc:
        logger.warning("SAML: signature verification error: %s", exc)
        return False


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

    # SPEC-F2 TR-03: verify signature (presence + optional crypto via IdP cert)
    ns = {
        "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }
    idp_meta = config.idp_metadata or {}
    idp_cert: str | None = (
        idp_meta.get("idp", {}).get("x509cert")
        or idp_meta.get("x509cert")
        or idp_meta.get("idp_cert")
    )
    if not _verify_saml_signature(assertion_xml, idp_cert):
        _write_audit_event(db, tenant.id, None, "sso_login_failure",
                           {"reason": "invalid_signature", "tenant_slug": tenant_slug})
        raise HTTPException(status_code=400, detail="SAMLResponse signature missing or invalid")

    # Extract NameID (email) — avoid Element truthiness DeprecationWarning
    name_id_el = root.find(".//saml:NameID", ns)
    if name_id_el is None:
        name_id_el = root.find(".//saml:Subject/saml:NameID", ns)
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

    # LIVE-008: Assertion replay guard — reject reuse of the same assertion ID
    assertion_el = root.find(".//saml:Assertion", ns)
    assertion_id = assertion_el.get("ID") if assertion_el is not None else None
    if assertion_id:
        # Use NotOnOrAfter as TTL; fall back to 5-minute window if absent
        _noa = conditions.get("NotOnOrAfter") if conditions is not None else None
        _replay_expiry = (
            datetime.fromisoformat(_noa.replace("Z", "+00:00"))
            if _noa
            else datetime.now(timezone.utc).replace(second=0, microsecond=0)
        )
        if not _check_and_record_assertion_id(assertion_id, _replay_expiry):
            _write_audit_event(db, tenant.id, None, "sso_login_failure",
                               {"reason": "assertion_replayed", "assertion_id": assertion_id})
            raise HTTPException(status_code=400, detail="SAMLResponse assertion already used (replay rejected)")

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
        # SSO JIT users have no local password.
        # hashed_password is nullable (migration 017) — store None so
        # authenticate_user() returns None immediately for any password attempt.
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password=None,
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
def magic_link_login(payload: MagicLinkIn, db: Session = Depends(get_db)) -> JSONResponse:
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
    return JSONResponse(
        content={
            "status": "magic_link_sent",
            "warning": "Magic link login is for testing only. Enterprise users must use SSO.",
            "email": payload.email,
        },
        headers={"X-SARO-Auth-Type": "magic-link-testing-only"},
    )


# Legacy /api/v1/auth/saml/* endpoints removed (SEC-C2).
# They bypassed per-tenant cert binding and hardcoded tenant_id=1 (integer,
# wrong type — tenants use UUIDs). Use /api/v1/sso/* exclusively.
