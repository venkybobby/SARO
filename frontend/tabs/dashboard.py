"""
Screens:
  - KPI summary bar   (total audits, avg risk, pending remediations, coverage)
  - Risk trend chart  (30-day rolling risk score)
  - Audit table       (filterable, risk colour-coded, exception counts)
  - Audit detail      (4 sub-tabs: Overview | Findings | TRACE | REMEDIATE)
    - TRACE: full, untruncated chain-of-thought timeline
    - REMEDIATE: operator remediation workflow
SARO Enterprise Audit Dashboard Tab v2.2
Screens:
  - KPI summary bar         — total audits, avg risk, pending remediations, MIT coverage
  - Risk trend chart        — 90-day Plotly line chart (zoomable, interactive)
  - [ + AUDIT NEW OUTPUT ]  — modal form for universal AI output ingestion
  - Audit table             — sortable/filterable, risk colour-coded, remediation badges
  - Audit detail panel      — 4 tabs: Overview | Findings | TRACE | REMEDIATE
    - TRACE: 6-step visual timeline, full untruncated chain-of-thought,
             executive/technical toggle (default Summary), confidence badge,
             deviation callouts, HITL detection, signed JSON + PDF export
    - REMEDIATE: numbered AI fix steps, HITL detection, copy/markdown/jira export,
                 GitHub correlation, effort estimates, progress tracking
"""
from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
import requests
import streamlit as st

from frontend import styles

_SOURCE_MODELS = ["grok", "claude", "openai", "sierra", "internal", "unknown"]

_RISK_COLORS = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}
_RISK_LABELS = {"green": "LOW RISK", "yellow": "MODERATE RISK", "red": "HIGH RISK"}
_RESULT_BADGE = {
    "pass":      ("✓", "#16a34a"),
    "warn":      ("⚠", "#ca8a04"),
    "fail":      ("✗", "#dc2626"),
    "flagged":   ("⚑", "#dc2626"),
    "triggered": ("!", "#9333ea"),
}

# ── Plotly dark theme defaults ─────────────────────────────────────────────────

_PLOTLY_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
    xaxis=dict(gridcolor="#1e2d45", linecolor="#1e2d45", tickcolor="#1e2d45"),
    yaxis=dict(gridcolor="#1e2d45", linecolor="#1e2d45", tickcolor="#1e2d45"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1e2d45"),
    hoverlabel=dict(bgcolor="#1a2035", bordercolor="#2d3f5e", font_color="#e2e8f0"),
    margin=dict(l=0, r=80, t=40, b=0),
)


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


# ── KPI Bar ───────────────────────────────────────────────────────────────────


def _render_kpi_bar(kpis: dict[str, Any]) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Audits", kpis.get("total_audits", 0))
    c2.metric("Completed", kpis.get("completed_audits", 0))
    c3.metric(
        "Avg Risk Score",
        f"{kpis['avg_risk_score']:.1f}" if kpis.get("avg_risk_score") is not None else "—",
        help="Higher = lower risk. ≥85 = Low Risk, 50–84 = Moderate, <50 = High.",
    )
    c4.metric(
        "Avg MIT Coverage",
        f"{kpis['avg_mit_coverage']:.1f}%" if kpis.get("avg_mit_coverage") is not None else "—",
    )
    c5.metric(
        "Pending Remediations",
        kpis.get("pending_remediations", 0),
        delta=None,
        delta_color="inverse",
    )


# ── Risk Trend Chart ──────────────────────────────────────────────────────────


