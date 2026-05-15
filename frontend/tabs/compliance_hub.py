"""
Compliance Hub Tab — landing page for the compliance_lead persona.
Recent audits, Claims Matrix, Governance links, Readiness Checklist.
"""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

_RAG_COLORS = {"green": "#16a34a", "amber": "#ca8a04", "red": "#dc2626"}
_FRAMEWORKS = ["EU AI Act", "NIST RMF", "ISO 42001", "AIGP"]

_GOVERNANCE_LINKS = [
    {"label": "DPA Template",       "key": "dpa_template"},
    {"label": "Sub-Processors List", "key": "sub_processors"},
    {"label": "Retention Policy",   "key": "retention_policy"},
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


def _rag_badge(rag: str) -> str:
    color = _RAG_COLORS.get(rag.lower(), "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.8rem;font-weight:700">'
        f'{rag.upper()}</span>'
    )


def _render_recent_audits(audits: list[dict]) -> None:
    st.markdown("### Recent Audits")
    if not audits:
        st.info("No recent audits found.")
        return

    h1, h2, h3, h4 = st.columns([2.5, 1.2, 1.2, 1])
    h1.markdown("**Dataset**")
    h2.markdown("**Date**")
    h3.markdown("**Risk**")
    h4.markdown("**Export**")
    st.divider()

    for i, audit in enumerate(audits[:10]):
        score = audit.get("overall_risk_score")
        color_key = audit.get("risk_color", "")
        hex_c = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}.get(color_key, "#6b7280")
        c1, c2, c3, c4 = st.columns([2.5, 1.2, 1.2, 1])
        c1.markdown(audit.get("dataset_name") or "—")
        c2.markdown((audit.get("created_at") or "")[:10])
        if score is not None:
            c3.markdown(
                f'<span style="background:{hex_c};color:#fff;padding:1px 7px;'
                f'border-radius:4px;font-size:0.8rem;font-weight:600">{score:.1f}</span>',
                unsafe_allow_html=True,
            )
        else:
            c3.markdown("—")
        audit_id = str(audit.get("id", ""))
        with c4:
            st.download_button(
                "JSON",
                data="{}",
                file_name=f"audit_{audit_id[:8]}.json",
                mime="application/json",
                key=f"hub_export_{i}",
                use_container_width=True,
                help=f"Export audit {audit_id[:8]}",
            )


def _render_claims_matrix(claims: dict) -> None:
    st.markdown("### Claims Matrix")
    cols = st.columns(len(_FRAMEWORKS))
    for col, fw in zip(cols, _FRAMEWORKS):
        fw_data = claims.get(fw, {})
        rag = fw_data.get("rag", "amber")
        score = fw_data.get("score")
        with col:
            st.markdown(f"**{fw}**")
            st.markdown(_rag_badge(rag), unsafe_allow_html=True)
            if score is not None:
                st.caption(f"Score: {score:.0f}%")


def _render_governance_links(links: dict) -> None:
    st.markdown("### Governance Documents")
    cols = st.columns(len(_GOVERNANCE_LINKS))
    for col, item in zip(cols, _GOVERNANCE_LINKS):
        url = links.get(item["key"], "#")
        with col:
            st.markdown(f"[{item['label']}]({url})")


def _render_readiness_checklist() -> None:
    st.markdown("### Readiness Checklist")
    for item in _CHECKLIST:
        key = f"chk_{item[:20].replace(' ', '_')}"
        st.checkbox(item, key=key)


def render(token: str) -> None:
    st.header("Compliance Hub")
    st.caption("Your compliance lead landing page — audits, frameworks, and governance at a glance.")

    with st.spinner("Loading compliance hub…"):
        data = _safe_get(token, "/api/v1/compliance/hub")

    if data is None:
        st.warning(
            "Compliance hub data is not available. "
            "This may be a permissions issue or the service is currently offline."
        )
        # Still render checklist as it is local-only
        st.divider()
        _render_readiness_checklist()
        return

    recent_audits: list[dict] = data.get("recent_audits", [])
    claims: dict = data.get("claims_matrix", {})
    gov_links: dict = data.get("governance_links", {})

    _render_recent_audits(recent_audits)
    st.divider()
    _render_claims_matrix(claims)
    st.divider()
    _render_governance_links(gov_links)
    st.divider()

    with st.sidebar:
        _render_readiness_checklist()
