"""
SARO Streamlit Application
===========================
Smart AI Risk Orchestrator — Enterprise web frontend v3.0.

Run:
    streamlit run frontend/app.py

Requires env vars:
    SARO_API_URL  (default: http://localhost:8000)
"""
from __future__ import annotations

import os

import requests
import streamlit as st

from frontend.tabs import dashboard as dashboard_tab
from frontend.tabs import reports as reports_tab
from frontend.tabs import upload as upload_tab
from frontend.tabs import remedy as remedy_tab
from frontend.tabs import onboarding as onboarding_tab
from frontend import styles

_API_BASE = os.environ.get("SARO_API_URL", "http://localhost:8000").rstrip("/")
_API_IS_LOCALHOST = "localhost" in _API_BASE or "127.0.0.1" in _API_BASE

# Persona → tab mapping (tab_id: (label, module_name))
_TAB_REGISTRY: dict[str, tuple[str, str]] = {
    "dashboard":       ("🏠 Dashboard",          "dashboard"),
    "compliance_hub":  ("🏛️ Compliance Hub",     "compliance_hub"),
    "trace_view":      ("🔍 TRACE View",          "trace_view"),
    "evidence_export": ("📦 Evidence Export",     "trace_view"),
    "risk_summary":    ("📊 Risk Summary",        "risk_summary"),
    "vendor_risk":     ("🏢 Vendor Risk",         "risk_summary"),
    "claims_matrix":   ("📋 Claims Matrix",       "claims_matrix"),
    "how_saro_reasons":("💡 How SARO Reasons",    "how_saro_reasons"),
    "dpa_governance":  ("📄 DPA & Governance",    "governance_docs"),
    "ir_plan":         ("🚨 IR Plan",             "governance_docs"),
    "rule_packs":      ("📦 Rule Packs",          "rule_packs_tab"),
    "coverage_gap":    ("🗺️ Coverage Gap",        "coverage"),
    "remediation":     ("🔧 Remediation",         "remedy"),
    "drift_alerts":    ("📡 Drift Alerts",        "drift"),
    "onboarding":      ("🏢 Onboarding",          "onboarding"),
    "upload":          ("📤 Upload & Scan",       "upload"),
    "admin_settings":  ("⚙️ Admin Settings",      "dashboard"),
}

_PERSONA_TABS: dict[str, list[str]] = {
    "compliance_lead": [
        "dashboard", "compliance_hub", "trace_view", "evidence_export",
        "claims_matrix", "how_saro_reasons", "dpa_governance",
        "onboarding", "upload",
    ],
    "risk_officer": [
        "dashboard", "risk_summary", "vendor_risk", "ir_plan", "trace_view",
    ],
    "ai_auditor": [
        "dashboard", "trace_view", "evidence_export",
        "rule_packs", "coverage_gap", "remediation", "drift_alerts", "upload",
    ],
    "admin": [
        "dashboard", "compliance_hub", "trace_view", "evidence_export",
        "risk_summary", "vendor_risk", "claims_matrix", "how_saro_reasons",
        "dpa_governance", "rule_packs", "coverage_gap", "remediation",
        "drift_alerts", "onboarding", "upload", "admin_settings",
    ],
    # Fallback for legacy roles
    "super_admin": [
        "dashboard", "compliance_hub", "trace_view", "evidence_export",
        "risk_summary", "vendor_risk", "claims_matrix", "how_saro_reasons",
        "dpa_governance", "rule_packs", "coverage_gap", "remediation",
        "drift_alerts", "onboarding", "upload", "admin_settings",
    ],
    "operator": ["dashboard", "upload", "trace_view", "remediation"],
}

_PERSONA_ICONS: dict[str, str] = {
    "compliance_lead": "⚖️",
    "risk_officer": "📊",
    "ai_auditor": "🔍",
    "admin": "⚙️",
    "super_admin": "⚙️",
    "operator": "👤",
}

_PERSONA_LABELS: dict[str, str] = {
    "compliance_lead": "Compliance Lead",
    "risk_officer": "Risk Officer",
    "ai_auditor": "AI Auditor",
    "admin": "Admin",
    "super_admin": "Super Admin",
    "operator": "Operator",
}


