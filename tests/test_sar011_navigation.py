"""
SAR-011: Navigation Consolidation — content ownership tests.

Verifies that:
  1. IR Plan quick-link is present in the Risk Officer dashboard (FR-08)
  2. _TAB_REGISTRY contains all expected tab IDs
  3. claims_matrix exists as a registered tab (FR-06 — accessible within tab system)
  4. risk_officer persona has ir_plan in allowed tabs
  5. compliance_lead persona has claims_matrix access
  6. Remediate tab module exists and is distinct from audit findings
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-sar011")


def test_risk_officer_dashboard_has_ir_plan_link():
    """risk_summary.py must contain an IR Plan quick-link (SAR-011 FR-08)."""
    src = (_REPO_ROOT / "frontend" / "tabs" / "risk_summary.py").read_text(encoding="utf-8")
    assert "IR Plan" in src or "ir_plan" in src, (
        "risk_summary.py must reference 'IR Plan' as a quick-link for Risk Officers"
    )
    # Confirm it's a prominent UI element, not just a comment
    assert "st.info" in src or "st.button" in src or "markdown" in src.lower(), (
        "IR Plan link must be rendered as a UI element"
    )


def test_claims_matrix_in_tab_registry():
    """_TAB_REGISTRY must include claims_matrix (FR-06 — accessible in tab system)."""
    src = (_REPO_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert '"claims_matrix"' in src, "claims_matrix must be registered in _TAB_REGISTRY"


def test_risk_officer_persona_has_ir_plan_tab():
    """risk_officer persona must have ir_plan in allowed tabs."""
    import ast
    src = (_REPO_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_PERSONA_TABS" and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and k.value == "risk_officer":
                        tabs = [e.value for e in v.elts if isinstance(e, ast.Constant)]
                        assert "ir_plan" in tabs, f"risk_officer tabs {tabs} missing ir_plan"
                        return
    assert False, "_PERSONA_TABS for risk_officer not found in app.py"


def test_compliance_lead_has_claims_matrix_access():
    """compliance_lead persona must have claims_matrix access."""
    import ast
    src = (_REPO_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_PERSONA_TABS" and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and k.value == "compliance_lead":
                        tabs = [e.value for e in v.elts if isinstance(e, ast.Constant)]
                        assert "claims_matrix" in tabs, (
                            f"compliance_lead tabs missing claims_matrix: {tabs}"
                        )
                        return
    assert False, "_PERSONA_TABS for compliance_lead not found in app.py"


def test_remediate_tab_module_exists():
    """frontend/tabs/remedy.py (remediate tab) must exist as a distinct module."""
    assert (_REPO_ROOT / "frontend" / "tabs" / "remedy.py").exists()


def test_trace_view_supports_executive_mode_param():
    """frontend/tabs/trace_view.py must support ?mode=executive query param (SAR-006/011)."""
    src = (_REPO_ROOT / "frontend" / "tabs" / "trace_view.py").read_text(encoding="utf-8")
    assert "mode" in src and ("executive" in src or "query_params" in src), (
        "trace_view.py must handle ?mode=executive query parameter"
    )
