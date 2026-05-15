"""
Compliance Claims Matrix Tab — SARO vs. NIST RMF, EU AI Act, AIGP, ISO 42001.
Reads from docs/compliance-claims.md and renders as a structured Streamlit page.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_DOCS_ROOT = Path(__file__).parent.parent.parent / "docs"

_FRAMEWORKS = [
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


def _rag_badge(rag: str) -> str:
    style = _RAG_STYLE.get(rag, "background:#6b7280;color:#fff")
    return f'<span style="{style};padding:2px 10px;border-radius:10px;font-size:0.8rem;font-weight:700">{rag}</span>'


def render(token: str) -> None:  # noqa: ARG001 — token not needed (static page)
    st.header("📋 Compliance Claims Matrix")
    st.caption(
        "**Version 1.0 | May 2026 | Status: Requires SME Review Before External Use**  \n"
        "This matrix clarifies what SARO claims to support versus what it does not replace. "
        "Share with legal counsel before representing SARO capabilities to regulators."
    )

    st.warning(
        "**Important Disclaimer:** SARO is an AI risk assessment and audit tool — not a "
        "certification body, legal advisor, or regulatory authority. Findings and risk scores "
        "are analytical aids and do not constitute legal compliance or regulatory approval.",
        icon="⚠️",
    )

    st.divider()

    # Summary RAG table
    st.subheader("Framework Coverage Summary")
    cols = st.columns(len(_FRAMEWORKS))
    for col, fw in zip(cols, _FRAMEWORKS):
        with col:
            st.markdown(
                f'<div style="border:1px solid #334155;border-radius:8px;padding:12px;text-align:center">'
                f'<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:6px">{fw["label"].split("(")[0].strip()}</div>'
                f'{_rag_badge(fw["rag"])}'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # Detailed per-framework tables
    for fw in _FRAMEWORKS:
        with st.expander(f"**{fw['label']}** — {fw['rag']}", expanded=True):
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
