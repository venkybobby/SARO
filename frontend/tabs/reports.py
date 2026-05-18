"""
Reports Tab — SARO Streamlit frontend.

Displays for a selected audit:
  - MIT Risk Coverage Score (gauge + domain breakdown)
  - Similar Incidents with similarity scores
  - Fixed vs Not Fixed deltas (bar chart)
  - Applied compliance rules (table)
  - Bayesian risk scores (radar / bar chart)
  - Remediations (prioritised list)
  - Gate-by-gate drill-down
"""
from __future__ import annotations

import logging
import os

import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

logger = logging.getLogger(__name__)

_API_BASE = os.environ.get("SARO_API_URL", "http://localhost:8000")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _get(path: str, token: str) -> dict | list:
    resp = requests.get(f"{_API_BASE}{path}", headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def render(token: str) -> None:
    """Render the Reports tab."""
    st.header("Audit Reports")

    # ── Audit selector ────────────────────────────────────────────────────────
    try:
        audits: list[dict] = _get("/api/v1/audits?limit=100", token)  # type: ignore[assignment]
    except requests.ConnectionError:
        st.error(f"Cannot connect to SARO API at `{_API_BASE}`.")
        return
    except requests.HTTPError as e:
        st.error(f"Failed to load audits: {e}")
        return

    completed = [a for a in audits if a["status"] == "completed"]

    if not completed:
        st.info("No completed audits yet. Upload a batch in the **Upload** tab to get started.")
        return

    # ── Summary dashboard ─────────────────────────────────────────────────────
    try:
        summary = _get("/api/v1/reports/summary", token)
        _render_summary(summary)
    except Exception:
        pass  # Summary is non-critical; skip if unavailable

    st.divider()

    # Build selector options
    audit_options: dict[str, dict] = {
        f"{a['dataset_name'] or 'unnamed'} — {a['created_at'][:19]} "
        f"({a['sample_count']} samples)": a
        for a in completed
    }
    selected_label = st.selectbox("Select audit to inspect", list(audit_options.keys()))
    if not selected_label:
        return

    selected_audit = audit_options[selected_label]
    audit_id = selected_audit["id"]

    # Load full report
    try:
        report: dict = _get(f"/api/v1/reports/{audit_id}", token)  # type: ignore[assignment]
    except requests.HTTPError as e:
        st.error(f"Failed to load report: {e}")
        return

    _render_report(report)


def _render_summary(summary: dict) -> None:
    st.subheader("Tenant Summary")
    cols = st.columns(5)
    cols[0].metric("Total Audits", summary.get("total_audits", "—"))
    cols[1].metric("Completed", summary.get("completed", "—"))
    cols[2].metric(
        "Avg MIT Coverage",
        f"{summary['avg_mit_coverage']:.1%}" if summary.get("avg_mit_coverage") is not None else "—",
    )
    cols[3].metric(
        "Avg Risk Score",
        f"{summary['avg_risk_score']:.1%}" if summary.get("avg_risk_score") is not None else "—",
    )
    cols[4].metric(
        "Avg Fixed Delta",
        (
            f"{summary['avg_fixed_delta']:+.2f}"
            if summary.get("avg_fixed_delta") is not None
            else "—"
        ),
    )

    top_domains = summary.get("top_triggered_domains", {})
    if top_domains:
        with st.expander("Top triggered risk domains across all audits"):
            st.bar_chart(top_domains)


def _render_report(report: dict) -> None:
    st.subheader(
        f"Report — Audit `{report['audit_id'][:8]}…`  "
        f"| {report['sample_count']} samples  "
        f"| `{report['status']}`"
    )

    # ── Top metrics ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MIT Coverage Score", f"{report['mit_coverage']['score']:.1%}")
    c2.metric(
        "Fixed Delta",
        f"{report['fixed_delta']['delta']:+.2f}",
        help="Positive = more historical incidents were fixed; "
        "negative = more remain unresolved.",
    )
    c3.metric("Overall Risk", f"{report['bayesian_scores']['overall']:.1%}")
    c4.metric("Confidence", f"{report['confidence_score']:.1%}")

    tabs = st.tabs(
        [
            "MIT Coverage",
            "Similar Incidents",
            "Fixed vs Not Fixed",
            "Applied Rules",
            "Bayesian Scores",
            "Remediations",
            "Gate Details",
        ]
    )

    with tabs[0]:
        _render_mit_coverage(report["mit_coverage"])

    with tabs[1]:
        _render_similar_incidents(report["similar_incidents"])

    with tabs[2]:
        _render_fixed_delta(report["fixed_delta"], report["similar_incidents"])

    with tabs[3]:
        _render_applied_rules(report["applied_rules"])

    with tabs[4]:
        _render_bayesian_scores(report["bayesian_scores"])

    with tabs[5]:
        _render_remediations(report["remediations"])

    with tabs[6]:
        _render_gate_details(report["gates"])


# ── Section renderers ─────────────────────────────────────────────────────────


def _render_mit_coverage(mit: dict) -> None:
    st.subheader("MIT Risk Coverage Score")
    score = mit["score"]

    # Gauge
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=score * 100,
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#2ca02c" if score >= 0.7 else "#ff7f0e" if score >= 0.4 else "#d62728"},
                "steps": [
                    {"range": [0, 40], "color": "#fee0d2"},
                    {"range": [40, 70], "color": "#fdae6b"},
                    {"range": [70, 100], "color": "#a1d99b"},
                ],
                "threshold": {"line": {"color": "black", "width": 2}, "value": 70},
            },
            title={"text": "MIT Risk Domain Coverage"},
        )
    )
    fig.update_layout(height=280, margin={"t": 30, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Covered domains**")
        for d in mit["covered_domains"]:
            st.success(f"✔ {d}  —  {mit['domain_risk_counts'].get(d, 0)} flags")
    with col2:
        st.markdown("**Uncovered domains**")
        for d in mit["uncovered_domains"]:
            st.info(f"○ {d}  (no signals detected)")

    st.metric("Total risks flagged", mit["total_risks_flagged"])


def _render_similar_incidents(incidents: list[dict]) -> None:
    st.subheader("Similar Historical Incidents")

    if not incidents:
        st.info("No similar incidents found in the database.")
        return

    for inc in incidents:
        sim = inc["similarity_score"]
        fixed_label = "✅ Resolved" if inc["is_fixed"] else "⚠️ Unresolved"
        colour = "green" if inc["is_fixed"] else "orange"
        with st.expander(
            f"**{inc['title']}** — similarity {sim:.1%} — :{colour}[{fixed_label}]",
            expanded=False,
        ):
            cols = st.columns(3)
            cols[0].write(f"**Category:** {inc.get('category') or '—'}")
            cols[1].write(f"**Harm type:** {inc.get('harm_type') or '—'}")
            cols[2].write(f"**Sector:** {inc.get('affected_sector') or '—'}")
            if inc.get("date"):
                st.caption(f"Date: {inc['date']}")
            if inc.get("url"):
                st.markdown(f"[Source]({inc['url']})")

    # Similarity bar chart
    fig = px.bar(
        x=[i["title"][:50] + "…" if len(i["title"]) > 50 else i["title"] for i in incidents],
        y=[i["similarity_score"] for i in incidents],
        color=["Resolved" if i["is_fixed"] else "Unresolved" for i in incidents],
        color_discrete_map={"Resolved": "#2ca02c", "Unresolved": "#d62728"},
        labels={"x": "Incident", "y": "Cosine Similarity"},
        title="Incident Similarity Scores",
    )
    fig.update_layout(height=300, margin={"t": 40, "b": 10}, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)


def _render_fixed_delta(delta_data: dict, incidents: list[dict]) -> None:
    st.subheader("Fixed vs Not Fixed")

    d = delta_data
    col1, col2, col3 = st.columns(3)
    col1.metric("Fixed incidents", d["fixed_count"])
    col2.metric("Unresolved incidents", d["unfixed_count"])
    col3.metric(
        "Delta (fixed – unfixed) / total",
        f"{d['delta']:+.3f}",
        delta=f"{d['delta']:+.3f}",
        delta_color="normal",
    )

    st.caption(f"Confidence: {d['confidence']:.1%}  |  Total similar incidents: {d['total_similar']}")

    # Delta interpretation
    if d["delta"] > 0:
        st.success(
            f"Delta **{d['delta']:+.3f}** — historically similar incidents are more often resolved. "
            "The risk pattern has known remediation pathways."
        )
    elif d["delta"] < 0:
        st.warning(
            f"Delta **{d['delta']:+.3f}** — historically similar incidents are mostly unresolved. "
            "This is an ongoing risk pattern with limited precedent for remediation."
        )
    else:
        st.info("Delta = 0.000 — equal numbers of fixed and unresolved similar incidents.")

    # Donut chart
    if d["total_similar"] > 0:
        fig = go.Figure(
            go.Pie(
                labels=["Fixed", "Unresolved"],
                values=[d["fixed_count"], d["unfixed_count"]],
                hole=0.5,
                marker_colors=["#2ca02c", "#d62728"],
            )
        )
        fig.update_layout(
            title="Similar Incident Remediation Status",
            height=280,
            margin={"t": 40, "b": 10},
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_applied_rules(rules: list[dict]) -> None:
    st.subheader("Applied Compliance Rules")

    if not rules:
        st.info("No compliance rules were triggered for this batch.")
        return

    # Group by framework
    by_framework: dict[str, list[dict]] = {}
    for rule in rules:
        by_framework.setdefault(rule["framework"], []).append(rule)

    for framework, fw_rules in sorted(by_framework.items()):
        st.markdown(f"#### {framework}")
        for rule in fw_rules:
            with st.expander(f"`{rule['rule_id']}` — {rule['title']}"):
                st.write(f"**Triggered by:** {rule['triggered_by']}")
                if rule.get("obligations"):
                    st.write("**Obligations:**")
                    st.write(rule["obligations"])

    # Summary table
    st.dataframe(
        [
            {
                "Framework": r["framework"],
                "Rule ID": r["rule_id"],
                "Title": r["title"],
                "Triggered By": r["triggered_by"],
            }
            for r in rules
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_bayesian_scores(bayesian: dict) -> None:
    st.subheader("Bayesian Risk Scores (MIT Domains)")
    st.metric("Overall Risk Probability", f"{bayesian['overall']:.1%}")

    domains = bayesian["by_domain"]

    # Bar chart with error bars
    fig = go.Figure(
        go.Bar(
            x=[d["domain"] for d in domains],
            y=[d["risk_probability"] for d in domains],
            error_y={
                "type": "data",
                "symmetric": False,
                "array": [max(0, d["ci_upper"] - d["risk_probability"]) for d in domains],
                "arrayminus": [max(0, d["risk_probability"] - d["ci_lower"]) for d in domains],
            },
            marker_color=[
                "#d62728" if d["risk_probability"] > 0.4 else
                "#ff7f0e" if d["risk_probability"] > 0.2 else
                "#2ca02c"
                for d in domains
            ],
            text=[f"{d['risk_probability']:.1%}" for d in domains],
            textposition="outside",
        )
    )
    fig.update_layout(
        xaxis_title="MIT Risk Domain",
        yaxis_title="Posterior Risk Probability",
        yaxis_range=[0, 1],
        height=380,
        margin={"t": 10, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Detail table
    st.dataframe(
        [
            {
                "Domain": d["domain"],
                "Risk Prob": f"{d['risk_probability']:.3f}",
                "95% CI Lower": f"{d['ci_lower']:.3f}",
                "95% CI Upper": f"{d['ci_upper']:.3f}",
                "Flagged": d["flagged_count"],
                "Samples": d["sample_count"],
            }
            for d in domains
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_remediations(remediations: list[dict]) -> None:
    st.subheader("Remediation Suggestions")

    if not remediations:
        st.success("No remediation actions required — no risk domains triggered.")
        return

    priority_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    for r in remediations:
        icon = priority_icons.get(r["priority"], "•")
        with st.expander(
            f"{icon} **{r['domain']}** — priority: `{r['priority']}`",
            expanded=r["priority"] in ("critical", "high"),
        ):
            st.write(r["suggestion"])
            st.write("**Related controls:**")
            for ctrl in r["related_controls"]:
                st.markdown(f"- `{ctrl}`")


def _render_gate_details(gates: list[dict]) -> None:
    st.subheader("Gate-by-Gate Results")

    gate_icons = {"pass": "✅", "warn": "⚠️", "fail": "❌"}

    for g in gates:
        icon = gate_icons.get(g["status"], "•")
        colour = {"pass": "green", "warn": "orange", "fail": "red"}.get(g["status"], "grey")

        with st.expander(
            f"{icon} Gate {g['gate_id']}: **{g['name']}** — "
            f":{colour}[{g['status'].upper()}] — score {g['score']:.3f}",
            expanded=g["status"] in ("fail", "warn"),
        ):
            st.json(g["details"])
