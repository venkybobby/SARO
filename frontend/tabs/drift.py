"""
Framework Drift Alerting Tab — detects new framework versions and affected rule packs.
"""
from __future__ import annotations


import requests
import streamlit as st


def _api(token: str, path: str) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return requests.get(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _safe_get(token: str, path: str) -> dict | None:
    try:
        resp = _api(token, path)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        st.error(f"API error ({exc.response.status_code}): {exc}")
        return None
    except Exception as exc:
        st.error(f"Could not reach drift-check endpoint: {exc}")
        return None


def _render_framework_versions(versions: list[dict]) -> None:
    st.markdown("### Current Framework Versions")
    if not versions:
        st.caption("No framework version data available.")
        return

    cols = st.columns(min(len(versions), 4))
    for col, fw in zip(cols, versions):
        with col:
            st.metric(
                fw.get("name", "—"),
                fw.get("current_version", "—"),
                help=f"Latest known: {fw.get('latest_version', '—')}",
            )


def _render_alert(alert: dict, idx: int) -> None:
    fw = alert.get("framework", "Unknown Framework")
    current = alert.get("current_version", "—")
    latest = alert.get("latest_version", "—")
    what_changed: list[str] = alert.get("what_changed", [])
    affected_packs: list[str] = alert.get("affected_rule_packs", [])

    with st.expander(
        f"Alert: {fw} — new version {latest} available (current: {current})",
        expanded=True,
    ):
        c1, c2 = st.columns(2)
        c1.markdown(f"**Current Version:** `{current}`")
        c2.markdown(f"**Available Version:** `{latest}`")

        if what_changed:
            st.markdown("**What Changed:**")
            for item in what_changed:
                st.markdown(f"- {item}")

        if affected_packs:
            st.markdown("**Affected Rule Packs:**")
            for pack in affected_packs:
                st.markdown(
                    f'<span style="background:#3b82f6;color:#fff;padding:2px 8px;'
                    f'border-radius:4px;font-size:0.78rem;margin:2px;display:inline-block">'
                    f'{pack}</span>',
                    unsafe_allow_html=True,
                )
        st.markdown("")  # spacing


def render(token: str) -> None:
    st.header("Framework Drift Alerting")
    st.caption("Monitors compliance framework versions and flags updates that affect your rule packs.")

    with st.spinner("Checking for framework drift…"):
        data = _safe_get(token, "/api/v1/rules/drift-check")

    if data is None:
        st.warning(
            "Drift check service is currently unavailable. "
            "This feature requires the backend to be running with framework version tracking enabled."
        )
        return

    versions: list[dict] = data.get("framework_versions", [])
    alerts: list[dict] = data.get("alerts", [])

    _render_framework_versions(versions)
    st.divider()

    st.markdown("### Drift Alerts")
    if not alerts:
        st.markdown(
            '<div style="background:#16a34a18;border:1px solid #16a34a;border-radius:8px;'
            'padding:16px;text-align:center">'
            '<span style="color:#16a34a;font-size:1.1rem;font-weight:700">'
            '✓ No drift detected — all framework versions are current</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.warning(f"{len(alerts)} framework update(s) detected. Review and update rule packs as needed.")
    for idx, alert in enumerate(alerts):
        _render_alert(alert, idx)
