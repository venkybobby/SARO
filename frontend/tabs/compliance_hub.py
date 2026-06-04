"""
Compliance Hub Tab — landing page for the compliance_lead persona.

Sections:
  1. EVF Validation Status  — live Tier 1/2/3 per framework (FR-EVF-11)
  2. Recent Audits          — last 10 completed audits with risk scores
  3. Governance Documents   — DPA, sub-processors, retention policy links
  4. QCO Expiry Alerts      — upcoming QCO expiry warnings (FR-EVF-13)
  5. Readiness Checklist    — sidebar manual checklist
"""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

_EVF_KEY_TO_LABEL: dict[str, str] = {
    "EU_AI_ACT":   "EU AI Act",
    "NIST_AI_RMF": "NIST AI RMF 1.0",
    "AIGP":        "AIGP",
    "ISO_42001":   "ISO 42001",
}

_TIER_CONFIG: dict[str, dict[str, str]] = {
    "tier_1": {"color": "#16a34a", "icon": "✅", "short": "EXTERNALLY REVIEWED"},
    "tier_2": {"color": "#ca8a04", "icon": "⏳", "short": "UNDER REVIEW"},
    "tier_3": {"color": "#64748b", "icon": "🔒", "short": "INTERNAL ONLY"},
}

_GOVERNANCE_LINKS = [
    {"label": "DPA Template",        "key": "dpa_template"},
    {"label": "Sub-Processors List", "key": "sub_processors"},
    {"label": "Retention Policy",    "key": "retention_policy"},
]

_CHECKLIST = [
    "Data processing agreements in place",
    "AI systems registered in inventory",
    "Risk assessments completed for high-risk systems",
    "Human oversight controls documented",
    "Incident response plan reviewed",
    "Annual compliance review scheduled",
]


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return getattr(requests, method)(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def _safe_get(token: str, path: str) -> dict | list | None:
    try:
        resp = _api(token, "get", path)
        if resp.status_code in (403, 404):
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error ({path}): {exc}")
        return None


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_evf_status(evf: dict[str, dict]) -> None:
    """Render the EVF validation tier summary (FR-EVF-11)."""
    st.markdown("### 🔐 EVF Validation Status")
    if not evf:
        st.info("EVF validation status unavailable.")
        return

    cols = st.columns(4)
    for col, (key, label) in zip(cols, _EVF_KEY_TO_LABEL.items()):
        status = evf.get(key, {})
        tier = status.get("tier", "tier_3")
        cfg = _TIER_CONFIG.get(tier, _TIER_CONFIG["tier_3"])
        qco_ref = status.get("qco_reference")
        expires_in = status.get("expires_in_days")

        with col:
            st.markdown(
                f'<div style="border-left:3px solid {cfg["color"]};'
                f'padding-left:8px;margin-bottom:4px">'
                f'<div style="font-size:0.75rem;color:#94a3b8">{label}</div>'
                f'<div style="font-weight:700;color:{cfg["color"]};font-size:0.8rem">'
                f'{cfg["icon"]} {cfg["short"]}</div>'
                + (f'<div style="font-size:0.7rem;color:#64748b">📄 {qco_ref}</div>' if qco_ref else "")
                + (
                    f'<div style="font-size:0.7rem;color:{"#dc2626" if (expires_in or 999) < 30 else "#ca8a04"}">'
                    f'Expires: {expires_in}d</div>' if expires_in is not None else ""
                )
                + "</div>",
                unsafe_allow_html=True,
            )

    # Show approved label for the first tier_1 framework, or global warning
    tier1_items = [
        (k, v) for k, v in evf.items()
        if v.get("tier") == "tier_1"
    ]
    if tier1_items:
        key, status = tier1_items[0]
        st.success(f"✅ Active QCO: **{status.get('label', '')}**")
    else:
        st.warning(
            "No active QCO — all framework references must use Tier 3 approved language. "
            "No external compliance claims permitted until a QCO is issued.",
            icon="⚠️",
        )


def _render_recent_audits(audits: list[dict]) -> None:
    st.markdown("### Recent Audits")
    if not audits:
        st.info("No recent audits found.")
        return

    h1, h2, h3 = st.columns([3, 1.5, 1.5])
    h1.markdown("**Dataset**")
    h2.markdown("**Date**")
    h3.markdown("**Risk**")
    st.divider()

    for audit in audits[:10]:
        score = audit.get("overall_risk_score")
        color_key = audit.get("risk_color", "")
        hex_c = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}.get(color_key, "#6b7280")
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        c1.markdown(audit.get("dataset_name") or "—")
        c2.markdown((audit.get("created_at") or "")[:10])
        if score is not None:
            c3.markdown(
                f'<span style="background:{hex_c};color:#fff;padding:1px 7px;'
                f'border-radius:4px;font-size:0.8rem;font-weight:600">{score:.1f}</span>',
                unsafe_allow_html=True,
            )
        else:
            c3.markdown(audit.get("status", "—"))