def _check_bootstrap() -> dict | None:
    import time
    cache_key = "_health_cache"
    ts_key = "_health_cache_ts"
    now = time.monotonic()
    cached_ts = st.session_state.get(ts_key, 0)
    if now - cached_ts < 30 and cache_key in st.session_state:
        return st.session_state[cache_key]
    try:
        r = requests.get(f"{_API_BASE}/health", timeout=10)
        if r.status_code == 200:
            result = r.json()
            st.session_state[cache_key] = result
            st.session_state[ts_key] = now
            return result
    except Exception:
        pass
    st.session_state[cache_key] = None
    st.session_state[ts_key] = now
    return None


def _do_bootstrap(org_name: str, email: str, password: str) -> bool:
    try:
        resp = requests.post(
            f"{_API_BASE}/api/v1/auth/bootstrap",
            json={"org_name": org_name, "email": email, "password": password},
            timeout=20,
        )
        if resp.status_code == 201:
            st.success(
                f"✅ First-run setup complete — "
                f"tenant and super-admin account created for **{email}**. "
                "Sign in below to begin."
            )
            return True
        elif resp.status_code == 409:
            st.info("Setup already completed — sign in with your existing account.")
            return True
        else:
            detail = resp.json().get("detail", resp.text)
            st.error(f"Bootstrap failed ({resp.status_code}): {detail}")
            return False
    except requests.ConnectionError:
        st.error(
            f"❌ Cannot reach the API at `{_API_BASE}`. "
            "Verify that `SARO_API_URL` is set correctly."
        )
        return False
    except Exception as exc:
        st.error(f"Bootstrap error: {exc}")
        return False


def _do_demo_signup(
    first_name: str,
    last_name: str,
    email: str,
    contact_number: str,
    company_name: str,
    message: str,
) -> bool:
    try:
        resp = requests.post(
            f"{_API_BASE}/api/v1/demo/signup",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "contact_number": contact_number or None,
                "company_name": company_name or None,
                "message": message or None,
            },
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return True
        detail = resp.json().get("detail", resp.text)
        st.error(f"Signup failed ({resp.status_code}): {detail}")
        return False
    except requests.ConnectionError:
        st.error(f"❌ Cannot reach the API at `{_API_BASE}`.")
        return False
    except Exception as exc:
        st.error(f"Signup error: {exc}")
        return False


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SARO — Smart AI Risk Orchestrator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "SARO — Smart AI Risk Orchestrator v3.0"},
)

styles.apply()

