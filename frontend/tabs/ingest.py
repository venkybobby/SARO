"""
S-201: SARO Ingest Dashboard Tab

Provides a form-based UI for submitting single AI outputs via
POST /api/v1/ingest, polling status, and displaying results.
"""
from __future__ import annotations

import time
from typing import Any

import requests
import streamlit as st

_SOURCE_MODELS = ["unknown", "grok", "claude", "openai", "sierra", "internal"]
_VERTICALS = [
    "general", "healthcare", "finance", "legal", "hr",
    "customer_support", "education", "government", "retail",
]

_RISK_COLORS = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}


def _api(api_base: str) -> str:
    return api_base.rstrip("/")


def _get_risk_color(score: float | None) -> str:
    if score is None:
        return "#94a3b8"
    if score >= 70:
        return _RISK_COLORS["red"]
    if score >= 40:
        return _RISK_COLORS["yellow"]
    return _RISK_COLORS["green"]


def render(api_base: str, token: str) -> None:
    """Render the ingest tab UI."""
    st.subheader("Submit AI Output for Risk Audit")
    st.caption(
        "SARO never calls external models. Provide any AI-generated output "
        "and receive a risk score, TRACE timeline, and remediation guidance."
    )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = _api(api_base)

    # ── SDK Snippet expander ──────────────────────────────────────────────────
    with st.expander("Python SDK Snippet", expanded=False):
        try:
            resp = requests.get(f"{base}/api/v1/sdk/snippet", headers=headers, timeout=10)
            if resp.status_code == 200:
                snippet_data = resp.json()
                st.code(snippet_data.get("snippet", ""), language="python")
                st.caption(snippet_data.get("description", ""))
            else:
                st.warning(f"Could not fetch SDK snippet ({resp.status_code})")
        except Exception as exc:
            st.warning(f"Could not load SDK snippet: {exc}")

    st.divider()

    # ── Ingestion form ────────────────────────────────────────────────────────
    with st.form("ingest_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            source_model = st.selectbox("Source Model", _SOURCE_MODELS, index=0)
        with col2:
            vertical = st.selectbox("Vertical", _VERTICALS, index=0)

        prompt = st.text_area(
            "Original Prompt",
            placeholder="Enter the prompt sent to the AI model...",
            height=120,
        )
        raw_output = st.text_area(
            "AI Output",
            placeholder="Paste the raw AI-generated output here...",
            height=200,
        )

        submitted = st.form_submit_button("Submit for Audit", use_container_width=True)

    if submitted:
        if not prompt.strip():
            st.error("Prompt is required.")
            return
        if not raw_output.strip():
            st.error("AI Output is required.")
            return

        # Get tenant_id from token (stored in session state by auth flow)
        tenant_id = st.session_state.get("tenant_id", "")
        if not tenant_id:
            st.error("No tenant ID found in session. Please log in again.")
            return

        with st.spinner("Submitting audit..."):
            try:
                resp = requests.post(
                    f"{base}/api/v1/ingest",
                    headers=headers,
                    json={
                        "prompt": prompt.strip(),
                        "raw_output": raw_output.strip(),
                        "source_model": source_model,
                        "tenant_id": tenant_id,
                        "vertical": vertical,
                    },
                    timeout=30,
                )
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                return

        if resp.status_code == 201:
            data = resp.json()
            audit_id = data["audit_id"]
            st.success(f"Audit submitted. ID: `{audit_id}`")
            st.session_state["last_ingest_audit_id"] = audit_id
        else:
            st.error(f"Submission failed ({resp.status_code}): {resp.text[:500]}")
            return

    st.divider()

    # ── Status polling ────────────────────────────────────────────────────────
    st.subheader("Poll Audit Status")

    audit_id_input = st.text_input(
        "Audit ID",
        value=st.session_state.get("last_ingest_audit_id", ""),
        placeholder="Enter audit UUID...",
    )

    col_poll, col_auto = st.columns([1, 1])
    with col_poll:
        poll_now = st.button("Check Status", use_container_width=True)
    with col_auto:
        auto_poll = st.checkbox("Auto-poll (5s)", value=False)

    if auto_poll and audit_id_input:
        time.sleep(5)
        st.rerun()

    if poll_now and audit_id_input:
        _render_audit_status(base, headers, audit_id_input.strip())


def _render_audit_status(base: str, headers: dict, audit_id: str) -> None:
    """Fetch and display audit status."""
    try:
        resp = requests.get(
            f"{base}/api/v1/audits/{audit_id}",
            headers=headers,
            timeout=10,
        )
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return

    if resp.status_code == 404:
        st.warning("Audit not found. Check the ID and try again.")
        return
    if resp.status_code != 200:
        st.error(f"Error fetching status ({resp.status_code}): {resp.text[:300]}")
        return

    data = resp.json()
    status = data.get("status", "unknown")

    # Status badge
    status_colors = {
        "running": "#3b82f6",
        "completed": "#16a34a",
        "failed": "#dc2626",
        "pending": "#ca8a04",
    }
    color = status_colors.get(status, "#94a3b8")
    st.markdown(
        f'<span style="background:{color};color:white;padding:4px 12px;'
        f'border-radius:12px;font-weight:600;font-size:0.85rem">'
        f'{status.upper()}</span>',
        unsafe_allow_html=True,
    )

    if status == "running":
        st.info("Audit is in progress. Refresh in a few seconds.")
        return

    if status == "failed":
        st.error("Audit failed during processing. Check logs for details.")
        return

    # Completed — show metrics
    cols = st.columns(4)
    risk_score = data.get("risk_score")
    mit_pct = data.get("mit_coverage_pct")
    confidence = data.get("confidence_score")
    exceptions = data.get("exceptions_count")

    with cols[0]:
        color = _get_risk_color(risk_score)
        val = f"{risk_score:.1f}" if risk_score is not None else "N/A"
        st.metric("Risk Score", val)

    with cols[1]:
        val = f"{mit_pct:.1f}%" if mit_pct is not None else "N/A"
        st.metric("MIT Coverage", val)

    with cols[2]:
        val = f"{confidence:.2f}" if confidence is not None else "N/A"
        st.metric("Confidence", val)

    with cols[3]:
        val = str(exceptions) if exceptions is not None else "N/A"
        st.metric("Exceptions", val)

    trace_url = data.get("trace_url", "")
    if trace_url:
        st.markdown(f"[View TRACE Timeline]({trace_url})")

    completed_at = data.get("completed_at")
    if completed_at:
        st.caption(f"Completed at: {completed_at}")
