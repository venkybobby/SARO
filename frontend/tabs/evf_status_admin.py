"""
EVF Admin Status Page — SAR-004.

Internal-only dashboard for tracking the External SME Validation Framework programme.
Accessible only to admin persona (enforced by tab registry in app.py).

Sections:
  1. Framework status cards (lifecycle state, gate checklist, language tier badge)
  2. QCO Registry table
  3. QCO expiry alert banner (60-day warning)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_EVF_FRAMEWORKS = ["EU_AI_ACT", "NIST_AI_RMF", "AIGP", "ISO_42001"]

_LIFECYCLE_STATES = [
    "SHORTLISTED", "COI_CLEARED", "SOW_ISSUED", "REVIEW_IN_PROGRESS",
    "DRAFT_QCO_RECEIVED", "QCO_APPROVED", "PUBLISHED", "RENEWAL_TRIGGERED",
]

_GATE_ITEMS = [
    ("coi_declared_approved", "COI Declared & Approved"),
    ("sow_executed", "SOW Executed"),
    ("evidence_package_delivered", "Evidence Package Delivered"),
    ("product_demo_completed", "Product Demo Completed"),
    ("draft_qco_received", "Draft QCO Received"),
    ("saro_legal_review_completed", "SARO Legal Review Completed"),
    ("qco_approved_ref_assigned", "QCO Approved & Reference Assigned"),
]


def _api(token: str, method: str, path: str, **kwargs: Any) -> requests.Response:
    base = st.session_state.get("api_base", "http://localhost:8000").rstrip("/")
    return getattr(requests, method)(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )


def render(token: str) -> None:
    st.title("🔐 EVF Validation Programme — Admin Status")
    st.caption(
        "Internal tracking dashboard for External SME Validation Framework. "
        "Admin access only. Not for external distribution."
    )

    # ── Fetch EVF status ──────────────────────────────────────────────────
    try:
        resp = _api(token, "get", "/api/v1/evf/engagements")
        engagements = resp.json() if resp.status_code == 200 else []
    except Exception:
        engagements = []

    try:
        # SAR-004: endpoint is /api/v1/evf/qco (not /qco-registry)
        resp_qco = _api(token, "get", "/api/v1/evf/qco")
        qco_records = resp_qco.json() if resp_qco.status_code == 200 else []
    except Exception:
        qco_records = []

    # ── QCO expiry alert ──────────────────────────────────────────────────
    import datetime
    today = datetime.date.today()
    expiring_soon = []
    for qco in (qco_records if isinstance(qco_records, list) else []):
        expiry = qco.get("expiry_date")
        if expiry:
            try:
                exp_date = datetime.date.fromisoformat(str(expiry)[:10])
                days_left = (exp_date - today).days
                if 0 <= days_left <= 60:
                    expiring_soon.append((qco.get("qco_reference_number", "?"), days_left))
            except ValueError:
                pass
    if expiring_soon:
        for ref, days in expiring_soon:
            st.error(f"⚠️ QCO {ref} expires in {days} days — renewal required.")

    # ── Framework cards ───────────────────────────────────────────────────
    st.subheader("Framework Validation Status")
    cols = st.columns(2)
    from services.compliance_label_service import get_label
    for i, fw_key in enumerate(_EVF_FRAMEWORKS):
        lbl = get_label(fw_key)
        tier = lbl["tier"]
        col = cols[i % 2]
        with col:
            tier_badge = f":{('green' if tier==1 else 'orange' if tier==2 else 'gray')}[{'Tier ' + str(tier)} — {lbl['badge_short']}]"
            st.markdown(f"### {lbl['display_name']} {tier_badge}")

            # Find engagement for this framework
            eng = next(
                (e for e in (engagements if isinstance(engagements, list) else [])
                 if e.get("framework") == fw_key),
                None,
            )
            state = eng.get("state", "SHORTLISTED") if eng else "SHORTLISTED"
            new_state = st.selectbox(
                "Lifecycle state",
                _LIFECYCLE_STATES,
                index=_LIFECYCLE_STATES.index(state) if state in _LIFECYCLE_STATES else 0,
                key=f"evf_state_{fw_key}",
            )
            if eng and new_state != state:
                if st.button(f"Update {lbl['display_name']} state", key=f"btn_{fw_key}"):
                    _api(token, "patch", f"/api/v1/evf/engagements/{eng['id']}",
                         json={"state": new_state})
                    st.success(f"State updated to {new_state}")
                    st.rerun()

            # Gate checklist
            if eng:
                gate = eng.get("gate") or {}
                st.markdown("**Validation Gate Checklist**")
                for field, label in _GATE_ITEMS:
                    item_done = gate.get(field, False)
                    icon = "✅" if item_done else "⬜"
                    st.markdown(f"{icon} {label}")
            else:
                # SAR-004: inline engagement create form
                st.warning("No engagement record for this framework.")
                with st.expander("➕ Create SME Engagement"):
                    with st.form(key=f"create_eng_{fw_key}"):
                        sme_firm = st.text_input("SME Firm Name", key=f"firm_{fw_key}")
                        sme_contact = st.text_input("Key Contact (optional)", key=f"contact_{fw_key}")
                        sme_cred = st.text_input("Credential (optional)", key=f"cred_{fw_key}")
                        notes = st.text_area("Notes (optional)", key=f"notes_{fw_key}", height=80)
                        if st.form_submit_button("Create Engagement", type="primary"):
                            if not sme_firm.strip():
                                st.error("SME Firm Name is required.")
                            else:
                                payload = {
                                    "framework": fw_key,
                                    "sme_firm_name": sme_firm.strip(),
                                    "sme_key_contact": sme_contact.strip() or None,
                                    "sme_credential": sme_cred.strip() or None,
                                    "notes": notes.strip() or None,
                                }
                                try:
                                    r = _api(token, "post", "/api/v1/evf/engagements", json=payload)
                                    if r.status_code in (200, 201):
                                        st.success(f"Engagement created for {lbl['display_name']}.")
                                        st.rerun()
                                    else:
                                        st.error(f"Failed ({r.status_code}): {r.text[:200]}")
                                except Exception as exc:
                                    st.error(f"Request failed: {exc}")

            st.markdown(f"*{lbl['label_text']}*")
            st.divider()

    # ── QCO Registry ─────────────────────────────────────────────────────
    st.subheader("QCO Registry")
    if isinstance(qco_records, list) and qco_records:
        import pandas as pd
        df = pd.DataFrame([{
            "Reference": r.get("qco_reference_number", ""),
            "Framework": r.get("framework_covered", ""),
            "SME Firm": r.get("sme_firm", ""),
            "Issue Date": r.get("issue_date", ""),
            "Expiry": r.get("expiry_date", ""),
            "Published": "✅" if r.get("published") else "⏳",
        } for r in qco_records])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No QCO records yet.")