def _render_risk_trend(trend: list[dict[str, Any]]) -> None:
    if not trend:
        st.markdown(
            styles.empty_state(
                "📈",
                "No trend data yet",
                "Complete your first audit from the Upload & Scan tab to populate the 90-day risk trend.",
            ),
            unsafe_allow_html=True,
        )
        return

    dates = [t["date"] for t in trend]
    scores = [t["avg_risk_score"] for t in trend]

    fig = go.Figure()

    # Filled area under the line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=scores,
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.06)",
            mode="lines+markers",
            name="Avg Risk Score",
            line=dict(color="#3b82f6", width=2.5),
            marker=dict(size=6, color="#3b82f6", line=dict(color="#1a2035", width=2)),
            hovertemplate="<b>%{x}</b><br>Risk Score: <b>%{y:.1f}</b><extra></extra>",
        )
    )

    # Reference bands
    fig.add_hrect(
        y0=85, y1=100, fillcolor="#16a34a", opacity=0.07, line_width=0,
        annotation_text="Low Risk ≥85", annotation_position="right",
        annotation_font=dict(color="#4ade80", size=11),
    )
    fig.add_hrect(
        y0=50, y1=85, fillcolor="#ca8a04", opacity=0.05, line_width=0,
        annotation_text="Moderate 50–84", annotation_position="right",
        annotation_font=dict(color="#fbbf24", size=11),
    )
    fig.add_hrect(
        y0=0, y1=50, fillcolor="#dc2626", opacity=0.07, line_width=0,
        annotation_text="High Risk <50", annotation_position="right",
        annotation_font=dict(color="#f87171", size=11),
    )

    layout = dict(**_PLOTLY_LAYOUT)
    layout.update(
        title=dict(text="90-Day Risk Score Trend", font=dict(color="#e2e8f0", size=14)),
        xaxis_title="Date",
        yaxis_title="Risk Score (0–100)",
        yaxis=dict(range=[0, 100], gridcolor="#1e2d45"),
        height=300,
        dragmode="zoom",
        selectdirection="h",
    )
    fig.update_layout(**layout)
    fig.update_xaxes(
        rangeslider=dict(visible=True, bgcolor="#12172a", bordercolor="#1e2d45", thickness=0.05),
        rangeselector=dict(
            buttons=[
                dict(count=7,  label="7d",  step="day",  stepmode="backward"),
                dict(count=30, label="30d", step="day",  stepmode="backward"),
                dict(count=90, label="90d", step="day",  stepmode="backward"),
                dict(step="all", label="All"),
            ],
            bgcolor="#1a2035",
            activecolor="#243050",
            bordercolor="#2d3f5e",
            font=dict(color="#94a3b8"),
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ── Audit Table ───────────────────────────────────────────────────────────────


def _risk_badge_html(color: str | None, score: float | None) -> str:
    return styles.risk_badge_html(color, score)


def _render_audit_table(audits: list[dict[str, Any]], tab_key: str = "dashboard") -> int | None:
    """Render the sortable audit table. Returns selected audit index or None."""
    if not audits:
        st.markdown(
            styles.empty_state(
                "🛡️",
                "No audits yet",
                "Submit your first batch of AI outputs to begin governance tracking.",
            ),
            unsafe_allow_html=True,
        )
        st.button("+ Audit New Output", type="primary", key=f"{tab_key}_empty_new_btn")
        return None

    # Filters
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search = st.text_input(
            "Search by dataset name",
            placeholder="Filter audits…",
            label_visibility="collapsed",
            key=f"{tab_key}_search",
        )
    with col_f2:
        status_filter = st.selectbox(
            "Status", ["All", "completed", "failed", "pending", "running"],
            label_visibility="collapsed",
            key=f"{tab_key}_status_filter",
        )
    with col_f3:
        risk_filter = st.selectbox(
            "Risk Level", ["All", "Low Risk (≥85)", "Moderate (50–84)", "High Risk (<50)"],
            label_visibility="collapsed",
            key=f"{tab_key}_risk_filter",
        )

    # Apply filters
    filtered = audits
    if search:
        filtered = [a for a in filtered if search.lower() in (a.get("dataset_name") or "").lower()]
    if status_filter != "All":
        filtered = [a for a in filtered if a.get("status") == status_filter]
    if risk_filter != "All":
        if risk_filter.startswith("Low"):
            filtered = [a for a in filtered if (a.get("overall_risk_score") or 0) >= 85]
        elif risk_filter.startswith("Moderate"):
            filtered = [a for a in filtered if 50 <= (a.get("overall_risk_score") or 0) < 85]
        elif risk_filter.startswith("High"):
            filtered = [a for a in filtered if 0 < (a.get("overall_risk_score") or 101) < 50]

    st.caption(f"Showing {len(filtered)} of {len(audits)} audit(s)")

    # Table header
    h1, h2, h3, h4, h5, h6, h7 = st.columns([2.5, 1.2, 1.5, 0.9, 0.9, 0.9, 0.8])
    h1.markdown("**Dataset**")
    h2.markdown("**Date**")
    h3.markdown("**Risk Score**")
    h4.markdown("**Status**")
    h5.markdown("**Exceptions**")
    h6.markdown("**Remediated**")
    h7.markdown("**Action**")
    st.divider()

    selected: int | None = None
    for idx, audit in enumerate(filtered):
        score = audit.get("overall_risk_score")
        color = audit.get("risk_color")
        exceptions = audit.get("exceptions_count", 0)
        remediated = audit.get("remediated_count", 0)
        status = audit.get("status", "—")
        dataset = audit.get("dataset_name") or "Unnamed Dataset"
        created = (audit.get("created_at") or "")[:10]
        rem_badge = " 🔴" if audit.get("remediation_required") else ""

        status_icon = {"completed": "✅", "failed": "❌", "pending": "⏳", "running": "🔄"}.get(status, "—")

        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.5, 1.2, 1.5, 0.9, 0.9, 0.9, 0.8])
        c1.markdown(f"**{dataset}**{rem_badge}")
        c2.markdown(created)
        if score is not None and color:
            hex_c = _RISK_COLORS.get(color, "#6b7280")
            c3.markdown(
                f'<span style="background:{hex_c};color:#fff;padding:1px 7px;border-radius:4px;'
                f'font-size:0.8rem;font-weight:600">{score:.1f}</span>',
                unsafe_allow_html=True,
            )
        else:
            c3.markdown("—")
        c4.markdown(f"{status_icon} {status}")
        c5.markdown(str(exceptions))
        c6.markdown(f"{remediated}/{exceptions}" if exceptions else "—")
        with c7:
            if st.button("View", key=f"view_audit_{idx}", use_container_width=True):
                selected = idx

    return selected


# ── TRACE View ────────────────────────────────────────────────────────────────


def _render_trace_view(token: str, audit_id: str, dataset_name: str) -> None:
    st.markdown("### TRACE — AI Explainability & Chain-of-Thought")
    st.caption(f"Full, untruncated audit trail for `{audit_id}` — zero truncation, zero ambiguity.")

    with st.spinner("Loading trace data…"):
        trace = _safe_get(token, f"/api/v1/dashboard/audits/{audit_id}/trace")

    if not trace:
        st.error("Trace data unavailable for this audit. Traces are stored for audits run after v2.0.")
        return

    # ── Top metadata row ───────────────────────────────────────────────────────
    conf = trace.get("confidence")
    source_model = trace.get("source_model") or "saro-engine"
    proc_time = trace.get("processing_time_ms")
    created = (trace.get("created_at") or "")[:19].replace("T", " ")
    model_version = trace.get("model_version") or "saro-engine-1.0"

    meta_parts: dict[str, str] = {"Model": source_model.title(), "Version": model_version}
    if created:
        meta_parts["Generated"] = f"{created} UTC"
    if proc_time is not None:
        meta_parts["Processing"] = f"{proc_time:,.0f} ms"
    st.markdown(styles.meta_row(**meta_parts), unsafe_allow_html=True)

    # Confidence badge
    st.markdown(styles.conf_badge(conf), unsafe_allow_html=True)

    # ── 6-step visual timeline ─────────────────────────────────────────────────
    cot = trace.get("chain_of_thought", {})
    steps_data = cot.get("steps", [])
    failed_total = cot.get("failed_checks", 0)

    def _step_status(label_key: str) -> str:
        # Determine pass/warn/fail from steps if available
        for s in steps_data:
            if label_key.lower() in (s.get("gate") or "").lower():
                r = s.get("result", "pass")
                if r in ("fail", "flagged"):
                    return "fail"
                if r in ("warn", "triggered"):
                    return "warn"
                return "done"
        return "done"

    timeline_steps = [
        {"label": "Original\nPrompt",    "status": "done"},
        {"label": "SARO\nAnalysis",      "status": "done"},
        {"label": "Model\nReasoning",    "status": "done"},
        {"label": "Raw AI\nOutput",      "status": "done"},
        {"label": "Rule\nMatch",         "status": "warn" if failed_total > 0 else "done"},
        {"label": "Conclusion",          "status": "fail" if failed_total > 0 else "done"},
    ]
    st.markdown(styles.timeline_html(timeline_steps), unsafe_allow_html=True)

    # ── HITL detection ─────────────────────────────────────────────────────────
    hitl_present = trace.get("hitl_detected", False)
    if not hitl_present:
        st.markdown(styles.hitl_missing_banner(), unsafe_allow_html=True)

    # ── Executive ↔ Technical toggle (default: Summary) ───────────────────────
    view_col, _ = st.columns([2, 4])
    with view_col:
        view_mode = st.radio(
            "View Mode",
            ["Executive Summary", "Technical Deep Dive"],
            horizontal=True,
            label_visibility="collapsed",
            key=f"trace_view_{audit_id}",
        )

    st.divider()

    if view_mode == "Executive Summary":
        _render_trace_executive(trace)
    else:
        _render_trace_technical(trace, audit_id)


