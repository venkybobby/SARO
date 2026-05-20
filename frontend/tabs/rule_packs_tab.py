"""
Rule Pack Management Tab — versioned rule packs with changelogs.
Falls back to demo data when the API is unavailable.
"""
from __future__ import annotations


import requests
import streamlit as st

_DEMO_PACKS = [
    {
        "name": "EU AI Act v1.0",
        "version": "1.0.0",
        "status": "active",
        "changelog": ["Initial release"],
    },
    {
        "name": "NIST RMF v1.0",
        "version": "1.0.0",
        "status": "active",
        "changelog": ["Initial release"],
    },
]

_STATUS_COLORS = {
    "active":     "#16a34a",
    "deprecated": "#ca8a04",
    "draft":      "#3b82f6",
    "inactive":   "#6b7280",
}


def _api(token: str, path: str) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return requests.get(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _fetch_packs(token: str) -> tuple[list[dict], bool]:
    """Return (packs, is_live). Falls back to demo data on any error."""
    try:
        resp = _api(token, "/api/v1/rules/packs")
        resp.raise_for_status()
        data = resp.json()
        # API returns {"packs": [...], "total": N} — extract the list
        packs = data.get("packs", data) if isinstance(data, dict) else data
        return packs if isinstance(packs, list) else _DEMO_PACKS, True
    except Exception:
        return _DEMO_PACKS, False


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get(status.lower(), "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.78rem;font-weight:600">{status.upper()}</span>'
    )


def _render_pack(pack: dict, idx: int) -> None:
    name = pack.get("name", "—")
    version = pack.get("version", "—")
    status = pack.get("status", "unknown")
    last_updated = pack.get("last_updated", "")
    changelog: list[str] = pack.get("changelog", [])

    col1, col2, col3, col4 = st.columns([2.5, 1, 1.2, 1.5])
    col1.markdown(f"**{name}**")
    col2.markdown(f"`{version}`")
    col3.markdown(_status_badge(status), unsafe_allow_html=True)
    col4.markdown(last_updated[:10] if last_updated else "—")

    if changelog:
        with st.expander(f"Changelog — {name}", expanded=False):
            for entry in changelog:
                st.markdown(f"- {entry}")
    else:
        with st.expander(f"Changelog — {name}", expanded=False):
            st.caption("No changelog entries.")


def render(token: str) -> None:
    st.header("Rule Pack Management")
    st.caption("Versioned rule packs for all compliance frameworks. Expand a pack to view its changelog.")

    packs, is_live = _fetch_packs(token)

    if not is_live:
        st.info("API unavailable — showing demo rule packs. Connect the backend to see live data.")

    if not packs:
        st.warning("No rule packs found.")
        return

    # Table header
    h1, h2, h3, h4 = st.columns([2.5, 1, 1.2, 1.5])
    h1.markdown("**Name**")
    h2.markdown("**Version**")
    h3.markdown("**Status**")
    h4.markdown("**Last Updated**")
    st.divider()

    for idx, pack in enumerate(packs):
        _render_pack(pack, idx)
        st.divider()
