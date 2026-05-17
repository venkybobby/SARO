"""
DPA & Governance Tab — Data Processing Agreement, sub-processors, IR plan, retention policy.
Renders from docs/ directory markdown files.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_DOCS_ROOT = Path(__file__).parent.parent.parent / "docs"

_DOCS = [
    {
        "label": "📄 Data Processing Agreement (DPA) Template",
        "file": "dpa-template.md",
        "description": "GDPR Article 28 compliant DPA template for customer agreements.",
        "download_name": "saro-dpa-template.md",
    },
    {
        "label": "🏢 Sub-Processor Inventory",
        "file": "sub-processors.md",
        "description": "List of all third-party sub-processors: Railway, Supabase, Redis.",
        "download_name": "saro-sub-processors.md",
    },
    {
        "label": "🚨 Incident Response Plan",  # ir_plan
        "file": "incident-response-plan.md",
        "description": "Procedures for false negatives, downtime, data breaches, and escalation.",
        "download_name": "saro-incident-response-plan.md",
    },
]


def _render_doc(doc: dict) -> None:
    path = _DOCS_ROOT / doc["file"]
    with st.expander(doc["label"], expanded=False):
        st.caption(doc["description"])
        if path.exists():
            content = path.read_text(encoding="utf-8")
            st.markdown(content)
            st.download_button(
                f"⬇️ Download {doc['download_name']}",
                data=path.read_bytes(),
                file_name=doc["download_name"],
                mime="text/markdown",
                key=f"dl_{doc['file']}",
            )
        else:
            st.warning(f"Document not found: `docs/{doc['file']}`")


def render(token: str) -> None:  # noqa: ARG001
    st.header("📄 DPA & Governance Documents")
    st.caption(
        "Data Processing Agreement template, sub-processor inventory, and incident response plan. "
        "Download any document for use in regulatory or customer-facing contexts."
    )

    st.info(
        "All documents require legal review before external use. "
        "Contact your legal counsel before sharing with customers or regulators.",
        icon="ℹ️",
    )

    for doc in _DOCS:
        _render_doc(doc)

    st.divider()
    st.subheader("Retention Policy Summary")
    st.markdown(
        "| Parameter | Value |\n"
        "|-----------|-------|\n"
        "| Default retention period | 90 days |\n"
        "| GDPR erasure SLA | 72 hours |\n"
        "| Audit chain tombstone | Preserved after purge |\n"
        "| Deletion certificate | PDF generated on erasure |"
    )