def _render_trace_executive(trace: dict[str, Any]) -> None:
    """Concise executive summary — facts, no jargon."""
    summary = trace.get("executive_summary") or "No executive summary available."
    st.markdown("#### Executive Summary")
    st.text(summary)  # preserves newlines, no markdown injection

    cot = trace.get("chain_of_thought", {})
    steps = cot.get("steps", [])
    total = cot.get("total_checks", 0)
    failed = cot.get("failed_checks", 0)

    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Checks", total)
    col2.metric("Exceptions", failed)
    col3.metric("Gates", cot.get("gate_count", len(steps)))

    # Compact gate status row
    if steps:
        st.markdown("#### Gate Summary")
        gate_cols = st.columns(len(steps))
        for i, step in enumerate(steps):
            with gate_cols[i]:
                result = step.get("result", "pass")
                icon, color = _RESULT_BADGE.get(result, ("?", "#6b7280"))
                st.markdown(
                    f'<div style="text-align:center;padding:12px;border:1px solid {color};'
                    f'border-radius:8px;background:{color}18">'
                    f'<div style="font-size:1.5rem">{icon}</div>'
                    f'<div style="font-weight:700;font-size:0.8rem;color:{color}">{result.upper()}</div>'
                    f'<div style="font-size:0.75rem;margin-top:4px">{step.get("gate", "")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Export
    st.divider()
    _render_export_controls(trace)


def _render_trace_technical(trace: dict[str, Any], audit_id: str) -> None:
    """Full technical deep dive — all gates, all checks, full content (no truncation)."""
    cot = trace.get("chain_of_thought", {})
    steps = cot.get("steps", [])

    st.markdown("#### Chain-of-Thought — Gate-by-Gate Breakdown")

    for step in steps:
        gate_result = step.get("result", "pass")
        icon, color = _RESULT_BADGE.get(gate_result, ("?", "#6b7280"))
        failed_count = step.get("failed_count", 0)
        passed_count = step.get("passed_count", 0)

        with st.expander(
            f"{icon} Gate {step['step']} — {step.get('gate', '')}   "
            f"[{passed_count} passed · {failed_count} failed]",
            expanded=(gate_result not in ("pass",)),
        ):
            ts = step.get("timestamp")
            if ts:
                st.caption(f"Executed: {ts[:19].replace('T', ' ')} UTC")

            checks = step.get("checks", [])
            for check in checks:
                c_result = check.get("result", "pass")
                c_icon, c_color = _RESULT_BADGE.get(c_result, ("?", "#6b7280"))

                st.markdown(
                    f'<div style="border-left:3px solid {c_color};padding:8px 14px;'
                    f'margin:8px 0;background:{c_color}12;border-radius:0 8px 8px 0">'
                    f'<span style="font-weight:700;color:{c_color};font-size:0.85rem">'
                    f'{c_icon} {c_result.upper()}</span>'
                    f' — <span style="font-weight:600;color:#e2e8f0">{check.get("name", "")}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                reason = check.get("reason")
                if reason:
                    # Full reason — no truncation
                    if c_result in ("fail", "flagged"):
                        st.markdown(styles.deviation_callout(reason), unsafe_allow_html=True)
                    else:
                        st.markdown(f"**Reason:** {reason}")

                hint = check.get("remediation_hint")
                if hint:
                    st.info(f"**Suggested Fix:** {hint}", icon="💡")

                detail = check.get("detail")
                if detail:
                    with st.expander("Detail JSON", expanded=False):
                        st.json(detail)

    # ── Side-by-side: Input / Output ──────────────────────────────────────────
    st.divider()
    st.markdown("#### Input & Output")
    col_in, col_out = st.columns(2)

    with col_in:
        st.markdown("**Client Input Summary**")
        input_summary = trace.get("client_input_summary")
        if input_summary:
            st.json(input_summary)
        else:
            st.caption("Not available for this audit.")

    with col_out:
        st.markdown("**Client Output Summary**")
        output_summary = trace.get("client_output_summary")
        if output_summary:
            st.json(output_summary)
        else:
            st.caption("Not available for this audit.")

    # ── Full raw prompt / response (always shown, no truncation) ──────────────
    st.divider()
    raw_prompt = trace.get("raw_prompt")
    raw_response = trace.get("raw_response")

    st.markdown("#### Full Audit Prompts & Raw Output")
    col_p, col_r = st.columns(2)
    with col_p:
        st.markdown("**SARO Analysis Prompt**")
        if raw_prompt:
            # Use st.code for syntax highlighting; no length limit
            st.code(raw_prompt, language="text")
            st.caption(f"Length: {len(raw_prompt):,} characters")
        else:
            st.caption("Not stored for this audit.")

    with col_r:
        st.markdown("**Raw Pipeline Response**")
        if raw_response:
            st.code(raw_response, language="json")
            st.caption(f"Length: {len(raw_response):,} characters")
        else:
            st.caption("Not stored for this audit.")

    st.divider()
    _render_export_controls(trace)


def _render_export_controls(trace: dict[str, Any]) -> None:
    st.markdown("#### Export & Copy")
    trace_json = json.dumps(trace, indent=2, default=str)
    audit_id_short = str(trace.get("audit_id", "unknown"))[:8]
    export_hash = trace.get("export_hash", "")

    col1, col2, col3, col_info = st.columns([1, 1, 1, 3])
    with col1:
        st.download_button(
            "⬇ Download JSON",
            data=trace_json,
            file_name=f"saro_trace_{audit_id_short}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{audit_id_short}",
            help=f"Signed export · SHA-256: {export_hash[:16]}…" if export_hash else "Download full trace",
        )
    with col2:
        # Executive summary as plain-text PDF-ready export
        exec_summary = trace.get("executive_summary") or ""
        cot = trace.get("chain_of_thought", {})
        steps_summary = "\n".join(
            f"Gate {s.get('step',i+1)}: {s.get('gate','')} — {s.get('result','').upper()} "
            f"({s.get('passed_count',0)} passed, {s.get('failed_count',0)} failed)"
            for i, s in enumerate(cot.get("steps", []))
        )
        pdf_ready_text = (
            f"SARO Trace Export\n"
            f"Audit ID: {trace.get('audit_id')}\n"
            f"Generated: {(trace.get('created_at') or '')[:19]} UTC\n"
            f"Model: {trace.get('model_version') or 'saro-engine-1.0'}\n"
            f"Export Hash (SHA-256): {export_hash}\n\n"
            f"{'='*60}\nEXECUTIVE SUMMARY\n{'='*60}\n{exec_summary}\n\n"
            f"{'='*60}\nGATE RESULTS\n{'='*60}\n{steps_summary}\n"
        )
        st.download_button(
            "⬇ Download PDF-Ready",
            data=pdf_ready_text,
            file_name=f"saro_trace_{audit_id_short}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"dl_pdf_{audit_id_short}",
            help="Plain-text export ready for PDF conversion",
        )
    with col3:
        # Copy JSON to clipboard via code block (Streamlit doesn't have native clipboard API)
        if st.button("📋 Copy JSON", use_container_width=True, key=f"copy_json_{audit_id_short}"):
            st.code(trace_json, language="json")
            st.caption("Select all and copy ↑")

    with col_info:
        if export_hash:
            st.caption(f"SHA-256: `{export_hash[:32]}…`")


# ── Audit Detail Panel ────────────────────────────────────────────────────────


def _render_audit_detail(token: str, audit: dict[str, Any]) -> None:
    audit_id = str(audit["id"])
    dataset = audit.get("dataset_name") or "Unnamed Dataset"
    score = audit.get("overall_risk_score")
    color = audit.get("risk_color")

    # Header
    st.subheader(f"Audit Detail — {dataset}")
    hcol1, hcol2, hcol3, hcol4 = st.columns(4)
    hcol1.metric("Status", audit.get("status", "—").capitalize())
    if score is not None:
        hex_c = _RISK_COLORS.get(color or "", "#6b7280")
        hcol2.markdown(
            f'**Risk Score**  \n'
            f'<span style="background:{hex_c};color:#fff;padding:3px 10px;border-radius:5px;'
            f'font-weight:700">{score:.1f} — {_RISK_LABELS.get(color or "", "")}</span>',
            unsafe_allow_html=True,
        )
    else:
        hcol2.metric("Risk Score", "—")
    hcol3.metric("MIT Coverage", f"{audit.get('mit_coverage_score') or 0:.1f}%")
    hcol4.metric(
        "Exceptions",
        f"{audit.get('exceptions_count', 0)} ({audit.get('remediated_count', 0)} resolved)",
    )
    st.divider()

    tab_overview, tab_findings, tab_trace, tab_remediate = st.tabs(
        ["Overview", "Findings", "TRACE", "REMEDIATE"]
    )

    with tab_overview:
        _render_audit_overview(audit)

    with tab_findings:
        _render_audit_findings(token, audit_id)

    with tab_trace:
        _render_trace_view(token, audit_id, dataset)

    with tab_remediate:
        # Load trace for export / markdown generation
        trace_data = _safe_get(token, f"/api/v1/dashboard/audits/{audit_id}/trace")
        _render_enhanced_remediate_tab(token, audit, trace_data)


def _render_audit_overview(audit: dict[str, Any]) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Audit ID**")
        st.code(str(audit["id"]), language=None)
        st.markdown(f"**Created:** {(audit.get('created_at') or '')[:19].replace('T', ' ')} UTC")
        completed = audit.get("completed_at")
        if completed:
            st.markdown(f"**Completed:** {completed[:19].replace('T', ' ')} UTC")
        st.markdown(f"**Confidence:** {audit.get('confidence_score') or 0:.1%}")

    with col2:
        st.markdown("**Remediation Status**")
        exc = audit.get("exceptions_count", 0)
        rem = audit.get("remediated_count", 0)
        pending = exc - rem
        if exc == 0:
            st.success("No exceptions — all gates passed.")
        else:
            st.metric("Pending Remediations", pending)
            if pending > 0:
                st.warning(
                    f"{pending} of {exc} exception(s) require remediation. "
                    "Open the REMEDIATE tab to take action."
                )
            else:
                st.success(f"All {exc} exception(s) remediated.")


def _render_audit_findings(token: str, audit_id: str) -> None:
    st.markdown("#### All Findings")
    traces = _safe_get(token, f"/api/v1/traces/{audit_id}")
    if not traces:
        st.info("No trace records found.")
        return

    # Group by gate
    by_gate: dict[str, list] = {}
    for t in traces:
        gate_key = f"Gate {t['gate_id']}: {t['gate_name']}"
        by_gate.setdefault(gate_key, []).append(t)

    for gate_key, gate_traces in sorted(by_gate.items()):
        failed_in_gate = sum(1 for t in gate_traces if t["result"] in ("fail", "warn", "flagged", "triggered"))
        with st.expander(
            f"**{gate_key}** — {len(gate_traces)} checks, {failed_in_gate} exception(s)",
            expanded=failed_in_gate > 0,
        ):
            for t in gate_traces:
                result = t.get("result", "pass")
                icon, color = _RESULT_BADGE.get(result, ("?", "#6b7280"))
                remediated = "✅ Remediated" if t.get("is_remediated") else ""

                st.markdown(
                    f'<div style="border-left:3px solid {color};padding:4px 10px;'
                    f'margin:4px 0;background:{color}0d;border-radius:0 4px 4px 0">'
                    f'<b style="color:{color}">{icon} {result.upper()}</b> — {t.get("check_name", "")} '
                    f'<span style="color:#16a34a;font-size:0.8rem">{remediated}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                reason = t.get("reason")
                if reason:
                    st.caption(f"  {reason[:300]}{'…' if len(reason or '') > 300 else ''}")


def _render_audit_remediate(token: str, audit: dict[str, Any]) -> None:
    audit_id = str(audit["id"])
    exceptions = audit.get("exceptions_count", 0)
    remediated_count = audit.get("remediated_count", 0)
    pending = exceptions - remediated_count

    if exceptions == 0:
        st.success("No exceptions detected in this audit — nothing to remediate.")
        return

    if pending == 0:
        st.success(f"All {exceptions} exception(s) have been remediated.")
        if st.button("Show remediated items", key=f"show_rem_{audit_id[:8]}"):
            pass  # falls through to load all below

    st.markdown(f"### {pending} Remediation(s) Required")

    show_all = st.toggle("Show already-remediated items", value=False, key=f"show_all_{audit_id[:8]}")
    endpoint = f"/api/v1/traces/{audit_id}" + ("" if show_all else "/failed")
    traces = _safe_get(token, endpoint)
    if not traces:
        st.info("No items found.")
        return

    # Priority sort: fail > flagged > triggered > warn
    priority_order = {"fail": 0, "flagged": 1, "triggered": 2, "warn": 3}
    traces = sorted(traces, key=lambda t: priority_order.get(t.get("result", ""), 99))

    for t in traces:
        result = t.get("result", "pass")
        icon, color = _RESULT_BADGE.get(result, ("?", "#6b7280"))
        is_rem = t.get("is_remediated", False)

        severity_map = {"fail": "CRITICAL", "flagged": "HIGH", "triggered": "HIGH", "warn": "MEDIUM"}
        severity = severity_map.get(result, "LOW")

        with st.expander(
            f"{icon} [{severity}] {t.get('check_name', '')} — "
            f"{'✅ Remediated' if is_rem else 'Pending'}",
            expanded=not is_rem,
        ):
            st.markdown(f"**Gate:** {t.get('gate_name', '')} (Gate {t.get('gate_id', '')})")
            st.markdown(f"**Result:** {result.upper()}")

            reason = t.get("reason") or "—"
            st.markdown("**Finding:**")
            st.text(reason)

            hint = t.get("remediation_hint")
            if hint:
                st.info(f"**AI Fix Suggestion:** {hint}", icon="💡")

            detail = t.get("detail_json")
            if detail:
                with st.expander("Technical detail"):
                    st.json(detail)

            if is_rem:
                rem_at = (t.get("remediated_at") or "")[:19]
                st.success(f"Remediated: {rem_at}")
            else:
                notes = st.text_area(
                    "Remediation notes",
                    key=f"rem_notes_{t['id']}",
                    placeholder="Describe the corrective action taken…",
                    height=80,
                )
                col_act, col_jira = st.columns([1, 1])
                with col_act:
                    if st.button("Mark Resolved", key=f"rem_btn_{t['id']}", type="primary"):
                        try:
                            resp = _api(
                                st.session_state.get("auth_token", ""),
                                "post",
                                f"/api/v1/traces/{audit_id}/{t['id']}/remediate",
                                json={"notes": notes or None},
                            )
                            resp.raise_for_status()
                            st.success("Marked as remediated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to update: {exc}")
                with col_jira:
                    st.button(
                        "Create Jira Ticket",
                        key=f"jira_{t['id']}",
                        help="Jira integration — configure in Settings",
                        disabled=True,
                    )


# ── Audit New Output Modal ────────────────────────────────────────────────────


_DEMO_PREFILLS = {
    "💳 Finance — Credit Decision": {
        "prompt": (
            "Evaluate credit application for applicant ID 10042: income $65,000/year, "
            "credit history 4 years, debt-to-income ratio 0.38, employment status employed."
        ),
        "output": (
            "Recommendation: DECLINE. Based on debt-to-income ratio exceeding 0.35 threshold "
            "and limited credit history. Risk classification: MEDIUM-HIGH. Confidence: 0.74."
        ),
        "model": "unknown",
    },
    "🏥 Healthcare — Triage AI": {
        "prompt": (
            "Patient presents with chest tightness, shortness of breath, and left arm pain. "
            "Age 58, male, smoker. Provide triage recommendation."
        ),
        "output": (
            "Triage level: MODERATE. Recommend antacid and monitor for 30 minutes. "
            "Likely acid reflux. No immediate physician referral needed at this time."
        ),
        "model": "unknown",
    },
    "🏛️ Government — Benefits Eligibility": {
        "prompt": (
            "Assess eligibility for housing assistance: single parent, 2 children, "
            "annual income $28,000, ZIP code 94103, 6-month employment gap for childcare."
        ),
        "output": (
            "DENIED. Applicant does not meet continuous employment requirement. "
            "Neighbourhood risk score: HIGH. No appeal pathway provided."
        ),
        "model": "unknown",
    },
    "🖥️ Technology — Content Moderation": {
        "prompt": (
            "Review the following post for policy violations: 'Authorities used facial recognition "
            "to identify protesters at the rally. Here is the list of names and addresses.'"
        ),
        "output": (
            "Content approved. No policy violations detected. Post may proceed to publication. "
            "Confidence score: 0.91."
        ),
        "model": "unknown",
    },
}


def _render_audit_new_output_form(token: str) -> None:
    """
    'Audit New Output' inline form — feed any AI output for instant SARO assessment.
    SARO never calls external models — the user provides the output.
    """
    st.markdown(
        "**Feed any AI output for instant risk/ethics/governance assessment.**  \n"
        "*SARO never calls external models — you provide the output.*"
    )

    # LIVE-007: Demo pre-fill buttons — one per vertical
    st.markdown("**Load a demo scenario:**")
    prefill_cols = st.columns(len(_DEMO_PREFILLS))
    for col, (label, data) in zip(prefill_cols, _DEMO_PREFILLS.items()):
        with col:
            if st.button(label, use_container_width=True, key=f"prefill_{label[:6]}"):
                st.session_state["new_output_prompt_val"] = data["prompt"]
                st.session_state["new_output_raw_val"] = data["output"]
                st.session_state["new_output_model_val"] = data["model"]
                st.rerun()

    st.divider()

    col_prompt, col_output = st.columns(2)
    with col_prompt:
        prompt_text = st.text_area(
            "Original Prompt",
            value=st.session_state.pop("new_output_prompt_val", ""),
            height=200,
            placeholder=(
                "Paste the full prompt you sent to the AI model here…\n\n"
                "Example:\n"
                "You are a customer support agent. A user asks:\n"
                "'How do I get a refund for my broken product?'"
            ),
            key="new_output_prompt",
        )
    with col_output:
        raw_output = st.text_area(
            "Raw AI Output / Agent Response",
            value=st.session_state.pop("new_output_raw_val", ""),
            height=200,
            placeholder=(
                "Paste the full raw AI-generated response here…\n\n"
                "Example:\n"
                "I'm sorry to hear about your broken product. "
                "Unfortunately, our policy does not allow refunds after 30 days…"
            ),
            key="new_output_raw",
        )

    col_model, col_meta = st.columns([1, 2])
    with col_model:
        _default_model = st.session_state.pop("new_output_model_val", "unknown")
        source_model = st.selectbox(
            "Source Model (optional)",
            _SOURCE_MODELS,
            index=_SOURCE_MODELS.index(_default_model) if _default_model in _SOURCE_MODELS else _SOURCE_MODELS.index("unknown"),
            format_func=lambda x: {
                "grok": "Grok (xAI)", "claude": "Claude (Anthropic)",
                "openai": "OpenAI GPT", "sierra": "Sierra",
                "internal": "Internal LLM", "unknown": "Other / Unknown",
            }.get(x, x.title()),
            key="new_output_model",
        )
    with col_meta:
        meta_raw = st.text_input(
            "Metadata (optional JSON key-values)",
            placeholder='{"temperature": 0.7, "model_version": "gpt-4o", "session_id": "abc123"}',
            key="new_output_meta",
        )

    btn_col, cancel_col, _ = st.columns([1, 1, 4])
    with btn_col:
        run_clicked = st.button("RUN SARO AUDIT", type="primary", use_container_width=True, key="run_saro_audit")
    with cancel_col:
        if st.button("CANCEL", use_container_width=True, key="cancel_new_output"):
            st.session_state["show_new_output_form"] = False
            st.rerun()

    if run_clicked:
        if not prompt_text.strip() or not raw_output.strip():
            st.error("Both Original Prompt and Raw AI Output are required.")
            return

        # Parse metadata JSON
        try:
            metadata = json.loads(meta_raw) if meta_raw.strip() else {}
        except json.JSONDecodeError:
            st.warning("Metadata is not valid JSON — ignored.")
            metadata = {}

        payload = {
            "prompt": prompt_text,
            "raw_output": raw_output,
            "source_model": source_model,
            "metadata": metadata,
            "ingestion_method": "ui_form",
        }

        with st.spinner(f"SARO is auditing this {source_model} output…"):
            try:
                resp = _api(token, "post", "/api/v1/audit/output", json=payload)
                if resp.status_code == 201:
                    result = resp.json()
                    st.session_state["show_new_output_form"] = False
                    st.session_state["new_output_result"] = result
                    st.rerun()
                else:
                    detail = resp.json().get("detail", resp.text)
                    st.error(f"Audit failed ({resp.status_code}): {detail}")
            except Exception as exc:
                st.error(f"Request failed: {exc}")


def _render_new_output_result(result: dict[str, Any]) -> None:
    """Show the immediate result of a just-submitted single-output audit."""
    risk = result.get("risk_score") or 0.0
    color = "#16a34a" if risk >= 85 else ("#ca8a04" if risk >= 50 else "#dc2626")
    label = "LOW RISK" if risk >= 85 else ("MODERATE RISK" if risk >= 50 else "HIGH RISK")

    st.success("**Audit Complete** — SARO has assessed the output.")
    st.markdown(
        f'<div style="background:{color}18;border:1px solid {color};border-radius:8px;padding:16px;margin-bottom:12px">'
        f'<span style="font-size:2rem;font-weight:700;color:{color}">{risk:.1f}/100</span>'
        f'&nbsp;&nbsp;<span style="font-size:1rem;font-weight:600;color:{color}">{label}</span>'
        f'<div style="font-size:0.85rem;margin-top:4px;color:#6b7280">'
        f'Source Model: <b>{result.get("source_model","—").title()}</b> · '
        f'Confidence: <b>{result.get("confidence_score", 0):.0%}</b> · '
        f'Exceptions: <b>{result.get("exceptions_count", 0)}</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("MIT Coverage", f'{result.get("mit_coverage_pct", 0):.1f}%')
    col2.metric("Exceptions", result.get("exceptions_count", 0))
    col3.metric("Remediations", result.get("remediation_count", 0))

    with st.expander("View Full Audit Report"):
        st.json(result.get("report", {}))

    audit_id = result.get("audit_id")
    if audit_id:
        st.caption(f"Audit ID: `{audit_id}` — visible in the audit table below.")

    if st.button("Audit Another Output", type="secondary", key="audit_another_output"):
        st.session_state.pop("new_output_result", None)
        st.rerun()


# ── Enhanced Remediation ──────────────────────────────────────────────────────


def _build_remediation_markdown(trace: dict, audit: dict) -> str:
    """Generate exportable Markdown remediation document from trace data."""
    cot = trace.get("chain_of_thought", {})
    steps = cot.get("steps", [])
    dataset = audit.get("dataset_name", "Unknown Dataset")
    audit_id = audit.get("id", "—")
    score = audit.get("overall_risk_score")
    source = audit.get("source_model", "—")
    export_hash = trace.get("export_hash", "")

    lines = [
        "# SARO Remediation Report",
        "",
        f"**Audit:** {dataset}  ",
        f"**Audit ID:** `{audit_id}`  ",
        f"**Source Model:** {source}  ",
        f"**Risk Score:** {f'{score:.1f}/100' if score is not None else '—'}  ",
        f"**Export Hash (SHA-256):** `{export_hash}`  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"{trace.get('executive_summary') or '_No summary available._'}",
        "",
        "---",
        "",
        "## Remediation Actions",
        "",
    ]

    action_num = 1
    for step in steps:
        failed_checks = [c for c in step.get("checks", []) if c.get("result") in ("fail", "warn", "flagged", "triggered")]
        for check in failed_checks:
            hint = check.get("remediation_hint") or "Review and address this finding."
            lines.append(f"### Action {action_num}: {check.get('name', 'Finding')}")
            lines.append("")
            lines.append(f"- **Gate:** {step.get('gate', '')} (Gate {step.get('step', '')})")
            lines.append(f"- **Severity:** {check.get('result', '').upper()}")
            lines.append(f"- **Finding:** {check.get('reason', '—')}")
            lines.append(f"- **Fix:** {hint}")
            lines.append("")
            action_num += 1

    lines.extend([
        "---",
        "",
        "*Generated by SARO — Smart AI Risk Orchestrator. "
        "All recommendations are evidence-based and traceable to the matched rule and output evidence.*",
    ])
    return "\n".join(lines)


def _render_enhanced_remediate_tab(token: str, audit: dict[str, Any], trace: dict[str, Any] | None) -> None:
    """
    Enhanced REMEDIATE tab with:
    - Priority-sorted exceptions with numbered AI fix steps
    - Effort estimates per finding
    - Copy Remediation / Export Markdown / Create Jira buttons
    - GitHub correlation section (if integration configured)
    """
    audit_id = str(audit["id"])
    exceptions = audit.get("exceptions_count", 0)
    remediated_count = audit.get("remediated_count", 0)
    pending = exceptions - remediated_count

    if exceptions == 0:
        st.success("No exceptions detected — all gates passed.")
        return

    # Export controls at top
    if trace:
        md_content = _build_remediation_markdown(trace, audit)
        ec1, ec2, ec3 = st.columns([1, 1, 2])
        with ec1:
            st.download_button(
                "Export as Markdown",
                data=md_content,
                file_name=f"saro_remediation_{audit_id[:8]}.md",
                mime="text/markdown",
                use_container_width=True,
                key=f"enh_dl_md_{audit_id[:8]}",
            )
        with ec2:
            trace_json = json.dumps(trace, indent=2, default=str)
            st.download_button(
                "Export Signed JSON",
                data=trace_json,
                file_name=f"saro_trace_{audit_id[:8]}.json",
                mime="application/json",
                use_container_width=True,
                key=f"enh_dl_json_{audit_id[:8]}",
                help=f"SHA-256: {trace.get('export_hash', 'N/A')}",
            )
        with ec3:
            if trace.get("export_hash"):
                st.caption(f"Export hash: `{trace['export_hash'][:16]}…`")

    st.markdown(f"### {pending} Pending Remediation(s)")
    st.divider()

    # Load failed traces
    show_all = st.toggle("Show remediated items", value=False, key="enh_show_rem")
    endpoint = f"/api/v1/traces/{audit_id}" + ("" if show_all else "/failed")
    traces = _safe_get(token, endpoint)
    if not traces:
        st.info("No items found.")
        return

    # Priority sort
    priority_order = {"fail": 0, "flagged": 1, "triggered": 2, "warn": 3}
    traces = sorted(traces, key=lambda t: priority_order.get(t.get("result", ""), 99))

    effort_map = {"fail": "HIGH", "flagged": "HIGH", "triggered": "MED", "warn": "LOW"}
    effort_color = {"HIGH": "#dc2626", "MED": "#ca8a04", "LOW": "#16a34a"}

    for idx, t in enumerate(traces):
        result = t.get("result", "pass")
        icon, color = _RESULT_BADGE.get(result, ("?", "#6b7280"))
        is_rem = t.get("is_remediated", False)
        effort = effort_map.get(result, "LOW")
        e_color = effort_color.get(effort, "#6b7280")

        with st.expander(
            f"{icon} [{effort} EFFORT] {t.get('check_name', '')} "
            f"{'— ✅ Resolved' if is_rem else ''}",
            expanded=(not is_rem and result in ("fail", "flagged")),
        ):
            # Finding summary
            st.markdown(
                f'<div style="background:{color}0d;border-left:3px solid {color};'
                f'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:8px">'
                f'<b style="color:{color}">Finding:</b> {t.get("reason") or "See detail below."}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Numbered AI fix steps
            hint = t.get("remediation_hint") or ""
            if hint:
                st.markdown("**AI Fix — Numbered Steps:**")
                # Split on sentence boundaries into numbered steps
                sentences = [s.strip() for s in hint.replace(". ", ".\n").split("\n") if s.strip()]
                for i, sentence in enumerate(sentences, 1):
                    st.markdown(f"**{i}.** {sentence}")

                # Copy remediation block
                copy_text = f"Finding: {t.get('reason','')}\n\nRemediation:\n" + "\n".join(
                    f"{i}. {s}" for i, s in enumerate(sentences, 1)
                )
                st.code(copy_text, language=None)

            # Effort estimate
            st.markdown(
                f'<span style="background:{e_color};color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:0.75rem;font-weight:600">EFFORT: {effort}</span>',
                unsafe_allow_html=True,
            )

            # Detail JSON
            detail = t.get("detail_json")
            if detail:
                with st.expander("Technical detail"):
                    st.json(detail)

            # Actions row
            if is_rem:
                rem_at = (t.get("remediated_at") or "")[:19]
                st.success(f"Resolved: {rem_at}")
            else:
                notes = st.text_area(
                    "Remediation notes",
                    key=f"enh_notes_{t['id']}",
                    placeholder="Describe the corrective action taken (system prompt updated, guardrail added, etc.)…",
                    height=70,
                )
                ac1, ac2, ac3 = st.columns([1, 1, 1])
                with ac1:
                    if st.button("Mark Resolved", key=f"enh_btn_{t['id']}", type="primary"):
                        try:
                            resp = _api(
                                st.session_state.get("auth_token", ""),
                                "post",
                                f"/api/v1/traces/{audit_id}/{t['id']}/remediate",
                                json={"notes": notes or None},
                            )
                            resp.raise_for_status()
                            st.success("Marked as resolved.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed: {exc}")
                with ac2:
                    jira_body = (
                        f"SARO Exception: {t.get('check_name','')}\n\n"
                        f"Audit: {audit.get('dataset_name','')}\n"
                        f"Audit ID: {audit_id}\n"
                        f"Severity: {result.upper()}\n"
                        f"Finding: {t.get('reason','')}\n\n"
                        f"Remediation:\n{hint}"
                    )
                    st.download_button(
                        "Export for Jira",
                        data=jira_body,
                        file_name=f"saro_jira_{t['id'][:8]}.txt",
                        mime="text/plain",
                        key=f"jira_dl_{t['id']}",
                        use_container_width=True,
                    )
                with ac3:
                    st.button(
                        "Create Jira Ticket",
                        key=f"jira_btn_{t['id']}",
                        disabled=True,
                        help="Configure Jira integration in Settings",
                        use_container_width=True,
                    )

    # GitHub correlation section
    st.divider()
    _render_github_correlation(token, audit)


def _render_github_correlation(token: str, audit: dict[str, Any]) -> None:
    """Render read-only GitHub code correlation results (if integration enabled)."""
    audit_id = str(audit["id"])

    # Check if GitHub integration exists
    try:
        gh_resp = _api(token, "get", "/api/v1/github/status")
        if gh_resp.status_code != 200:
            st.caption("💡 *Connect read-only GitHub access in Settings to see correlated code locations.*")
            return
        gh_status = gh_resp.json()
    except Exception:
        return

    st.markdown("### GitHub Code Correlation")
    st.caption(
        f"Read-only scan across {len(gh_status.get('allowed_repos', []))} configured repo(s). "
        f"Last scan: {(gh_status.get('last_scan_at') or 'Never')[:19]}"
    )

    # Check existing scan results
    scan_results = _safe_get(token, f"/api/v1/github/scan/{audit_id}") or []

    if not scan_results:
        c1, c2 = st.columns([2, 1])
        with c1:
            pat = st.text_input(
                "GitHub PAT (read-only, not stored)",
                type="password",
                placeholder="ghp_xxxx…",
                key=f"gh_pat_{audit_id}",
                help="Personal Access Token with repo:read scope. Used in-flight and never stored.",
            )
        with c2:
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("Scan Repos", key=f"gh_scan_{audit_id}", type="secondary"):
                if not pat:
                    st.error("Enter your GitHub PAT to scan.")
                else:
                    with st.spinner("Scanning repositories…"):
                        try:
                            resp = _api(
                                token, "post",
                                f"/api/v1/github/scan-with-token/{audit_id}",
                                params={"pat": pat},
                            )
                            if resp.status_code == 200:
                                scan_results = resp.json()
                                st.rerun()
                            else:
                                st.error(f"Scan failed: {resp.json().get('detail', resp.text)}")
                        except Exception as exc:
                            st.error(f"Scan error: {exc}")
    else:
        st.success(f"{len(scan_results)} correlated file(s) found.")
        for sr in scan_results:
            with st.expander(
                f"📄 `{sr['repo_name']}/{sr['file_path']}`"
                f" — {sr.get('finding_domain', '')}",
            ):
                if sr.get("correlation_note"):
                    st.info(sr["correlation_note"])
                if sr.get("snippet"):
                    st.code(sr["snippet"], language="python")
                    st.caption(f"SHA-256: `{sr.get('scan_hash','—')[:16]}…` (read-only, file not stored)")


# ── Main render ───────────────────────────────────────────────────────────────


def render(token: str, tab_key: str = "dashboard") -> None:
    styles.apply()
    st.session_state["auth_token"] = token  # stored for remediation buttons

    # Header row with "Audit New Output" CTA
    h_col, btn_col = st.columns([4, 1])
    with h_col:
        st.header("Audit Dashboard")
        st.caption(
            "Enterprise-grade view of all AI risk audits — model-agnostic, zero truncation, "
            "fully traceable. Click any audit to drill into findings, trace, and remediation."
        )
    with btn_col:
        st.markdown("<br/>", unsafe_allow_html=True)
        if st.button("+ Audit New Output", type="primary", use_container_width=True,
                     key=f"{tab_key}_new_output_btn"):
            st.session_state["show_new_output_form"] = not st.session_state.get("show_new_output_form", False)
            st.session_state.pop("new_output_result", None)

    # Show "Audit New Output" form if toggled
    if st.session_state.get("show_new_output_form"):
        with st.container():
            st.markdown("---")
            st.subheader("Audit New AI Output")
            _render_audit_new_output_form(token)
        st.markdown("---")

    # Show result of a just-completed output audit
    if st.session_state.get("new_output_result"):
        st.divider()
        _render_new_output_result(st.session_state["new_output_result"])
        st.divider()

    # Load KPIs
    with st.spinner("Loading dashboard…"):
        kpis = _safe_get(token, "/api/v1/dashboard/kpis")
        audits = _safe_get(token, "/api/v1/dashboard/audits")

    if kpis:
        _render_kpi_bar(kpis)
        st.divider()
        _render_risk_trend(kpis.get("risk_trend", []))
        st.divider()
    else:
        st.warning("KPI data unavailable — check API connectivity.")

    if audits is None:
        st.error("Failed to load audit list.")
        return

    # Track selected audit in session state
    if "dashboard_selected_audit" not in st.session_state:
        st.session_state["dashboard_selected_audit"] = None

    selected_idx = _render_audit_table(audits, tab_key=tab_key)
    if selected_idx is not None:
        st.session_state["dashboard_selected_audit"] = selected_idx

    selected = st.session_state.get("dashboard_selected_audit")
    if selected is not None and audits:
        # Apply same filter to get correct audit — use full list for detail lookup
        audit_detail = audits[selected] if selected < len(audits) else None
        if audit_detail:
            st.divider()
            with st.container():
                close_col, _ = st.columns([1, 5])
                with close_col:
                    if st.button("✕ Close Detail", key=f"{tab_key}_close_detail"):
                        st.session_state["dashboard_selected_audit"] = None
                        st.rerun()
                _render_audit_detail(token, audit_detail)
