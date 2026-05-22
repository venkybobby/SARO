"""SAML 2.0 SSO integration service.

Provides assertion parsing, user provisioning from SAML claims, and
persona mapping from IdP attributes. Uses a simplified assertion model
suitable for testing with mock IdPs.
"""
from datetime import datetime, timezone
import xml.etree.ElementTree as ET


PERSONA_MAP = {
    "compliance_lead": "Compliance Lead",
    "risk_officer": "Risk Officer",
    "ai_auditor": "AI Auditor",
    "admin": "AI Auditor",
    "user": "Compliance Lead",
}

SAML_NS = {
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
}


def parse_saml_assertion(assertion_xml: str) -> dict:
    """Parse a SAML 2.0 assertion and extract user attributes.

    Returns:
        {
            "name_id": str,
            "email": str,
            "role": str,
            "tenant_id": str | None,
            "not_on_or_after": str,
            "valid": bool,
            "error": str | None,
        }
    """
    try:
        root = ET.fromstring(assertion_xml)

        # Extract NameID
        name_id_el = root.find(".//saml:NameID", SAML_NS)
        name_id = name_id_el.text if name_id_el is not None else ""

        # Extract Conditions (expiry check)
        conditions = root.find(".//saml:Conditions", SAML_NS)
        not_on_or_after = ""
        if conditions is not None:
            not_on_or_after = conditions.get("NotOnOrAfter", "")

        # Check expiry
        if not_on_or_after:
            try:
                expiry = datetime.fromisoformat(not_on_or_after.replace("Z", "+00:00"))
                if expiry < datetime.now(timezone.utc):
                    return {
                        "name_id": name_id, "email": "", "role": "",
                        "tenant_id": None, "not_on_or_after": not_on_or_after,
                        "valid": False, "error": "Assertion has expired",
                    }
            except ValueError:
                pass

        # Extract attributes
        attributes = {}
        for attr in root.findall(".//saml:Attribute", SAML_NS):
            attr_name = attr.get("Name", "").split("/")[-1].lower()
            values = [v.text for v in attr.findall("saml:AttributeValue", SAML_NS)]
            attributes[attr_name] = values[0] if values else ""

        email = attributes.get("email", attributes.get("emailaddress", name_id))
        role = attributes.get("role", attributes.get("groups", "user"))
        tenant_id = attributes.get("tenantid", attributes.get("organizationid"))

        return {
            "name_id": name_id,
            "email": email,
            "role": role,
            "tenant_id": tenant_id,
            "not_on_or_after": not_on_or_after,
            "valid": True,
            "error": None,
        }
    except ET.ParseError as e:
        return {
            "name_id": "", "email": "", "role": "",
            "tenant_id": None, "not_on_or_after": "",
            "valid": False, "error": f"Invalid SAML XML: {e}",
        }


def map_persona_from_claims(claims: dict) -> str:
    """Map IdP role/group claims to a SARO persona name."""
    role = (claims.get("role") or "").lower()
    for key, persona in PERSONA_MAP.items():
        if key in role:
            return persona
    return "Compliance Lead"  # safe default


def provision_user_from_saml(claims: dict, tenant_id: int) -> dict:
    """Create a user provisioning payload from SAML claims.

    In production this would upsert a User record in Supabase.
    """
    return {
        "email": claims.get("email", ""),
        "tenant_id": tenant_id,
        "persona": map_persona_from_claims(claims),
        "sso_provider": "saml",
        "provisioned_at": datetime.now(timezone.utc).isoformat(),
        "name_id": claims.get("name_id", ""),
    }