for key, default in [
    ("token", None),
    ("user", None),
    ("last_report", None),
    ("demo_submitted", False),
    ("active_tab", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _login(email: str, password: str) -> bool:
    try:
        resp = requests.post(
            f"{_API_BASE}/api/v1/auth/token",
            json={"email": email, "password": password},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        st.session_state["token"] = data["access_token"]

        me_resp = requests.get(
            f"{_API_BASE}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {st.session_state['token']}"},
            timeout=15,
        )
        me_resp.raise_for_status()
        st.session_state["user"] = me_resp.json()
        return True

    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 401:
            st.error("❌ Invalid email or password — check your credentials and try again.")
        elif code == 503:
            st.error(
                f"🔴 **Backend service unavailable (503).**\n\n"
                f"- `SARO_API_URL` is **`{_API_BASE}`** — verify this is the correct backend URL.\n"
                f"- The backend may still be starting — wait ~30 s and retry.\n"
                f"- Check service logs for the **saro-api** deployment."
            )
        else:
            st.error(f"Login failed ({code}): {e}")
        return False
    except requests.ConnectionError:
        st.error(
            f"❌ Cannot connect to the SARO API at **`{_API_BASE}`**.\n\n"
            + (
                "Set `SARO_API_URL` in your deployment environment variables."
                if _API_IS_LOCALHOST
                else "Check that the backend service is running and reachable."
            )
        )
        return False
    except requests.Timeout:
        st.error("⏱ Request timed out — the backend may be cold-starting. Wait 30 s and retry.")
        return False


def _render_login() -> None:
    st.markdown(
        '<div style="text-align:center;padding:40px 0 24px">'
        '<div style="font-size:3rem">🛡️</div>'
        '<h1 style="font-size:2rem;font-weight:800;color:#f1f5f9;margin:8px 0 4px">'
        'SARO</h1>'
        '<p style="color:#64748b;font-size:0.95rem;margin:0">'
        'Smart AI Risk Orchestrator — Enterprise Governance Platform'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    if _API_IS_LOCALHOST:
        st.warning(
            "⚠️ **API not configured.** `SARO_API_URL` is not set — login will fail.\n\n"
            "| Key | Value |\n|---|---|\n"
            "| `SARO_API_URL` | `https://your-saro-api.example.com` |",
        )

    health_data = _check_bootstrap()
    bootstrap_needed = health_data.get("bootstrap_needed") if health_data else None

    if bootstrap_needed is True:
        st.info("🚀 **First-run setup required.** No accounts exist yet — create the super-admin account to begin.")
        with st.form("bootstrap_form"):
            st.subheader("Create super-admin account")
            org_name = st.text_input("Organisation name", placeholder="Acme Financial Group")
            email_bs = st.text_input("Admin email", placeholder="admin@acme.com")
            pw_bs = st.text_input("Password (min 8 characters)", type="password")
            submitted_bs = st.form_submit_button(
                "Create Account & Continue →", use_container_width=True, type="primary"
            )
        if submitted_bs:
            if not org_name or not email_bs or not pw_bs:
                st.warning("All fields are required.")
            elif len(pw_bs) < 8:
                st.warning("Password must be at least 8 characters.")
            else:
                if _do_bootstrap(org_name, email_bs, pw_bs):
                    st.rerun()
        return

    if bootstrap_needed is None and health_data is None:
        st.warning(f"⚠️ Cannot reach the API at `{_API_BASE}`. Refresh to retry.")

    login_tab, demo_tab = st.tabs(["🔐 Sign In", "🚀 Request Demo"])

    with login_tab:
        _, c, _ = st.columns([1, 2, 1])
        with c:
            st.subheader("Sign in to SARO")
            with st.form("login_form"):
                email = st.text_input("Work Email", placeholder="operator@acme.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Sign In →", use_container_width=True, type="primary"
                )
            if submitted:
                if not email or not password:
                    st.warning("Please enter your email and password.")
                else:
                    if _login(email, password):
                        st.rerun()

    with demo_tab:
        _render_demo_signup()


def _render_demo_signup() -> None:
    st.subheader("Request a Demo")
    st.caption(
        "Interested in SARO for your organisation? Submit your details and "
        "our team will schedule a personalised demo within 1–2 business days."
    )

    if st.session_state.get("demo_submitted"):
        st.success(
            "✅ **Request received.** Thank you for your interest in SARO.  \n"
            "Our team will be in touch within 1–2 business days to schedule your demo."
        )
        if st.button("Submit another request"):
            st.session_state["demo_submitted"] = False
            st.rerun()
        return

    with st.form("demo_signup_form"):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First name *", placeholder="Jane")
        with col2:
            last_name = st.text_input("Last name *", placeholder="Smith")

        email = st.text_input("Work email *", placeholder="jane.smith@company.com")
        company_name = st.text_input("Company name", placeholder="Acme Corp")
        contact_number = st.text_input("Contact number", placeholder="+1 555 000 0000")
        message = st.text_area(
            "Tell us about your use case",
            placeholder="We want to audit our NLP models for bias, safety, and EU AI Act compliance…",
            height=100,
        )
        submitted = st.form_submit_button(
            "Request Demo →", use_container_width=True, type="primary"
        )

    if submitted:
        if not first_name or not last_name or not email:
            st.warning("First name, last name, and work email are required.")
        else:
            if _do_demo_signup(first_name, last_name, email, contact_number, company_name, message):
                st.session_state["demo_submitted"] = True
                st.rerun()


def _get_persona(user: dict) -> str:
    """Resolve persona role from user dict, falling back to legacy role mapping."""
    persona = user.get("persona_role") or user.get("role", "operator")
    if persona in _PERSONA_TABS:
        return persona
    return "operator"


def _render_persona_badge(persona: str, email: str) -> None:
    icon = _PERSONA_ICONS.get(persona, "👤")
    label = _PERSONA_LABELS.get(persona, persona.replace("_", " ").title())
    st.markdown(
        f'<div style="margin-bottom:12px">'
        f'<div style="font-size:0.75rem;color:#475569;text-transform:uppercase;'
        f'letter-spacing:0.05em;font-weight:600;margin-bottom:4px">Signed in as</div>'
        f'<div style="font-size:0.85rem;color:#e2e8f0;font-weight:500">{email}</div>'
        f'<div style="margin-top:4px">'
        f'<span style="background:#1e3a5f;color:#60a5fa;padding:2px 10px;border-radius:4px;'
        f'font-size:0.72rem;font-weight:600">{icon} {label}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _load_tab_module(module_name: str):
    """Dynamically import a tab module."""
    import importlib
    try:
        return importlib.import_module(f"frontend.tabs.{module_name}")
    except ImportError:
        return None


def _render_app() -> None:
    user = st.session_state["user"]
    token: str = st.session_state["token"]
    persona = _get_persona(user)

    st.session_state["api_base"] = _API_BASE
    st.session_state["persona"] = persona

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">'
            '<span style="font-size:1.5rem">🛡️</span>'
            '<div>'
            '<div style="font-weight:700;font-size:1rem;color:#f1f5f9">SARO</div>'
            '<div style="font-size:0.72rem;color:#475569;letter-spacing:0.04em">SMART AI RISK ORCHESTRATOR</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        _render_persona_badge(persona, user.get("email", ""))

        st.divider()

        # API / DB health
        try:
            health = requests.get(f"{_API_BASE}/health", timeout=5).json()
            db_status = health.get("database", "unknown")
            db_ok = db_status == "ok"
            st.markdown(
                f'<div style="font-size:0.78rem;color:#475569">'
                f'<span style="color:#4ade80">● API online</span>'
                f'&nbsp;&nbsp;'
                f'<span style="color:{"#4ade80" if db_ok else "#f87171"}">● DB {db_status}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown(
                '<div style="font-size:0.78rem"><span style="color:#f87171">● API offline</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        if persona in ("admin", "super_admin") and st.expander("🔀 Switch Persona"):
            new_persona = st.selectbox(
                "View as",
                options=["admin", "compliance_lead", "risk_officer", "ai_auditor"],
                key="persona_switch",
            )
            if st.button("Apply", key="apply_persona_switch"):
                st.session_state["user"]["persona_role"] = new_persona
                st.rerun()

        if st.button("Sign Out", use_container_width=True):
            st.session_state["token"] = None
            st.session_state["user"] = None
            st.rerun()

        st.markdown(
            '<div style="position:absolute;bottom:20px;left:16px;right:16px;'
            'font-size:0.7rem;color:#334155;text-align:center">'
            'SARO v3.0 — Enterprise AI Governance'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Build persona-filtered tab list ───────────────────────────────────────
    allowed_tab_ids = _PERSONA_TABS.get(persona, _PERSONA_TABS["operator"])
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_tab_ids: list[str] = []
    for tid in allowed_tab_ids:
        if tid not in seen and tid in _TAB_REGISTRY:
            seen.add(tid)
            unique_tab_ids.append(tid)

    tab_labels = [_TAB_REGISTRY[tid][0] for tid in unique_tab_ids]

    if not tab_labels:
        st.error("No tabs available for your persona. Contact your administrator.")
        return

    # Admin gets demo requests tab
    if persona in ("admin", "super_admin"):
        tab_labels.append("📋 Demo Requests")
        unique_tab_ids.append("_demo_requests")

    rendered_tabs = st.tabs(tab_labels)

    for i, (tab_id, tab_obj) in enumerate(zip(unique_tab_ids, rendered_tabs)):
        with tab_obj:
            if tab_id == "_demo_requests":
                _render_demo_requests(token)
                continue

            module_name = _TAB_REGISTRY[tab_id][1]

            # Route to built-in modules first.
            # IMPORTANT: tab_id checks must come BEFORE module_name checks when
            # multiple tab IDs share the same module (e.g. "dashboard" and
            # "admin_settings" both map to module "dashboard").  If the
            # module_name check fires first, render() is called twice in the
            # same Streamlit pass → StreamlitDuplicateElementId on every
            # keyless widget inside that module.
            if tab_id == "admin_settings":
                _render_admin_settings(token)
            elif module_name == "dashboard":
                # Pass tab_key so widgets are namespaced and never collide even
                # if a future persona exposes two dashboard-module tabs at once.
                dashboard_tab.render(token, tab_key=tab_id)
            elif module_name == "upload":
                upload_tab.render(token)
            elif module_name == "remedy" or tab_id == "remediation":
                remedy_tab.render(token)
            elif module_name == "onboarding" or tab_id == "onboarding":
                onboarding_tab.render(token)
            elif module_name == "reports":
                reports_tab.render(token)
            else:
                # Dynamically load new tab modules
                mod = _load_tab_module(module_name)
                if mod and hasattr(mod, "render"):
                    import inspect as _inspect
                    sig = _inspect.signature(mod.render)
                    if "tab_key" in sig.parameters:
                        mod.render(token, tab_key=tab_id)
                    else:
                        mod.render(token)
                else:
                    # Graceful fallback if tab module not yet implemented
                    st.info(f"**{_TAB_REGISTRY[tab_id][0]}** — tab loading…")
                    st.caption(f"Module: `frontend.tabs.{module_name}`")


def _render_demo_requests(token: str) -> None:
    st.header("📋 Demo Requests")

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "pending", "contacted", "converted", "rejected"],
        key="demo_status_filter",
    )

    try:
        param = "" if status_filter == "All" else f"?status={status_filter}"
        resp = requests.get(
            f"{_API_BASE}/api/v1/demo/requests{param}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        resp.raise_for_status()
        requests_data: list[dict] = resp.json()
    except Exception as e:
        st.error(f"Failed to load demo requests: {e}")
        return

    if not requests_data:
        st.markdown(
            styles.empty_state("📋", "No Demo Requests", "No requests match the selected filter."),
            unsafe_allow_html=True,
        )
        return

    st.metric("Total requests", len(requests_data))

    for req in requests_data:
        status_badge = {
            "pending":   "🟡 Pending",
            "contacted": "🟢 Contacted",
            "converted": "✅ Converted",
            "rejected":  "🔴 Rejected",
        }.get(req["status"], req["status"])

        with st.expander(
            f"**{req['first_name']} {req['last_name']}** — {req['email']} — {status_badge}",
            expanded=req["status"] == "pending",
        ):
            c1, c2 = st.columns(2)
            c1.write(f"**Company:** {req.get('company_name') or '—'}")
            c2.write(f"**Phone:** {req.get('contact_number') or '—'}")
            c1.write(f"**Submitted:** {req['created_at'][:19]}")
            c2.write(f"**Status:** {req['status']}")
            if req.get("message"):
                st.write("**Message:**")
                st.write(req["message"])

            new_status = st.selectbox(
                "Update status",
                ["pending", "contacted", "converted", "rejected"],
                index=["pending", "contacted", "converted", "rejected"].index(req["status"]),
                key=f"demo_status_{req['id']}",
            )
            if st.button("Update", key=f"demo_update_{req['id']}"):
                try:
                    patch_resp = requests.patch(
                        f"{_API_BASE}/api/v1/demo/requests/{req['id']}",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"status": new_status},
                        timeout=15,
                    )
                    patch_resp.raise_for_status()
                    st.success(f"Status updated to **{new_status}**.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")


def _render_admin_settings(token: str) -> None:
    """Admin Settings — user management and persona assignment."""
    st.header("⚙️ Admin Settings")

    st.subheader("👤 User Persona Assignment")
    st.caption("Assign a persona role to any user. Personas control which tabs and actions are available.")

    with st.form("persona_assign_form"):
        user_id = st.text_input("User UUID", placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6")
        persona = st.selectbox(
            "Persona Role",
            options=["compliance_lead", "risk_officer", "ai_auditor", "admin"],
            format_func=lambda x: {
                "compliance_lead": "⚖️ Compliance Lead",
                "risk_officer": "📊 Risk Officer",
                "ai_auditor": "🔍 AI Auditor",
                "admin": "⚙️ Admin",
            }.get(x, x),
        )
        submitted = st.form_submit_button("Assign Persona", type="primary")

    if submitted and user_id:
        try:
            resp = requests.patch(
                f"{_API_BASE}/api/v1/auth/users/{user_id}/persona",
                headers={"Authorization": f"Bearer {token}"},
                params={"persona_role": persona},
                timeout=15,
            )
            resp.raise_for_status()
            st.success(f"✅ Persona `{persona}` assigned to user `{user_id}`.")
        except requests.HTTPError as e:
            st.error(f"Failed ({e.response.status_code}): {e.response.json().get('detail', str(e))}")
        except Exception as exc:
            st.error(f"Error: {exc}")

    st.divider()
    st.subheader("🔑 Persona Permissions Reference")
    st.markdown(
        "| Persona | Default Landing | Key Permissions |\n"
        "|---------|----------------|------------------|\n"
        "| ⚖️ Compliance Lead | Compliance Hub | TRACE (executive), evidence export, claims matrix, DPA |\n"
        "| 📊 Risk Officer | Risk Summary | Risk dashboard, vendor risk, IR plan, board PDF |\n"
        "| 🔍 AI Auditor | Dashboard | TRACE (technical), rule packs, coverage gap, remediation |\n"
        "| ⚙️ Admin | Dashboard | All tabs and actions |"
    )


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    if st.session_state["token"] is None:
        _render_login()
    else:
        _render_app()


main()