def _render_governance_links(links: dict) -> None:
    st.markdown("### Governance Documents")
    cols = st.columns(len(_GOVERNANCE_LINKS))
    for col, item in zip(cols, _GOVERNANCE_LINKS):
        url = links.get(item["key"], "#")
        with col:
            st.markdown(f"[{item['label']}]({url})")


def _render_expiry_alerts(token: str) -> None:
    """Show QCO expiry alerts — T-60/T-30/T-7/EXPIRED (FR-EVF-13)."""
    st.markdown("### 🔔 QCO Expiry Alerts")
    data = _safe_get(token, "/api/v1/evf/qco/expiry-alerts?limit=10")
    if not data:
        st.caption("No expiry alerts.")
        return

    alerts = data if isinstance(data, list) else []
    if not alerts:
        st.success("No active QCO expiry alerts.", icon="✅")
        return

    _NOTIF_STYLE: dict[str, tuple[str, str]] = {
        "EXPIRED":    ("🔴", "#dc2626"),
        "SALES_NOTIFY": ("🚨", "#dc2626"),
        "T_MINUS_7":  ("🟠", "#ea580c"),
        "T_MINUS_30": ("🟡", "#ca8a04"),
        "T_MINUS_60": ("🔵", "#3b82f6"),
    }

    for alert in alerts:
        icon, color = _NOTIF_STYLE.get(alert.get("notification_type", ""), ("⚪", "#94a3b8"))
        qco_ref = alert.get("qco_reference_number", "—")
        fw = alert.get("framework", "—")
        ntype = alert.get("notification_type", "—")
        days = alert.get("expires_in_days")
        days_str = f"{abs(days)}d {'ago' if days < 0 else 'remaining'}" if days is not None else ""
        st.markdown(
            f'<div style="border-left:3px solid {color};padding:6px 10px;'
            f'margin-bottom:6px;background:#0f172a;border-radius:4px">'
            f'{icon} <b style="color:{color}">{ntype}</b> — {fw} — '
            f'<code>{qco_ref}</code> {days_str}'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_readiness_checklist() -> None:
    st.markdown("### Readiness Checklist")
    for item in _CHECKLIST:
        key = f"chk_{item[:20].replace(' ', '_')}"
        st.checkbox(item, key=key)


# ── Main render ───────────────────────────────────────────────────────────────

def render(token: str) -> None:
    st.header("🏛️ Compliance Hub")
    st.caption("Compliance lead landing page — EVF status, audit history, and governance at a glance.")

    with st.spinner("Loading compliance hub…"):
        data = _safe_get(token, "/api/v1/compliance/hub")

    if data is None:
        st.warning(
            "Compliance hub data is not available. "
            "This may be a permissions issue or the service is currently offline."
        )
        st.divider()
        with st.sidebar:
            _render_readiness_checklist()
        return

    recent_audits: list[dict] = data.get("recent_audits", [])
    gov_links: dict = data.get("governance_links", {})

    # EVF validation status — from the hub response (stamped by reports.py)
    evf_raw = data.get("evf_validation_status", {})
    # Normalise: hub returns { "EU_AI_ACT": { tier, label, qco_reference, expires_in_days } }
    evf_by_key: dict[str, dict] = {}
    for key, val in evf_raw.items():
        if isinstance(val, dict):
            evf_by_key[key] = val

    _render_evf_status(evf_by_key)
    st.divider()

    _render_recent_audits(recent_audits)
    st.divider()

    _render_governance_links(gov_links)
    st.divider()

    _render_expiry_alerts(token)
    st.divider()

    with st.sidebar:
        _render_readiness_checklist()
