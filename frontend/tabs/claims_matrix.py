"""
Compliance Claims Matrix Tab — sortable, filterable matrix with CSV export
and live EVF Validation Status (FR-EVF-11, FR-EVF-16).

The top section shows the live Tier 1/2/3 validation label per framework,
fetched from GET /api/v1/evf/validation-status.  The existing matrix table
and detailed framework cards follow below.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import requests
import streamlit as st

_DOCS_ROOT = Path(__file__).parent.parent.parent / "docs"

# Map EVFFramework enum keys → display names used in the UI
_EVF_KEY_TO_LABEL: dict[str, str] = {
    "EU_AI_ACT":   "EU AI Act",
    "NIST_AI_RMF": "NIST AI RMF 1.0",
    "AIGP":        "AIGP",
    "ISO_42001":   "ISO 42001",
}

_TIER_STYLE: dict[str, dict[str, str]] = {
    "tier_1": {"border": "#16a34a", "bg": "#052e16", "badge_bg": "#16a34a", "label": "EXTERNALLY REVIEWED"},
    "tier_2": {"border": "#ca8a04", "bg": "#1c1407", "badge_bg": "#ca8a04", "label": "UNDER REVIEW"},
    "tier_3": {"border": "#475569", "bg": "#0f172a", "badge_bg": "#475569", "label": "INTERNAL ONLY"},
}

_FRAMEWORKS: list[dict[str, Any]] = [
    {
        "id": "nist_rmf",
        "evf_key": "NIST_AI_RMF",
        "label": "NIST AI Risk Management Framework (RMF 1.0)",
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
        "evf_key": "EU_AI_ACT",
        "label": "EU AI Act (2024/1689)",
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
        "evf_key": "AIGP",
        "label": "AI Governance Professional (AIGP) Framework",
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
        "evf_key": "ISO_42001",
        "label": "ISO/IEC 42001:2023 (AI Management System)",
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

_RISK_COLORS = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢", "N/A": "⚪"}

_SORT_COLUMNS = {
    "None (default)": None,
    "Risk Level": "risk_level",
    "Regulation Name": "regulation_name",
    "Last Updated": "last_updated",
}


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return getattr(requests, method)(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def _safe_get(token: str, path: str) -> Any:
    try:
        resp = _api(token, "get", path)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _fetch_evf_statuses(token: str) -> dict[str, dict]:
    """Fetch live EVF validation status for all 4 frameworks.
    Returns dict keyed by EVF framework key (e.g. 'EU_AI_ACT')."""
    data = _safe_get(token, "/api/v1/evf/validation-status")
    if not data:
        return {}
    return {item["framework"]: item for item in data} if isinstance(data, list) else {}


def _render_evf_banner(statuses: dict[str, dict]) -> None:
    """Render the live EVF Validation Status section (FR-EVF-11)."""
    st.markdown("### 🔐 EVF Validation Status")
    st.caption(
        "Live status per framework — drives approved language tier (FR-EVF-16). "
        "**Tier 1** = QCO issued by independent SME. "
        "**Tier 2** = under active SME review. "
        "**Tier 3** = internal review only, not for external claim."
    )

    cols = st.columns(4)
    evf_keys = ["EU_AI_ACT", "NIST_AI_RMF", "AIGP", "ISO_42001"]
    for col, key in zip(cols, evf_keys):
        status = statuses.get(key, {})
        tier = status.get("tier", "tier_3")
        qco_ref = status.get("qco_reference")
        expires_in = status.get("expires_in_days")
        style = _TIER_STYLE.get(tier, _TIER_STYLE["tier_3"])
        fw_display = _EVF_KEY_TO_LABEL.get(key, key)

        with col:
            badge_html = (
                f'<div style="border:1px solid {style["border"]};border-radius:8px;'
                f'padding:10px;background:{style["bg"]};min-height:100px">'
                f'<div style="font-size:0.7rem;color:#94a3b8;margin-bottom:4px">{fw_display}</div>'
                f'<span style="background:{style["badge_bg"]};color:#fff;padding:2px 8px;'
                f'border-radius:8px;font-size:0.65rem;font-weight:700">{style["label"]}</span>'
            )
            if qco_ref:
                badge_html += f'<div style="font-size:0.65rem;color:#94a3b8;margin-top:6px">📄 {qco_ref}</div>'
                if expires_in is not None:
                    color = "#dc2626" if expires_in < 30 else "#ca8a04" if expires_in < 60 else "#94a3b8"
                    badge_html += f'<div style="font-size:0.65rem;color:{color};margin-top:2px">Expires in {expires_in}d</div>'
            badge_html += "</div>"
            st.markdown(badge_html, unsafe_allow_html=True)

    if not any(statuses.get(k, {}).get("tier") == "tier_1" for k in evf_keys):
        st.warning(
            "⚠️ No framework has an active Qualified Compliance Opinion (QCO). "
            "All framework references must use **Tier 3** language (internal only) "
            "until an independent SME review is completed. "
            "See docs/COMPLIANCE_CLAIMS_MATRIX.md for approved language.",
            icon="⚠️",
        )


def _fetch_matrix_rows(
    token: str, sort_by: str | None, sort_dir: str,
    filter_regulation: str | None, filter_risk_level: str | None,
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
    token: str, sort_by: str | None, sort_dir: str,
    filter_regulation: str | None, filter_risk_level: str | None,
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
        cols = st.columns(col_widths)
        cols[0].write(row.get("regulation_name", ""))
        cols[1].write(row.get("article_section", ""))
        cols[2].write(f"{icon} {risk}")
        cols[3].write(row.get("status", ""))
        cols[4].write(cov_str)
        cols[5].write(row.get("last_updated") or "—")


def render(token: str) -> None:
    st.header("📋 Compliance Claims Matrix")
    st.caption(
        "**Version 1.0 | 2026 | Status: Requires SME Review Before External Use**  \n"
        "This matrix clarifies what SARO supports versus what it does not replace."
    )

    st.warning(
        "**Important Disclaimer:** SARO is an AI risk assessment and audit tool — not a "
        "certification body, legal advisor, or regulatory authority.",
        icon="⚠️",
    )

    st.divider()

    # ── Live EVF Validation Status (P-0 — FR-EVF-11) ─────────────────────────
    evf_statuses = _fetch_evf_statuses(token)
    _render_evf_banner(evf_statuses)

    st.divider()

    # ── Sort & filter controls ────────────────────────────────────────────────
    st.subheader("Matrix Rows")
    ctrl_cols = st.columns([2, 1, 2, 1])
    with ctrl_cols[0]:
        sort_label = st.selectbox("Sort by", options=list(_SORT_COLUMNS.keys()), key="matrix_sort_col")
        sort_by = _SORT_COLUMNS[sort_label]
    with ctrl_cols[1]:
        sort_dir = st.radio("Direction", options=["asc", "desc"], key="matrix_sort_dir", horizontal=True)
    with ctrl_cols[2]:
        filter_regulation = st.selectbox(
            "Filter regulation",
            options=["All", "EU AI Act", "NIST AI RMF", "AIGP Framework", "ISO 42001"],
            key="matrix_filter_reg",
        )
        filter_regulation = None if filter_regulation == "All" else filter_regulation
    with ctrl_cols[3]:
        filter_risk = st.selectbox(
            "Filter risk level", options=["All", "Critical", "High", "Medium", "Low", "N/A"],
            key="matrix_filter_risk",
        )
        filter_risk_level = None if filter_risk == "All" else filter_risk

    rows = _fetch_matrix_rows(token, sort_by, sort_dir, filter_regulation, filter_risk_level)

    export_col, _ = st.columns([1, 3])
    with export_col:
        if rows:
            csv_bytes = _fetch_csv_export(token, sort_by, sort_dir, filter_regulation, filter_risk_level)
            if csv_bytes:
                st.download_button(
                    "⬇️ Export CSV", data=csv_bytes,
                    file_name=f"saro-compliance-matrix-{date.today().isoformat()}.csv",
                    mime="text/csv", key="matrix_export_csv",
                )
        else:
            st.button("⬇️ Export CSV", disabled=True, key="matrix_export_csv_disabled")

    st.caption(f"{len(rows)} row(s) shown")
    _render_matrix_table(rows)

    st.divider()

    # ── Per-framework detail cards ────────────────────────────────────────────
    st.subheader("Framework Detail")
    for fw in _FRAMEWORKS:
        evf = evf_statuses.get(fw["evf_key"], {})
        tier = evf.get("tier", "tier_3")
        tier_label = _TIER_STYLE.get(tier, _TIER_STYLE["tier_3"])["label"]
        with st.expander(f"**{fw['label']}** — {tier_label}", expanded=False):
            if fw["disclaimer"]:
                st.markdown(fw["disclaimer"])
                st.divider()
            # EVF status inline
            evf_label = evf.get("label", "Internal Review Only — Not for External Claim")
            st.info(f"**EVF Status:** {evf_label}", icon="🔐")
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

    md_path = _DOCS_ROOT / "COMPLIANCE_CLAIMS_MATRIX.md"
    if not md_path.exists():
        md_path = _DOCS_ROOT / "compliance-claims.md"
    if md_path.exists():
        st.download_button(
            "⬇️ Download Full Claims Matrix (Markdown)",
            data=md_path.read_bytes(),
            file_name="saro-compliance-claims-matrix.md",
            mime="text/markdown",
        )
