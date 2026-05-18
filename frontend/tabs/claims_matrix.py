"""
Compliance Claims Matrix Tab — sortable, filterable matrix with CSV export.

Reads row data from GET /api/v1/compliance-matrix and renders per-framework
detail cards.  Sort state is stored in session_state so it survives reruns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import requests
import streamlit as st

_DOCS_ROOT = Path(__file__).parent.parent.parent / "docs"

_FRAMEWORKS: list[dict[str, Any]] = [
    {
        "id": "nist_rmf",
        "label": "NIST AI Risk Management Framework (RMF 1.0)",
        "rag": "GREEN",
        "supports": [
            "Automated risk scoring against NIST RMF categories (Govern, Map, Measure, Manage)",
            "Rule-based flagging of AI outputs against RMF principles",
            "Evidence export with NIST RMF citations",
            "90-day trend tracking of AI risk scores",
            "TRACE explanations of which RMF controls were evaluated",
        ],
        "not_replace": [
            "Formal NIST AI RMF organisational programme implementation",
            "Human judgement in RMF governance decisions",
            "Attestation or certification by a NIST-recognised body",
            "Ongoing human oversight of AI systems",
            "Legal counsel review of compliance posture",
        ],
        "disclaimer": None,
    },
    {
        "id": "eu_ai_act",
        "label": "EU AI Act (2024/1689)",
        "rag": "AMBER",
        "supports": [
            "Automated flagging of AI outputs against EU AI Act high-risk categories",
            "Risk classification assistance (Annex III risk categories)",
            "Evidence documentation for internal compliance reviews",
            "Audit trail for AI system outputs used in regulated contexts",
            "TRACE explanations for non-technical reviewers",
        ],
        "not_replace": [
            "Conformity assessments as defined in Article 43",
            "Certification or CE marking",
            "Registration in the EU AI Act database (Article 49)",
            "Notified body assessment for high-risk AI systems",
            "Legal determination of whether a system is 'high-risk' under Article 6",
        ],
        "disclaimer": (
            "⚠️ **EXPLICIT DISCLAIMER:** SARO does not perform conformity assessments as "
            "defined in the EU AI Act. SARO does not issue CE markings, declarations of "
            "conformity, or any certification recognised under the EU AI Act."
        ),
    },
    {
        "id": "aigp",
        "label": "AI Governance Professional (AIGP) Framework",
        "rag": "GREEN",
        "supports": [
            "Continuous AI output monitoring aligned with AIGP principles",
            "Risk scoring against fairness, transparency, and accountability criteria",
            "Evidence packs supporting AIGP audit documentation",
            "Compliance gap identification against AIGP best practices",
        ],
        "not_replace": [
            "Human governance committee decisions",
            "AIGP professional qualification or certification",
            "Ethical review board judgements",
            "Organisational AI governance policy development",
        ],
        "disclaimer": None,
    },
    {
        "id": "iso_42001",
        "label": "ISO/IEC 42001:2023 (AI Management System)",
        "rag": "GREEN",
        "supports": [
            "Audit trail documentation aligned with ISO 42001 Clause 9 (performance evaluation)",
            "Risk assessment evidence for ISO 42001 Clause 6 (planning)",
            "Continuous monitoring supporting ISO 42001 Clause 10 (improvement)",
        ],
        "not_replace": [
            "ISO 42001 certification audit by an accredited certification body",
            "Implementation of a full AI management system",
            "Internal audit function for ISO 42001",
        ],
        "disclaimer": None,
    },
]

_RAG_STYLE = {
    "GREEN": "background:#16a34a;color:#fff",
    "AMBER": "background:#ca8a04;color:#fff",
    "RED":   "background:#dc2626;color:#fff",
}

_RISK_COLORS = {
    "Critical": "🔴",
    "High":     "🟠",
    "Medium":   "🟡",
    "Low":      "🟢",
    "N/A":      "⚪",
}

_SORT_COLUMNS = {
    "None (default)": None,
    "Risk Level": "risk_level",
    "Regulation Name": "regulation_name",
    "Last Updated": "last_updated",
}


def _rag_badge(rag: str) -> str:
    style = _RAG_STYLE.get(rag, "background:#6b7280;color:#fff")
    return f'<span style="{style};padding:2px 10px;border-radius:10px;font-size:0.8rem;font-weight:700">{rag}</span>'


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return getattr(requests, method)(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def _fetch_matrix_rows(
    token: str,
    sort_by: str | None,
    sort_dir: str,
    filter_regulation: str | None,
    filter_risk_level: str | None,
) -> list[dict[str, Any]]:
    params: dict[str, str] = {"sort_dir": sort_dir}
    if sort_by:
        params["sort_by"] = sort_by
    if filter_regulation:
        params["filter_regulation"] = filter_regulation
    if filter_risk_level:
        params["filter_risk_level"] = filter_risk_level
    try:
        resp = _api(token, "get", "/api/v1/compliance-matrix", params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as exc:
        st.error(f"Could not load matrix data from API: {exc}")
        return []


def _fetch_csv_export(
    token: str,
    sort_by: str | None,
    sort_dir: str,
    filter_regulation: str | None,
    filter_risk_level: str | None,
) -> bytes | None:
    params: dict[str, str] = {"sort_dir": sort_dir}
    if sort_by:
        params["sort_by"] = sort_by
    if filter_regulation:
        params["filter_regulation"] = filter_regulation
    if filter_risk_level:
        params["filter_risk_level"] = filter_risk_level
    try:
        resp = _api(token, "get", "/api/v1/compliance-matrix/export", params=params)
        if resp.status_code == 413:
            st.error("Export too large — apply filters to reduce the dataset.")
            return None
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        st.error(f"Export failed: {exc}")
        return None


def _render_matrix_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("No rows match the current filter.")
        return

    headers = ["Regulation", "Article", "Risk", "Status", "Coverage", "Updated"]
    col_widths = [3, 2, 1, 2, 1, 2]
    cols = st.columns(col_widths)
    for col, h in zip(cols, headers):
        col.markdown(f"**{h}**")

    st.divider()
    for row in rows:
        risk = row.get("risk_level") or "N/A"
        icon = _RISK_COLORS.get(risk, "⚪")
        cov = row.get("coverage_pct")
        cov_str = f"{cov}%" if cov is not None else "—"
        updated = row.get("last_updated") or "—"
        cols = st.columns(col_widths)
        cols[0].write(row.get("regulation_name", ""))
        cols[1].write(row.get("article_section", ""))
        cols[2].write(f"{icon} {risk}")
        cols[3].write(row.get("status", ""))
        cols[4].write(cov_str)
        cols[5].write(updated)


def render(token: str) -> None:
    st.header("📋 Compliance Claims Matrix")
    st.caption(
        "**Version 1.0 | May 2026 | Status: Requires SME Review Before External Use**  \n"
        "This matrix clarifies what SARO claims to support versus what it does not replace."
    )

    st.warning(
        "**Important Disclaimer:** SARO is an AI risk assessment and audit tool — not a "
        "certification body, legal advisor, or regulatory authority.",
        icon="⚠️",
    )

    st.divider()

    # ── Sort & filter controls ────────────────────────────────────────────────
    st.subheader("Matrix View")
    ctrl_cols = st.columns([2, 1, 2, 1])

    with ctrl_cols[0]:
        sort_label = st.selectbox(
            "Sort by",
            options=list(_SORT_COLUMNS.keys()),
            key="matrix_sort_col",
        )
        sort_by = _SORT_COLUMNS[sort_label]

    with ctrl_cols[1]:
        sort_dir = st.radio(
            "Direction",
            options=["asc", "desc"],
            key="matrix_sort_dir",
            horizontal=True,
        )

    with ctrl_cols[2]:
        filter_regulation = st.selectbox(
            "Filter regulation",
            options=["All", "EU AI Act", "NIST AI RMF", "AIGP Framework", "ISO 42001"],
            key="matrix_filter_reg",
        )
        filter_regulation = None if filter_regulation == "All" else filter_regulation

    with ctrl_cols[3]:
        filter_risk = st.selectbox(
            "Filter risk level",
            options=["All", "Critical", "High", "Medium", "Low", "N/A"],
            key="matrix_filter_risk",
        )
        filter_risk_level = None if filter_risk == "All" else filter_risk

    # Fetch rows from API
    rows = _fetch_matrix_rows(token, sort_by, sort_dir, filter_regulation, filter_risk_level)

    # ── Export CSV button ─────────────────────────────────────────────────────
    export_col, _ = st.columns([1, 3])
    with export_col:
        if rows:
            csv_bytes = _fetch_csv_export(
                token, sort_by, sort_dir, filter_regulation, filter_risk_level
            )
            if csv_bytes:
                from datetime import date
                filename = f"saro-compliance-matrix-{date.today().isoformat()}.csv"
                st.download_button(
                    label="⬇️ Export CSV",
                    data=csv_bytes,
                    file_name=filename,
                    mime="text/csv",
                    key="matrix_export_csv",
                )
        else:
            st.button("⬇️ Export CSV", disabled=True, key="matrix_export_csv_disabled")

    st.caption(f"{len(rows)} row(s) shown")

    # ── Render table ──────────────────────────────────────────────────────────
    _render_matrix_table(rows)

    st.divider()

    # ── Framework coverage summary ────────────────────────────────────────────
    st.subheader("Framework Coverage Summary")
    fw_cols = st.columns(len(_FRAMEWORKS))
    for col, fw in zip(fw_cols, _FRAMEWORKS):
        with col:
            st.markdown(
                f'<div style="border:1px solid #334155;border-radius:8px;padding:12px;text-align:center">'
                f'<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:6px">'
                f'{fw["label"].split("(")[0].strip()}</div>'
                f'{_rag_badge(fw["rag"])}'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Detailed per-framework cards ──────────────────────────────────────────
    for fw in _FRAMEWORKS:
        with st.expander(f"**{fw['label']}** — {fw['rag']}", expanded=False):
            if fw["disclaimer"]:
                st.markdown(fw["disclaimer"])
                st.divider()
            col_s, col_n = st.columns(2)
            with col_s:
                st.markdown("#### ✅ SARO Supports")
                for item in fw["supports"]:
                    st.markdown(f"- {item}")
            with col_n:
                st.markdown("#### ❌ SARO Does NOT Replace")
                for item in fw["not_replace"]:
                    st.markdown(f"- {item}")

    st.divider()

    # Raw markdown download
    md_path = _DOCS_ROOT / "compliance-claims.md"
    if md_path.exists():
        st.download_button(
            "⬇️ Download Full Claims Matrix (Markdown)",
            data=md_path.read_bytes(),
            file_name="saro-compliance-claims-matrix.md",
            mime="text/markdown",
        )
