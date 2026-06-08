"""
AI System Inventory Tab (SAR-013 / EU AI Act Art. 49).

Sections:
  1. System registry table — all active AI systems for the tenant
  2. Register new system form
  3. Per-system risk tier assignment (compliance_lead / risk_officer only)
  4. Audit history per system
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_RISK_TIERS = ["unacceptable", "high", "limited", "minimal"]
_TIER_COLORS = {
    "unacceptable": "#dc2626",
    "high":         "#ea580c",
    "limited":      "#ca8a04",
    "minimal":      "#16a34a",
    None:           "#64748b",
    "":             "#64748b",
}
_TIER_ICONS = {
    "unacceptable": "🔴",
    "high":         "🟠",
    "limited":      "🟡",
    "minimal":      "🟢",
}


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return getattr(requests, method)(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def _safe_get(token: str, path: str) -> Any:
    try:
        resp = _api(token, "get", path)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def _tier_badge(tier: str | None) -> str:
    icon = _TIER_ICONS.get(tier or "", "⚪")
    label = (tier or "Not classified").replace("_", " ").title()
    color = _TIER_COLORS.get(tier or "", "#64748b")
    return f'<span style="background:{color}22;color:{color};padding:2px 10px;border-radius:4px;font-size:0.75rem;font-weight:600">{icon} {label}</span>'


def render(token: str) -> None:
    st.title("🤖 AI System Inventory")
    st.caption(
        "EU AI Act Art. 49 system registry. "
        "Risk tier classification is a **human governance decision** — "
        "SARO never auto-classifies systems."
    )

    systems = _safe_get(token, "/api/v1/systems") or []
    persona = st.session_state.get("persona", "")
    can_set_tier = persona in ("compliance_lead", "risk_officer", "admin", "super_admin")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total = len(systems)
    tier_counts = {}
    for s in systems:
        t = s.get("eu_ai_act_risk_tier") or "unclassified"
        tier_counts[t] = tier_counts.get(t, 0) + 1

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Systems", total)
    k2.metric("Unacceptable / High", tier_counts.get("unacceptable", 0) + tier_counts.get("high", 0))
    k3.metric("Limited / Minimal", tier_counts.get("limited", 0) + tier_counts.get("minimal", 0))
    k4.metric("Not Classified", tier_counts.get("unclassified", 0))
    st.divider()

    # ── Register new system ───────────────────────────────────────────────────
    with st.expander("➕ Register New AI System"):
        with st.form("new_system_form"):
            name = st.text_input("System Name *")
            description = st.text_area("Description", height=80)
            purpose = st.text_input("Purpose / Use Case")
            deployment_context = st.selectbox(
                "Deployment Context",
                ["", "production", "staging", "research", "pilot"],
            )
            system_owner = st.text_input("System Owner (email)")
            if st.form_submit_button("Register System", type="primary"):
                if not name.strip():
                    st.error("System Name is required.")
                else:
                    payload = {
                        "name": name.strip(),
                        "description": description.strip() or None,
                        "purpose": purpose.strip() or None,
                        "deployment_context": deployment_context or None,
                        "system_owner": system_owner.strip() or None,
                    }
                    try:
                        resp = _api(token, "post", "/api/v1/systems", json=payload)
                        if resp.status_code == 201:
                            st.success(f"System '{name}' registered.")
                            st.rerun()
                        else:
                            st.error(f"Failed ({resp.status_code}): {resp.text[:200]}")
                    except Exception as exc:
                        st.error(f"Request failed: {exc}")

    # ── System registry table ─────────────────────────────────────────────────
    if not systems:
        st.info("No AI systems registered yet. Use the form above to register your first system.")
        return

    st.subheader(f"Registered Systems ({total})")
    for sys_row in systems:
        sys_id = sys_row.get("id", "")
        tier = sys_row.get("eu_ai_act_risk_tier")
        last_audit = sys_row.get("last_audit_date", "—")
        risk_score = sys_row.get("current_risk_score")

        with st.container():
            col_name, col_tier, col_score, col_audit, col_action = st.columns([3, 2, 1, 2, 1])

            with col_name:
                st.markdown(f"**{sys_row.get('name', '—')}**")
                st.caption(sys_row.get("purpose") or sys_row.get("description") or "")
            with col_tier:
                st.markdown(_tier_badge(tier), unsafe_allow_html=True)
                if can_set_tier:
                    new_tier = st.selectbox(
                        "Set tier",
                        [""] + _RISK_TIERS,
                        index=([""] + _RISK_TIERS).index(tier or "") if tier in _RISK_TIERS else 0,
                        key=f"tier_{sys_id}",
                        label_visibility="collapsed",
                    )
                    if new_tier and new_tier != tier:
                        if st.button("Apply", key=f"apply_tier_{sys_id}"):
                            try:
                                r = _api(
                                    token, "patch", f"/api/v1/systems/{sys_id}",
                                    json={"eu_ai_act_risk_tier": new_tier},
                                )
                                if r.status_code == 200:
                                    st.success(f"Tier set to {new_tier}.")
                                    st.rerun()
                                else:
                                    st.error(f"Failed: {r.text[:100]}")
                            except Exception as exc:
                                st.error(str(exc))
            with col_score:
                if risk_score is not None:
                    color = "#dc2626" if risk_score >= 70 else "#ca8a04" if risk_score >= 40 else "#16a34a"
                    st.markdown(
                        f'<div style="font-size:1.2rem;font-weight:700;color:{color}">{risk_score}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("—")
            with col_audit:
                if last_audit and last_audit != "—":
                    st.caption(str(last_audit)[:10])
                else:
                    st.caption("No audits yet")
            with col_action:
                if st.button("🔍", key=f"view_{sys_id}", help="View audit history"):
                    st.session_state[f"show_audits_{sys_id}"] = not st.session_state.get(f"show_audits_{sys_id}", False)

            # Audit history drawer
            if st.session_state.get(f"show_audits_{sys_id}"):
                audits = _safe_get(token, f"/api/v1/systems/{sys_id}/audits") or []
                if audits:
                    for a in audits[:5]:
                        st.markdown(
                            f"&nbsp;&nbsp;• **{a.get('dataset_name','Unnamed')}** — "
                            f"status: {a.get('status','?')} — "
                            f"{str(a.get('created_at',''))[:10]}",
                        )
                else:
                    st.caption("  No audits linked to this system.")

            st.markdown("---")
