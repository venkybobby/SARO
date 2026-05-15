"""
TRACE View Tab — standalone TRACE timeline for any audit ID.
Shows 6-step pipeline: Ingest, Classify, Match, Score, Explain, Remediate.
Executive / Technical toggle, JSON + PDF export.
"""
from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st

_STEPS = [
    {"key": "ingest",    "label": "Ingest"},
    {"key": "classify",  "label": "Classify"},
    {"key": "match",     "label": "Match"},
    {"key": "score",     "label": "Score"},
    {"key": "explain",   "label": "Explain"},
    {"key": "remediate", "label": "Remediate"},
]

_STATUS_COLORS = {
    "done":    ("#16a34a", "✓"),
    "pass":    ("#16a34a", "✓"),
    "warn":    ("#ca8a04", "⚠"),
    "fail":    ("#dc2626", "✗"),
    "pending": ("#6b7280", "…"),
}


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
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error ({path}): {exc}")
        return None


def _status_badge(status: str) -> str:
    color, icon = _STATUS_COLORS.get(status, ("#6b7280", "?"))
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8rem;font-weight:600">'
        f'{icon} {status.upper()}</span>'
    )


def _render_step(step_def: dict, step_data: dict | None, technical: bool) -> None:
    label = step_def["label"]
    if step_data:
        status = step_data.get("status", "done")
        confidence = step_data.get("confidence")
        detail = step_data.get("detail", "")
        rules = step_data.get("rules", [])
    else:
        status = "pending"
        confidence = None
        detail = ""
        rules = []

    color, icon = _STATUS_COLORS.get(status, ("#6b7280", "?"))
    conf_str = f" · Confidence: {confidence:.0%}" if confidence is not None else ""

    with st.expander(f"{icon} {label}{conf_str}", expanded=(status in ("fail", "warn"))):
        st.markdown(_status_badge(status), unsafe_allow_html=True)
        if confidence is not None:
            st.progress(min(max(confidence, 0.0), 1.0), text=f"Confidence: {confidence:.0%}")
        if detail:
            st.markdown(f"**Detail:** {detail}")
        if technical:
            if rules:
                st.markdown("**Matched Rules:**")
                for r in rules:
                    st.markdown(f"- `{r}`")
            if step_data and step_data.get("raw"):
                with st.expander("Raw step data"):
                    st.json(step_data["raw"])


def _render_trace(token: str, audit_id: str, technical: bool) -> None:
    with st.spinner("Loading trace…"):
        trace = _safe_get(token, f"/api/v1/audit/{audit_id}/trace")

    if not trace:
        st.warning("No trace data found for this audit ID.")
        return

    steps_map: dict[str, dict] = {}
    for s in trace.get("steps", []):
        steps_map[s.get("key", "").lower()] = s

    st.markdown("#### 6-Step TRACE Timeline")
    for step_def in _STEPS:
        _render_step(step_def, steps_map.get(step_def["key"]), technical)

    st.divider()
    _render_exports(token, audit_id, trace)


def _render_exports(token: str, audit_id: str, trace: dict) -> None:
    st.markdown("#### Export")
    col_json, col_pdf, _ = st.columns([1, 1, 3])

    with col_json:
        st.download_button(
            "Download JSON",
            data=json.dumps(trace, indent=2, default=str),
            file_name=f"saro_trace_{audit_id[:8]}.json",
            mime="application/json",
            use_container_width=True,
        )

    with col_pdf:
        if st.button("Download PDF", use_container_width=True, key="trace_pdf_btn"):
            try:
                resp = _api(token, "get", f"/api/v1/audit/{audit_id}/export/pdf")
                if resp.status_code == 200:
                    st.download_button(
                        "Save PDF",
                        data=resp.content,
                        file_name=f"saro_trace_{audit_id[:8]}.pdf",
                        mime="application/pdf",
                        key="trace_pdf_dl",
                    )
                else:
                    st.info("PDF export is not available for this audit.")
            except Exception as exc:
                st.error(f"PDF export failed: {exc}")


def render(token: str) -> None:
    st.header("TRACE View")
    st.caption("Step-by-step AI explainability timeline for any audit.")

    col_id, col_mode = st.columns([3, 1])
    with col_id:
        audit_id = st.text_input(
            "Audit ID",
            placeholder="Enter audit ID…",
            label_visibility="collapsed",
        )
    with col_mode:
        technical = st.toggle("Technical mode", value=False)

    if not audit_id:
        st.info("Enter an audit ID above to load its TRACE timeline.")
        return

    _render_trace(token, audit_id.strip(), technical)
