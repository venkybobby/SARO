"""
Risk Summary Tab — board-level risk officer view.
Key metrics, 90-day trend, top findings, What's Changed, vendor risk, board PDF export.
"""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

_RAG_COLORS = {"green": "#16a34a", "amber": "#ca8a04", "red": "#dc2626"}


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


def _rag_badge(rag: str | None) -> str:
    rag = (rag or "amber").lower()
    color = _RAG_COLORS.get(rag, "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:3px 12px;'
        f'border-radius:12px;font-size:0.85rem;font-weight:700">'
        f'{rag.upper()}</span>'
    )


def _render_kpi_bar(summary: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    rag = summary.get("rag_status", "amber")
    color = _RAG_COLORS.get(rag.lower(), "#6b7280")
    c1.markdown(f"**Overall RAG**\n")
    c1.markdown(_rag_badge(rag), unsafe_allow_html=True)
    c2.metric("90-Day Trend", summary.get("trend_label", "—"), help="Direction of avg risk score over 90 days")
    c3.metric(
        "Remediation %",
        f"{summary.get('remediation_pct', 0):.0f}%",
        delta=summary.get("remediation_delta"),
        delta_color="normal",
    )
    c4.metric("Open Findings", summary.get("open_findings", 0), delta_color="inverse")


def _render_trend_chart(trend: list[dict]) -> None:
    if not trend:
        st.info("No trend data available yet.")
        return
    if not _PLOTLY:
        st.warning("Plotly not installed — chart unavailable.")
        return

    dates = [t.get("date") for t in trend]
    scores = [t.get("avg_risk_score") for t in trend]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=scores,
            mode="lines+markers",
            name="Avg Risk Score",
            line=dict(color="#3b82f6", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.06)",
            hovertemplate="<b>%{x}</b><br>Risk Score: <b>%{y:.1f}</b><extra></extra>",
        )
    )
    fig.add_hrect(y0=85, y1=100, fillcolor="#16a34a", opacity=0.07, line_width=0,
                  annotation_text="Low Risk", annotation_position="right",
                  annotation_font=dict(color="#4ade80", size=11))
    fig.add_hrect(y0=50, y1=85, fillcolor="#ca8a04", opacity=0.05, line_width=0,
                  annotation_text="Moderate", annotation_position="right",
                  annotation_font=dict(color="#fbbf24", size=11))
    fig.add_hrect(y0=0, y1=50, fillcolor="#dc2626", opacity=0.07, line_width=0,
                  annotation_text="High Risk", annotation_position="right",
                  annotation_font=dict(color="#f87171", size=11))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"),
        yaxis=dict(range=[0, 100], gridcolor="#1e2d45"),
        xaxis=dict(gridcolor="#1e2d45"),
        height=280,
        margin=dict(l=0, r=80, t=30, b=0),
        title=dict(text="90-Day Risk Score Trend", font=dict(color="#e2e8f0", size=14)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_top_findings(findings: list[dict]) -> None:
    st.markdown("### Top 5 Findings")
    if not findings:
        st.info("No findings to display.")
        return

    h1, h2, h3, h4 = st.columns([2.5, 1.5, 1, 1])
    h1.markdown("**Finding**")
    h2.markdown("**Audit**")
    h3.markdown("**Severity**")
    h4.markdown("**Status**")
    st.divider()

    severity_colors = {"CRITICAL": "#dc2626", "HIGH": "#ea580c", "MEDIUM": "#ca8a04", "LOW": "#16a34a"}
    for f in findings[:5]:
        sev = f.get("severity", "MEDIUM")
        color = severity_colors.get(sev, "#6b7280")
        c1, c2, c3, c4 = st.columns([2.5, 1.5, 1, 1])
        c1.markdown(f.get("name", "—"))
        c2.markdown(f.get("audit_name", "—"))
        c3.markdown(
            f'<span style="color:{color};font-weight:700">{sev}</span>',
            unsafe_allow_html=True,
        )
        c4.markdown(f.get("status", "—"))


def _render_whats_changed(changes: list[dict]) -> None:
    st.markdown("### What's Changed (7-day delta)")
    if not changes:
        st.info("No changes in the last 7 days.")
        return
    for change in changes:
        direction = change.get("direction", "neutral")
        icon = "📈" if direction == "up" else ("📉" if direction == "down" else "➡️")
        st.markdown(f"{icon} **{change.get('label', '—')}** — {change.get('description', '')}")


def _render_vendor_risk(vendors: list[dict]) -> None:
    st.markdown("### Vendor Risk Panel")
    if not vendors:
        st.info("No vendor data available.")
        return

    for v in vendors:
        rag = v.get("rag", "amber")
        color = _RAG_COLORS.get(rag.lower(), "#6b7280")
        st.markdown(
            f'<div style="border-left:4px solid {color};padding:8px 14px;'
            f'margin:6px 0;background:{color}12;border-radius:0 8px 8px 0">'
            f'<b>{v.get("name", "—")}</b> &nbsp; '
            f'<span style="background:{color};color:#fff;padding:1px 8px;'
            f'border-radius:4px;font-size:0.78rem;font-weight:600">{rag.upper()}</span>'
            f'<span style="color:#94a3b8;margin-left:12px;font-size:0.85rem">'
            f'{v.get("note", "")}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render(token: str) -> None:
    st.header("Risk Officer Dashboard")
    st.caption("Board-level risk view — RAG status, trends, findings, and vendor exposure.")

    with st.spinner("Loading risk summary…"):
        summary = _safe_get(token, "/api/v1/risk/summary")
        vendors = _safe_get(token, "/api/v1/risk/vendors")
        delta = _safe_get(token, "/api/v1/risk/whats-changed") or {}

    if not summary:
        st.warning("Risk summary data is unavailable. Check API connectivity.")
        return

    _render_kpi_bar(summary)
    st.divider()
    _render_trend_chart(summary.get("trend_90_days", summary.get("trend", [])))
    st.divider()
    _render_top_findings(summary.get("top_findings", []))
    st.divider()
    _render_whats_changed([delta] if delta else [])
    st.divider()
    _render_vendor_risk(vendors if isinstance(vendors, list) else [])
    st.divider()

    # Board PDF export
    if st.button("Export Board PDF", type="primary"):
        try:
            resp = _api(token, "get", "/api/v1/risk/board-export")
            if resp.status_code == 200:
                st.download_button(
                    "Save Board PDF",
                    data=resp.content,
                    file_name="saro_board_report.pdf",
                    mime="application/pdf",
                    key="board_pdf_dl",
                )
            else:
                st.error(f"Export failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as exc:
            st.error(f"Export error: {exc}")
