"""
SARO Enterprise Client Onboarding Tab (Admin-Only)
====================================================
4-section single-screen form:
  1. Client Details          — company name (uniqueness check), industry, size, contact
  2. Identity Provider       — SSO templates (Okta, Azure AD, Google, PingFederate, Custom)
  3. User Enrollment         — CSV or inline; JIT provisioning toggle
  4. Security & Compliance   — MFA enforcement, non-SSO magic-link fallback
"""
from __future__ import annotations

import csv
import io
from typing import Any

import os

import requests
import streamlit as st

from frontend import styles

_API_BASE = os.environ.get("SARO_API_URL", "http://localhost:8000").rstrip("/")

_IDP_TEMPLATES: dict[str, dict[str, str]] = {
    "Okta": {
        "provider": "okta",
        "label": "Okta",
        "entity_id_hint": "https://{your-domain}.okta.com",
        "sso_url_hint": "https://{your-domain}.okta.com/app/{app-id}/sso/saml",
        "metadata_url_hint": "https://{your-domain}.okta.com/app/{app-id}/sso/saml/metadata",
        "requires_certificate": "true",
    },
    "Azure AD / Entra ID": {
        "provider": "azure_ad",
        "label": "Azure AD / Entra ID",
        "entity_id_hint": "https://sts.windows.net/{tenant-id}/",
        "sso_url_hint": "https://login.microsoftonline.com/{tenant-id}/saml2",
        "metadata_url_hint": "https://login.microsoftonline.com/{tenant-id}/federationmetadata/2007-06/federationmetadata.xml",
        "requires_certificate": "false",
    },
    "Google Workspace": {
        "provider": "google_workspace",
        "label": "Google Workspace",
        "entity_id_hint": "https://accounts.google.com/o/saml2?idpid={idp-id}",
        "sso_url_hint": "https://accounts.google.com/o/saml2/idp?idpid={idp-id}",
        "metadata_url_hint": "",
        "requires_certificate": "true",
    },
    "PingFederate": {
        "provider": "pingfederate",
        "label": "PingFederate",
        "entity_id_hint": "https://{pingfed-host}/pf/federation_metadata.ping",
        "sso_url_hint": "https://{pingfed-host}/idp/SSO.saml2",
        "metadata_url_hint": "https://{pingfed-host}/pf/federation_metadata.ping",
        "requires_certificate": "true",
    },
    "Custom SAML 2.0": {
        "provider": "custom_saml",
        "label": "Custom SAML 2.0",
        "entity_id_hint": "https://idp.yourcompany.com/saml/metadata",
        "sso_url_hint": "https://idp.yourcompany.com/saml/sso",
        "metadata_url_hint": "",
        "requires_certificate": "true",
    },
    "Custom OIDC": {
        "provider": "custom_oidc",
        "label": "Custom OIDC",
        "entity_id_hint": "client-id-here",
        "sso_url_hint": "https://idp.yourcompany.com/oauth2/authorize",
        "metadata_url_hint": "https://idp.yourcompany.com/.well-known/openid-configuration",
        "requires_certificate": "false",
    },
}

_INDUSTRIES = [
    "Financial Services",
    "Healthcare & Life Sciences",
    "Legal & Compliance",
    "Technology & Software",
    "Government & Public Sector",
    "Insurance",
    "Retail & eCommerce",
    "Manufacturing",
    "Education",
    "Other",
]

