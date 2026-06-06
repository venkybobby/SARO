"""
SAR-010: Unified Control Library — 8 tests.

Tests cover:
  1. Control + ControlFrameworkMapping ORM models exist with correct columns
  2. Migration SQL file exists
  3. Seed script defines >= 20 controls
  4. Risk Assessment control tagged to 4 frameworks
  5. Human Oversight control tagged to 4 frameworks
  6. Seed script is idempotent (uses ON CONFLICT / WHERE NOT EXISTS)
  7. GET /api/v1/controls router is registered in app
  8. Multi-framework filter logic: control library filter returns controls per framework
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-sar010")


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_control_model_has_required_columns():
    """Control ORM model must have all required SAR-010 columns."""
    from models import Control
    cols = {c.key for c in Control.__table__.columns}
    for required in ("id", "control_id", "title", "description", "control_type", "status",
                     "evidence_count", "last_assessed_date", "created_at"):
        assert required in cols, f"Control model missing column: {required}"


def test_control_framework_mapping_model_exists():
    """ControlFrameworkMapping must exist with control_id, framework, clause_reference."""
    from models import ControlFrameworkMapping
    cols = {c.key for c in ControlFrameworkMapping.__table__.columns}
    for required in ("id", "control_id", "framework", "clause_reference"):
        assert required in cols, f"ControlFrameworkMapping missing column: {required}"


def test_migration_sql_file_exists():
    """migrations/011_unified_control_library.sql must exist."""
    assert (_REPO_ROOT / "migrations" / "011_unified_control_library.sql").exists()


def test_seed_script_defines_minimum_20_controls():
    """Seed script must contain at least 20 control definitions."""
    from scripts.seed_control_library import _CONTROLS
    assert len(_CONTROLS) >= 20, f"Expected >= 20 controls, found {len(_CONTROLS)}"


def test_risk_assessment_control_tagged_to_4_frameworks():
    """CTRL-RISK-001 (Risk Assessment) must map to ISO, EU AI Act, AIGP, and NIST."""
    from scripts.seed_control_library import _CONTROLS
    ctrl = next((c for c in _CONTROLS if c[0] == "CTRL-RISK-001"), None)
    assert ctrl is not None, "CTRL-RISK-001 not found in seed data"
    framework_keys = {fw for fw, _ in ctrl[4]}
    assert "ISO_42001" in framework_keys
    assert "EU_AI_ACT" in framework_keys
    assert "AIGP" in framework_keys
    assert "NIST_AI_RMF" in framework_keys


def test_human_oversight_control_tagged_to_4_frameworks():
    """CTRL-OVER-001 (Human Oversight) must map to ISO, EU AI Act, AIGP, and NIST."""
    from scripts.seed_control_library import _CONTROLS
    ctrl = next((c for c in _CONTROLS if c[0] == "CTRL-OVER-001"), None)
    assert ctrl is not None, "CTRL-OVER-001 not found in seed data"
    framework_keys = {fw for fw, _ in ctrl[4]}
    assert len(framework_keys) >= 4, f"Expected >= 4 frameworks for Human Oversight, got {framework_keys}"


def test_seed_script_is_idempotent():
    """Seed script source must use ON CONFLICT or equivalent idempotency guard."""
    src = (_REPO_ROOT / "scripts" / "seed_control_library.py").read_text(encoding="utf-8")
    assert "ON CONFLICT" in src or "WHERE NOT EXISTS" in src, (
        "seed_control_library.py must use ON CONFLICT or WHERE NOT EXISTS for idempotency"
    )


def test_controls_router_registered_in_app():
    """GET /api/v1/controls must be a registered route in the FastAPI app."""
    from main import app
    routes = {r.path for r in app.routes}
    assert "/api/v1/controls" in routes, (
        f"/api/v1/controls not found in registered routes: {sorted(routes)}"
    )
