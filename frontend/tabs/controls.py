"""
Unified Control Library Tab (SAR-010).

Sections:
  1. Framework filter + control table
  2. Per-control evidence traces (drill-down)
  3. Coverage summary per framework
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_FRAMEWORK_LABELS = {
    "EU_AI_ACT":    "EU AI Act",
    "NIST_AI_RMF":  "NIST AI RMF",
    "AIGP":         "AIGP",
    "ISO_42001":    "ISO 42001",
}
_TYPE_ICONS = {
    "preventive":    "🛡",
    "detective":     "🔍",
    "corrective":    "🔧",
    "compensating":  "⚖",
}
_STATUS_COLORS = {
    "active":     "#16a34a",
    "planned":    "#ca8a04",
    "deprecated": "#94a3b8",
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
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def render(token: str) -> None:
    st.title("📚 Unified Control Library")
    st.caption(
        "Cross-framework control catalogue — each control appears once and is tagged "
        "to the EU AI Act, NIST AI RMF, AIGP, and ISO 42001 clauses it satisfies."
    )

    # ── Framework filter ──────────────────────────────────────────────────────
    all_frameworks = list(_FRAMEWORK_LABELS.keys())
    selected_frameworks = st.multiselect(
        "Filter by framework",
        options=all_frameworks,
        format_func=lambda k: _FRAMEWORK_LABELS.get(k, k),
        default=[],
        placeholder="Show all frameworks",
    )

    # ── Fetch controls ────────────────────────────────────────────────────────
    params = ""
    if selected_frameworks:
        params = "&".join(f"frameworks={fw}" for fw in selected_frameworks)
        path = f"/api/v1/controls?{params}"
    else:
        path = "/api/v1/controls"

    controls = _safe_get(token, path) or []

    if not controls:
        st.info(
            "No controls in the library yet. "
            "Run `python scripts/seed_control_library.py` to populate the library "
            "with 20+ pre-mapped cross-framework controls."
        )
        return

    # ── Coverage summary ──────────────────────────────────────────────────────
    fw_coverage: dict[str, int] = {}
    for ctrl in controls:
        for fw_mapping in ctrl.get("frameworks", []):
            fw = fw_mapping.get("framework", "")
            fw_coverage[fw] = fw_coverage.get(fw, 0) + 1

    st.subheader("Framework Coverage")
    cov_cols = st.columns(len(_FRAMEWORK_LABELS))
    for col, (fw_key, fw_label) in zip(cov_cols, _FRAMEWORK_LABELS.items()):
        with col:
            count = fw_coverage.get(fw_key, 0)
            st.metric(fw_label, f"{count} controls")
    st.divider()

    # ── Control list ──────────────────────────────────────────────────────────
    st.subheader(f"Controls ({len(controls)})")

    search = st.text_input("Search controls", placeholder="e.g. fairness, transparency, oversight…")
    if search.strip():
        q = search.strip().lower()
        controls = [
            c for c in controls
            if q in (c.get("title") or "").lower()
            or q in (c.get("description") or "").lower()
            or q in (c.get("control_id") or "").lower()
        ]
        st.caption(f"{len(controls)} matches for '{search}'")

    for ctrl in controls:
        ctrl_id = ctrl.get("id", "")
        status_color = _STATUS_COLORS.get(ctrl.get("status", "active"), "#94a3b8")
        type_icon = _TYPE_ICONS.get(ctrl.get("control_type", ""), "•")
        evidence_count = ctrl.get("evidence_count", 0)

        with st.expander(
            f"{type_icon} **{ctrl.get('control_id')}** — {ctrl.get('title')}  "
            f"·  📎 {evidence_count} evidence traces"
        ):
            col_info, col_fw = st.columns([2, 1])

            with col_info:
                st.markdown(ctrl.get("description") or "")
                st.markdown(
                    f'<span style="color:{status_color};font-size:0.8rem;font-weight:600">'
                    f'● {ctrl.get("status","active").title()}</span>'
                    f'&nbsp;&nbsp;<span style="font-size:0.8rem;color:#94a3b8">'
                    f'{ctrl.get("control_type","").title()}</span>',
                    unsafe_allow_html=True,
                )
                if ctrl.get("last_assessed_date"):
                    st.caption(f"Last assessed: {ctrl['last_assessed_date'][:10]}")

            with col_fw:
                st.markdown("**Framework mappings:**")
                for mapping in ctrl.get("frameworks", []):
                    fw_label = _FRAMEWORK_LABELS.get(mapping["framework"], mapping["framework"])
                    clause = mapping.get("clause_reference") or ""
                    st.markdown(f"- {fw_label} `{clause}`")

            # Evidence traces drill-down
            if evidence_count > 0:
                if st.button(f"View {evidence_count} evidence traces", key=f"ev_{ctrl_id}"):
                    evidence = _safe_get(token, f"/api/v1/controls/{ctrl_id}/evidence") or []
                    if evidence:
                        st.markdown("**Evidence AuditTrace IDs:**")
                        for item in evidence[:10]:
                            trace_id = item.get("trace_id", "?")
                            gate = item.get("gate_name", "")
                            result = item.get("result", "")
                            st.caption(f"`{trace_id}` — {gate} ({result})")
                    else:
                        st.caption("No evidence traces found.")
