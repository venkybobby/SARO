"""
How SARO Reasons Tab — transparency page explaining SARO's analysis methodology.
Reads from docs/how-saro-reasons.md if available, otherwise renders hardcoded content.
"""
from __future__ import annotations

import pathlib

import streamlit as st

_HARDCODED_CONTENT = """
## Analysis Method

SARO analyses AI outputs through a 6-gate sequential pipeline:

1. **Ingest** — The AI output and its originating prompt are ingested and normalised.
2. **Classify** — The output is classified by domain (customer-facing, internal, regulated, etc.).
3. **Match** — Rule packs are matched against the output using semantic and lexical matching.
4. **Score** — A Bayesian risk score (0–100) is computed across MIT risk domains.
5. **Explain** — Each exception is explained with a finding, reason, and remediation hint.
6. **Remediate** — Actionable fix suggestions are generated and tracked until resolved.

---

## Score Calculation

Risk scores are computed using a Bayesian posterior mean across the following MIT AI Risk domains:

- Fairness & Non-Discrimination
- Transparency & Explainability
- Accountability & Human Oversight
- Safety & Reliability
- Privacy & Data Governance
- Security & Robustness

A score of **≥85** is Low Risk, **50–84** is Moderate Risk, and **<50** is High Risk.

---

## Confidence Meaning

Confidence reflects how certain SARO is about its findings, based on:

- Sample size (more samples = higher confidence)
- Rule coverage (how many applicable rules matched)
- Signal clarity (unambiguous vs. borderline findings)

| Confidence | Meaning |
|---|---|
| ≥90% | Very high — findings highly reliable |
| 70–89% | High — findings reliable |
| 50–69% | Moderate — some uncertainty |
| <50% | Low — treat findings as indicative only |

---

## Limitations

SARO is a governance and risk orchestration tool — it is **not** itself an AI model.

- SARO does not call external AI models. You provide the outputs.
- SARO's rule packs reflect the frameworks at the time of the last pack update.
- Statistical fairness metrics require demographic group labels in the batch.
- SARO cannot detect hallucinations that are factually plausible.
- Results should be reviewed by a qualified compliance or AI ethics professional.

*SARO — Smart AI Risk Orchestrator. Transparent, traceable, evidence-based.*
"""


def _load_content() -> str:
    """Load markdown content from docs/how-saro-reasons.md relative to repo root."""
    try:
        # Walk up from this file's directory to find the repo root
        here = pathlib.Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "docs" / "how-saro-reasons.md"
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
    except Exception:
        pass
    return _HARDCODED_CONTENT


def render(token: str) -> None:  # noqa: ARG001 — token unused for static page
    st.header("How SARO Reasons")
    st.caption("Transparency statement — methodology, scoring, confidence, and known limitations.")

    content = _load_content()
    st.markdown(content)

    st.divider()

    # PDF export — generates a plain-text version for offline sharing
    st.markdown("#### Export")
    st.download_button(
        "Export as PDF-Ready Text",
        data=content,
        file_name="how_saro_reasons.txt",
        mime="text/plain",
        help="Plain-text export suitable for PDF conversion or regulatory submissions.",
    )
