"""STORY-109: the ORM PersonaPermission seed must match the single source of truth.

The fallback seed in database.py had a stale, incomplete ai_auditor row and was
missing the admin persona entirely, diverging from services.persona_service.
PERSONA_PERMISSIONS (and migration 004). Derive the seed from that source so a
fresh deploy grants every persona the correct tabs/actions and cannot drift again.
"""
from __future__ import annotations

import pytest

from services.persona_service import PERSONA_PERMISSIONS


@pytest.mark.unit
def test_seed_covers_all_personas_including_admin():
    from database import _build_persona_seeds

    seeded = {s["persona_role"] for s in _build_persona_seeds()}
    assert seeded == set(PERSONA_PERMISSIONS), (
        f"ORM seed personas must match the source of truth; missing: "
        f"{set(PERSONA_PERMISSIONS) - seeded}, extra: {seeded - set(PERSONA_PERMISSIONS)}"
    )
    assert "admin" in seeded, "admin persona must be seeded (was missing)"


@pytest.mark.unit
def test_ai_auditor_seed_matches_source_of_truth():
    from database import _build_persona_seeds

    by_role = {s["persona_role"]: s for s in _build_persona_seeds()}
    auditor = by_role["ai_auditor"]
    src = PERSONA_PERMISSIONS["ai_auditor"]
    assert auditor["allowed_tabs"] == src["tabs"], "ai_auditor tabs must match persona_service"
    assert auditor["allowed_actions"] == src["allowed_actions"], "ai_auditor actions must match"
    # the previously-missing capabilities are now present
    for tab in ("evidence_export", "drift_alerts", "upload"):
        assert tab in auditor["allowed_tabs"], f"ai_auditor must regain tab {tab!r}"


@pytest.mark.unit
def test_seed_only_uses_orm_columns():
    """ORM table stores persona_role/allowed_tabs/allowed_actions only — no denied_actions/trace_mode."""
    from database import _build_persona_seeds

    for s in _build_persona_seeds():
        assert set(s) == {"persona_role", "allowed_tabs", "allowed_actions"}, (
            f"seed dict has unexpected keys: {set(s)}"
        )
