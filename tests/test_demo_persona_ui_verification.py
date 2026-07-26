"""Pins for the persona UI verification harness (scripts/demo_persona_ui_verification.py).

The harness derives its expectations by parsing Sidebar.jsx at runtime. These
tests pin that the parser stays in sync with the frontend: if PERSONA_TABS,
TAB_REGISTRY, or ROLE_LABELS change shape in a way the parser cannot read, the
harness would silently verify nothing — these tests make that loud instead.
No browser required; the Playwright walk itself is operator-run (see the
runbook, docs/demo/AZURE_VERTEX_E2E_DEMO.md Part 6).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demo_persona_ui_verification import DEFAULT_PERSONAS, parse_sidebar

pytestmark = pytest.mark.unit


def test_all_six_personas_parse_with_nonempty_tab_lists():
    persona_tabs, _labels, _roles = parse_sidebar()
    assert set(persona_tabs) == {
        "compliance_lead",
        "risk_officer",
        "ai_auditor",
        "admin",
        "super_admin",
        "operator",
    }
    assert all(tabs for tabs in persona_tabs.values()), "empty persona tab list"


def test_every_persona_tab_has_a_label_and_a_role_label():
    persona_tabs, labels, roles = parse_sidebar()
    for persona, tabs in persona_tabs.items():
        missing = [t for t in tabs if t not in labels]
        assert not missing, (
            f"{persona} references tabs with no TAB_REGISTRY label: {missing}"
        )
        assert persona in roles, (
            f"{persona} has no ROLE_LABELS entry (switcher unclickable)"
        )


def test_default_walk_covers_the_requested_business_personas():
    # The ask behind this harness: ai auditor, risk auditor (risk_officer),
    # and the lead persona. Pin the default set so a refactor can't drop one.
    assert DEFAULT_PERSONAS == ["ai_auditor", "risk_officer", "compliance_lead"]
    persona_tabs, _labels, _roles = parse_sidebar()
    for p in DEFAULT_PERSONAS:
        assert p in persona_tabs


def test_labels_are_unique_so_click_targets_are_unambiguous():
    # The walk clicks tabs by exact label text; duplicate labels would make
    # get_by_text(exact=True).first click the wrong nav entry silently.
    _persona_tabs, labels, _roles = parse_sidebar()
    assert len(set(labels.values())) == len(labels)
