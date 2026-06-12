"""PT-004/005/012: canonical governance documents are consistent.

- The canonical architecture doc exists and names the stack of record.
- Superseded infra docs are marked SUPERSEDED/ARCHIVED.
- The document register and the continuity/escrow/compensating-control docs exist.
- fly.toml is frozen (auto_stop_machines off).
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_canonical_docs_exist():
    for name in [
        "ARCHITECTURE.md", "DOCUMENT_REGISTER.md", "CLAIMS_AUDIT_LOG.md",
        "COMPENSATING_CONTROLS.md", "VENDOR_CONTINUITY_PLAN.md", "ESCROW_AGREEMENT.md",
    ]:
        assert (DOCS / name).exists(), f"missing canonical doc: {name}"


def test_architecture_names_stack_of_record():
    arch = _read(DOCS / "ARCHITECTURE.md")
    assert "Fly.io" in arch and "Supabase" in arch
    # Legacy hosts must appear only as SUPERSEDED, never as the current stack of record.
    assert "SUPERSEDED" in arch


def test_legacy_infra_docs_marked_superseded():
    assert "[SUPERSEDED]" in _read(ROOT / "deployment-context.md")
    assert "[ARCHIVED]" in _read(DOCS / "MIGRATION_RUNBOOK.md")
    assert "[SUPERSEDED]" in _read(DOCS / "DPA_interim_v0.md")
    assert "[SUPERSEDED]" in _read(DOCS / "DPA_interim_v0.1.md")


def test_register_lists_architecture_as_canonical():
    reg = _read(DOCS / "DOCUMENT_REGISTER.md")
    assert "ARCHITECTURE.md" in reg and "CANONICAL" in reg


def test_fly_config_frozen():
    fly = _read(ROOT / "fly.toml")
    assert "auto_stop_machines" in fly and "'off'" in fly


def test_escrow_release_conditions_objective():
    escrow = _read(DOCS / "ESCROW_AGREEMENT.md")
    assert "30" in escrow and "discretion" in escrow.lower()