_SIZES = ["1–50", "51–200", "201–1,000", "1,000+"]


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    return getattr(requests, method)(
        f"{_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def _check_company_unique(token: str, company_name: str) -> bool:
    """Returns True if the company name is available (not already provisioned)."""
    try:
        resp = _api(token, "get", "/api/v1/clients")
        if resp.status_code == 200:
            clients = resp.json()
            return not any(
                c.get("company_name", "").strip().lower() == company_name.strip().lower()
                for c in clients
            )
    except Exception:
        pass
    return True  # optimistic if API unreachable


def _parse_csv_users(csv_text: str) -> list[dict[str, str]]:
    """Parse CSV with columns: email, role (optional)."""
    users: list[dict[str, str]] = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        email = (row.get("email") or row.get("Email") or "").strip()
        role = (row.get("role") or row.get("Role") or "operator").strip().lower()
        if email and "@" in email:
            users.append({"email": email, "role": role if role in ("super_admin", "operator") else "operator"})
    return users


def _submit_onboarding(token: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        resp = _api(token, "post", "/api/v1/clients", json=payload)
        if resp.status_code == 201:
            return resp.json()
        detail = resp.json().get("detail", resp.text)
        st.error(f"Onboarding failed ({resp.status_code}): {detail}")
        return None
    except requests.ConnectionError:
        st.error("Cannot reach the SARO API.")
        return None
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        return None


def _test_sso_connection(token: str, tenant_id: str) -> None:
    with st.spinner("Testing SSO connection…"):
        try:
            resp = _api(token, "post", f"/api/v1/clients/{tenant_id}/test-sso")
            result = resp.json()
            if result.get("status") == "success":
                st.success(f"SSO connection validated successfully. {result.get('message', '')}")
            else:
                errors = result.get("errors", [])
                st.error(f"SSO validation failed: {'; '.join(errors) or result.get('message', 'Unknown error')}")
        except Exception as exc:
            st.error(f"Test connection failed: {exc}")


def render(token: str) -> None:
    styles.apply()
    st.header("Enterprise Client Onboarding")
    st.caption(
        "Provision a new enterprise client with SSO/SCIM identity controls, "
        "user enrollment, and security policies. All actions are immutably logged."
    )
    st.divider()

    # Immutable audit log preview
    with st.expander("🔒 Immutable Audit Log — Recent Provisioning Events", expanded=False):
        try:
            log_resp = _api(token, "get", "/api/v1/clients/audit-log?limit=10")
            log_entries: list[dict] = log_resp.json() if log_resp.status_code == 200 else []
        except Exception:
            log_entries = []

        if log_entries:
            log_lines = [
                f"[{e.get('timestamp','')[:19]}] {e.get('action','').upper():20s} "
                f"client={e.get('company_name','—')}  actor={e.get('actor_email','system')}"
                for e in log_entries
            ]
        else:
            import datetime
            now = datetime.datetime.utcnow()
            log_lines = [
                f"[{now.strftime('%Y-%m-%dT%H:%M:%S')}] SYSTEM_READY          "
                "SARO audit log initialised — all provisioning events recorded here.",
            ]

        st.markdown(styles.audit_log_html(log_lines), unsafe_allow_html=True)
        st.caption(
            "This log is append-only and cryptographically sealed. "
            "Export full log via the API: GET /api/v1/clients/audit-log"
        )
        if log_entries:
            log_export = "\n".join(log_lines)
            st.download_button(
                "Export Audit Log", data=log_export,
                file_name="saro_audit_log.txt", mime="text/plain",
            )

    st.divider()

    # ── Success state ─────────────────────────────────────────────────────────
    if st.session_state.get("onboarding_success"):
        result = st.session_state["onboarding_success"]
        st.success(
            f"**{result['company_name']}** successfully provisioned! "
            f"Tenant ID: `{result['tenant_id']}` | Slug: `{result['slug']}`"
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Users Enrolled", result.get("users_enrolled", 0))
        col2.metric("SSO Provider", result.get("idp_provider") or "—")
        col3.metric("SCIM Enabled", "Yes" if result.get("scim_enabled") else "No")

        if result.get("scim_bearer_token"):
            st.warning(
                "**SCIM Bearer Token — Store this now. It will NOT be shown again.**",
                icon="⚠️",
            )
            st.code(result["scim_bearer_token"], language=None)
            st.caption(f"SCIM Endpoint: `{result.get('scim_endpoint', '')}`")

        if result.get("sso_enabled"):
            st.info(
                f"SSO provisioning instructions have been prepared for **{result['company_name']}**. "
                "Share the dashboard link with your primary contact to begin user onboarding."
            )

        st.divider()
        scim_token_section, test_sso_section, new_client_section = st.columns(3)
        with test_sso_section:
            if st.button("Test SSO Connection", type="secondary"):
                _test_sso_connection(token, result["tenant_id"])
        with new_client_section:
            if st.button("Onboard Another Client", type="primary"):
                st.session_state.pop("onboarding_success", None)
                st.session_state.pop("onboarding_idp_template", None)
                st.rerun()
        return

    # ── Form state ────────────────────────────────────────────────────────────
    if "onboarding_idp_template" not in st.session_state:
        st.session_state["onboarding_idp_template"] = None

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1: Client Details
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("1 / 4   Client Details")

    col1, col2 = st.columns([2, 1])
    with col1:
        company_name = st.text_input(
            "Company Name *",
            placeholder="Acme Financial Group",
            help="Legal registered company name. Must be globally unique within SARO.",
        )
    with col2:
        industry = st.selectbox("Industry", ["— Select —"] + _INDUSTRIES)
        if industry == "— Select —":
            industry = None

    col3, col4, col5 = st.columns(3)
    with col3:
        size = st.selectbox("Company Size", ["— Select —"] + _SIZES)
        if size == "— Select —":
            size = None
    with col4:
        primary_contact_name = st.text_input("Primary Contact Name", placeholder="Jane Smith")
    with col5:
        primary_contact_email = st.text_input(
            "Primary Contact Email", placeholder="jane.smith@acme.com"
        )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2: Identity Provider Configuration
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("2 / 4   Identity Provider Configuration")

    sso_enabled = st.toggle("Enable SSO / Federated Identity", value=True)

    idp_config: dict[str, Any] | None = None

    if sso_enabled:
        st.caption(
            "Select your Identity Provider below to pre-fill configuration. "
            "All SAML 2.0 and OIDC Connect providers are supported."
        )

        # IDP template buttons
        template_cols = st.columns(len(_IDP_TEMPLATES))
        for i, (label, tmpl) in enumerate(_IDP_TEMPLATES.items()):
            with template_cols[i]:
                if st.button(label, key=f"idp_tmpl_{i}", use_container_width=True):
                    st.session_state["onboarding_idp_template"] = tmpl

        selected_tmpl = st.session_state.get("onboarding_idp_template") or {}

        st.markdown("")
        col_a, col_b = st.columns(2)
        with col_a:
            entity_id = st.text_input(
                "Entity ID / Client ID",
                value=selected_tmpl.get("entity_id_hint", ""),
                placeholder="https://your-idp.example.com/metadata",
            )
            sso_url = st.text_input(
                "Single Sign-On URL",
                value=selected_tmpl.get("sso_url_hint", ""),
                placeholder="https://your-idp.example.com/sso",
            )
            metadata_url = st.text_input(
                "Metadata URL (optional — auto-configures fields)",
                value=selected_tmpl.get("metadata_url_hint", ""),
                placeholder="https://your-idp.example.com/metadata.xml",
            )
        with col_b:
            tenant_domain = st.text_input(
                "Tenant Domain (Azure AD / Google)",
                placeholder="yourcompany.onmicrosoft.com",
            )
            requires_cert = selected_tmpl.get("requires_certificate", "true") == "true"
            certificate = st.text_area(
                "X.509 Certificate (PEM)",
                height=120,
                placeholder=(
                    "-----BEGIN CERTIFICATE-----\n"
                    "MIIDpDCCAoy…\n"
                    "-----END CERTIFICATE-----"
                )
                if requires_cert
                else "Not required for OIDC flows",
                disabled=not requires_cert,
            )
            client_secret = st.text_input(
                "Client Secret (OIDC only)",
                type="password",
                placeholder="oidc-client-secret",
                disabled=requires_cert,
            )

        if selected_tmpl:
            provider = selected_tmpl["provider"]
        else:
            provider = "custom_saml"

        idp_config = {
            "provider": provider,
            "entity_id": entity_id or None,
            "sso_url": sso_url or None,
            "metadata_url": metadata_url or None,
            "tenant_domain": tenant_domain or None,
            "certificate": certificate or None,
            "client_secret": client_secret or None,
        }
    else:
        st.info(
            "SSO is disabled for this client. Users will authenticate with SARO-managed credentials. "
            "SSO can be enabled at any time from Client Settings."
        )
        # When SSO is off, magic-link is effectively the auth method — show warning
        st.markdown(styles.magic_link_banner(), unsafe_allow_html=True)

    scim_enabled = st.toggle(
        "Enable SCIM 2.0 Provisioning",
        value=False,
        help="Generates a SCIM endpoint + bearer token for automated user lifecycle management.",
    )
    if scim_enabled:
        st.caption(
            "A SCIM 2.0 endpoint and bearer token will be generated on save. "
            "The token is shown **once** — save it to your IDP immediately."
        )

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3: User Enrollment
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("3 / 4   User Enrollment")

    jit_enabled = st.toggle(
        "Enable JIT (Just-in-Time) Provisioning",
        value=True,
        help="SSO users are automatically provisioned on first login.",
    )

    enrollment_method = st.radio(
        "Initial user enrollment",
        ["Inline (manual)", "CSV upload"],
        horizontal=True,
    )

    initial_users: list[dict[str, str]] = []

    if enrollment_method == "Inline (manual)":
        st.caption("Add users below (one per row). Press **+** to add more.")
        user_rows = st.session_state.get("onboarding_user_rows", [{"email": "", "role": "operator"}])

        updated_rows: list[dict[str, str]] = []
        for idx, row in enumerate(user_rows):
            c1, c2, c3 = st.columns([3, 1, 0.4])
            with c1:
                email_val = st.text_input(
                    f"Email {idx + 1}", value=row["email"], key=f"u_email_{idx}", label_visibility="collapsed",
                    placeholder="user@company.com",
                )
            with c2:
                role_val = st.selectbox(
                    f"Role {idx + 1}", ["operator", "super_admin"],
                    index=0 if row["role"] == "operator" else 1,
                    key=f"u_role_{idx}", label_visibility="collapsed",
                )
            with c3:
                remove = st.button("✕", key=f"u_remove_{idx}", help="Remove this user")
            if not remove:
                updated_rows.append({"email": email_val, "role": role_val})

        col_add, _ = st.columns([1, 5])
        with col_add:
            if st.button("+ Add User"):
                updated_rows.append({"email": "", "role": "operator"})

        st.session_state["onboarding_user_rows"] = updated_rows
        initial_users = [r for r in updated_rows if r["email"].strip() and "@" in r["email"]]

    else:
        st.caption(
            "Upload a CSV with columns `email` and `role` (operator or super_admin). "
            "Maximum 500 users per onboarding."
        )
        csv_template = "email,role\nalice@company.com,operator\nbob@company.com,super_admin\n"
        st.download_button(
            "Download CSV template", csv_template, "saro_user_enrollment.csv", "text/csv"
        )
        uploaded = st.file_uploader("Upload user CSV", type=["csv"], label_visibility="collapsed")
        if uploaded:
            csv_text = uploaded.read().decode("utf-8")
            initial_users = _parse_csv_users(csv_text)
            if initial_users:
                st.success(f"{len(initial_users)} user(s) parsed from CSV.")
                with st.expander("Preview enrolled users"):
                    st.json(initial_users)
            else:
                st.warning("No valid users found in CSV. Check format: email,role headers required.")

    if initial_users:
        st.caption(f"**{len(initial_users)}** user(s) will be enrolled on save.")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4: Security & Compliance
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("4 / 4   Security & Compliance")

    # MFA — locked ON with enterprise badge
    st.markdown(
        '<div class="saro-mfa-locked">'
        '🔒 <b>Multi-Factor Authentication — LOCKED ON</b> — '
        'MFA is mandatory for all users on this tenant. '
        'This cannot be disabled without a signed security exception approved by your CISO. '
        'Compliant with EU AI Act Art. 9, SOC 2 Type II, ISO 27001 A.9.4.'
        '</div>',
        unsafe_allow_html=True,
    )
    # Keep the value as True for the payload — UI is informational only
    mfa_required = True

    st.markdown("")

    allow_magic_link = st.toggle(
        "Allow magic-link (non-SSO) fallback — Testing Only",
        value=False,
        help=(
            "Enables email-based magic-link login as a last-resort fallback. "
            "⚠️ Non-Enterprise / Testing Mode Only — not for production use."
        ),
    )
    if allow_magic_link:
        st.markdown(styles.magic_link_banner(), unsafe_allow_html=True)

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # Submit
    # ═══════════════════════════════════════════════════════════════════════════
    submit_col, _ = st.columns([1, 3])
    with submit_col:
        submitted = st.button(
            "Provision Client",
            type="primary",
            use_container_width=True,
            help="Creates the client, generates SCIM token (if enabled), and logs the event.",
        )

    if submitted:
        errors: list[str] = []

        # Validate Section 1
        if not company_name or len(company_name.strip()) < 2:
            errors.append("Company Name is required (minimum 2 characters).")
        elif not _check_company_unique(token, company_name.strip()):
            errors.append(f"A client named '{company_name.strip()}' already exists.")

        # Validate Section 2
        if sso_enabled and idp_config:
            if not idp_config.get("entity_id") and not idp_config.get("metadata_url"):
                errors.append("SSO enabled: provide Entity ID or Metadata URL.")
            if not idp_config.get("sso_url") and not idp_config.get("metadata_url"):
                errors.append("SSO enabled: provide Single Sign-On URL or Metadata URL.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            payload = {
                "company_name": company_name.strip(),
                "industry": industry,
                "size": size,
                "primary_contact_name": primary_contact_name or None,
                "primary_contact_email": primary_contact_email or None,
                "sso_enabled": sso_enabled,
                "idp_config": idp_config if sso_enabled else None,
                "scim_enabled": scim_enabled,
                "initial_users": initial_users,
                "jit_provisioning_enabled": jit_enabled,
                "mfa_required": mfa_required,
                "allow_magic_link_fallback": allow_magic_link,
            }

            with st.spinner(f"Provisioning {company_name.strip()}…"):
                result = _submit_onboarding(token, payload)

            if result:
                st.session_state["onboarding_success"] = result
                st.session_state.pop("onboarding_user_rows", None)
                st.session_state.pop("onboarding_idp_template", None)
                st.rerun()
