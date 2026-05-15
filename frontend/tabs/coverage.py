"""
Coverage Gap Analysis Tab — registered AI systems with RAG audit-age indicators.
Green = audited ≤30 days, Amber = 31-60 days, Red = >60 days or never audited.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

_RAG_COLORS = {"green": "#16a34a", "amber": "#ca8a04", "red": "#dc2626"}
_RAG_LABELS = {
    "green": "Audited (≤30 days)",
    "amber": "Overdue (31-60 days)",
    "red":   "Critical (>60 days / never)",
}


def _api(token: str, path: str) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return requests.get(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _safe_get(token: str, path: str) -> list | None:
    try:
        resp = _api(token, path)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error ({path}): {exc}")
        return None


def _compute_rag(last_audit_date: str | None) -> str:
    if not last_audit_date:
        return "red"
    try:
        last = datetime.fromisoformat(last_audit_date.replace("Z", "+00:00"))
        days_ago = (datetime.now(timezone.utc) - last).days
        if days_ago <= 30:
            return "green"
        if days_ago <= 60:
            return "amber"
        return "red"
    except Exception:
        return "red"


def _days_since(last_audit_date: str | None) -> str:
    if not last_audit_date:
        return "Never"
    try:
        last = datetime.fromisoformat(last_audit_date.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - last).days
        return f"{days}d ago"
    except Exception:
        return "Unknown"


def _rag_pill(rag: str) -> str:
    color = _RAG_COLORS.get(rag, "#6b7280")
    label = _RAG_LABELS.get(rag, rag.upper())
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600">{label}</span>'
    )


def _render_legend() -> None:
    cols = st.columns(3)
    for col, (rag, label) in zip(cols, _RAG_LABELS.items()):
        color = _RAG_COLORS[rag]
        col.markdown(
            f'<span style="background:{color};color:#fff;padding:2px 10px;'
            f'border-radius:12px;font-size:0.8rem;font-weight:600">{label}</span>',
            unsafe_allow_html=True,
        )


def _render_systems(systems: list[dict]) -> None:
    overdue = [s for s in systems if _compute_rag(s.get("last_audit_date")) in ("amber", "red")]
    current = [s for s in systems if _compute_rag(s.get("last_audit_date")) == "green"]

    if overdue:
        st.markdown(f"#### Overdue Systems ({len(overdue)})")
        st.warning(f"{len(overdue)} system(s) require immediate attention.")
        _render_table(overdue, expanded=True)
        st.divider()

    if current:
        st.markdown(f"#### Current Systems ({len(current)})")
        _render_table(current, expanded=False)


def _render_table(systems: list[dict], expanded: bool) -> None:
    h1, h2, h3, h4, h5 = st.columns([2, 1.5, 1.5, 1.2, 1.5])
    h1.markdown("**System**")
    h2.markdown("**Owner**")
    h3.markdown("**Last Audit**")
    h4.markdown("**Days Since**")
    h5.markdown("**Status**")
    st.divider()

    for system in systems:
        last_date = system.get("last_audit_date")
        rag = _compute_rag(last_date)
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1.2, 1.5])
        c1.markdown(f"**{system.get('name', '—')}**")
        c2.markdown(system.get("owner", "—"))
        c3.markdown((last_date or "Never")[:10])
        c4.markdown(_days_since(last_date))
        c5.markdown(_rag_pill(rag), unsafe_allow_html=True)


def render(token: str) -> None:
    st.header("Coverage Gap Analysis")
    st.caption("Audit coverage status for all registered AI systems.")

    _render_legend()
    st.divider()

    with st.spinner("Loading coverage data…"):
        systems = _safe_get(token, "/api/v1/coverage")

    if systems is None:
        return

    if not systems:
        st.success("No AI systems registered yet. Add systems via the API or onboarding flow.")
        return

    # Summary metrics
    rags = [_compute_rag(s.get("last_audit_date")) for s in systems]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Systems", len(systems))
    c2.metric("Current (Green)", rags.count("green"))
    c3.metric("Overdue (Amber)", rags.count("amber"))
    c4.metric("Critical (Red)", rags.count("red"))
    st.divider()

    _render_systems(systems)
