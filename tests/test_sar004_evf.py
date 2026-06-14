"""
SAR-004 EVF gap tests.

All 9 tests are pure unit / file-level checks — no DB connection required.
"""
from __future__ import annotations

import inspect
from pathlib import Path


# ── 1. EVFFramework enum has exactly 4 expected values ───────────────────────

def test_evf_framework_enum_has_4_values():
    from models import EVFFramework
    values = {e.value for e in EVFFramework}
    assert values == {"EU_AI_ACT", "NIST_AI_RMF", "AIGP", "ISO_42001"}


# ── 2. SMEEngagementState has all 8 states ───────────────────────────────────

def test_sme_engagement_state_machine_has_all_states():
    from models import SMEEngagementState
    values = {e.value for e in SMEEngagementState}
    expected = {
        "SHORTLISTED", "COI_CLEARED", "SOW_ISSUED", "REVIEW_IN_PROGRESS",
        "DRAFT_QCO_RECEIVED", "QCO_APPROVED", "PUBLISHED", "RENEWAL_TRIGGERED",
    }
    assert expected.issubset(values)


# ── 3. ValidationGate has the 7 gate boolean columns ─────────────────────────

def test_validation_gate_has_7_items():
    from models import ValidationGate
    column_names = {c.name for c in ValidationGate.__table__.columns}
    expected = {
        "coi_declared_approved",
        "sow_executed",
        "evidence_package_delivered",
        "product_demo_completed",
        "draft_qco_received",
        "saro_legal_review_completed",
        "qco_approved_ref_assigned",
    }
    assert expected.issubset(column_names)


# ── 4. QCORegistry has a published field defaulting to False ─────────────────

def test_qco_registry_model_has_published_field():
    from models import QCORegistry
    col = QCORegistry.__table__.columns.get("published")
    assert col is not None, "QCORegistry must have a 'published' column"
    # Check default is False
    default_val = col.default.arg if col.default is not None else None
    assert default_val is False, f"Expected default False, got {default_val!r}"


# ── 5. evf_status_admin.py tab file exists ───────────────────────────────────

def test_evf_status_admin_tab_file_exists():
    # STORY-105: the Streamlit tab was removed; the EVF admin page lives in React.
    tab_path = Path("frontend/src/pages/EvfAdmin.jsx")
    assert tab_path.exists(), f"Missing: {tab_path}"


# ── 6. evf_admin tab is registered in the React nav ──────────────────────────

def test_evf_admin_tab_registered_in_app():
    source = Path("frontend/src/components/Sidebar.jsx").read_text(encoding="utf-8")
    assert "evf_admin" in source, "Sidebar.jsx must register the 'evf_admin' tab"


# ── 7. upgrade_to_tier1 has the expected parameters ──────────────────────────

def test_compliance_label_service_upgrade_to_tier1_signature():
    from services.compliance_label_service import upgrade_to_tier1
    sig = inspect.signature(upgrade_to_tier1)
    params = set(sig.parameters.keys())
    assert {"framework", "qco_reference", "sme_firm", "qco_expiry"}.issubset(params), (
        f"upgrade_to_tier1 missing expected parameters. Got: {params}"
    )


# ── 8. evf_qco_service imports compliance_label_service ──────────────────────

def test_evf_qco_service_imports_compliance_label_service():
    source = Path("services/evf_qco_service.py").read_text(encoding="utf-8")
    assert "compliance_label_service" in source or "upgrade_to_tier1" in source, (
        "services/evf_qco_service.py must reference compliance_label_service or upgrade_to_tier1"
    )


# ── 9. ValidationGate has exactly 7 gate-item boolean columns ────────────────

def test_gate_checklist_has_exactly_7_boolean_columns():
    from models import ValidationGate
    from sqlalchemy import Boolean

    _GATE_SUFFIXES = (
        "_approved", "_executed", "_delivered", "_completed",
        "_received", "_assigned",
    )
    gate_bool_cols = [
        c for c in ValidationGate.__table__.columns
        if isinstance(c.type, Boolean)
        and any(c.name.endswith(sfx) for sfx in _GATE_SUFFIXES)
    ]
    assert len(gate_bool_cols) == 7, (
        f"Expected exactly 7 gate boolean columns, found {len(gate_bool_cols)}: "
        f"{[c.name for c in gate_bool_cols]}"
    )
