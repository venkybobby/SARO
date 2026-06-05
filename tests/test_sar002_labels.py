"""
SAR-002: Compliance label governance service tests.
Pure unit tests — no DB required.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Ensure repo root is on sys.path regardless of pytest invocation directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import services.compliance_label_service as label_svc

_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "compliance_label_registry.json"
_KNOWN_FRAMEWORKS = ["EU_AI_ACT", "NIST_AI_RMF", "AIGP", "ISO_42001"]


def _reset_registry() -> None:
    """Clear the module-level cache so the next call re-reads from disk."""
    label_svc._registry = None


def _force_all_tier2() -> str:
    """Reset every framework in the registry file to tier 2 and return the JSON string."""
    reg = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    for fw in reg["frameworks"].values():
        fw.update({"tier": 2, "qco_reference": None, "tier1_text": None, "sme_firm": None})
    content = json.dumps(reg, indent=2)
    _REGISTRY_PATH.write_text(content, encoding="utf-8")
    return content


@pytest.fixture(autouse=True)
def _tier2_registry():
    """
    Ensure each test sees all frameworks at tier 2 regardless of what other
    tests (e.g. EVF publish_qco tests) may have written to the registry file.
    Restores tier-2 state after the test too.
    """
    tier2_content = _force_all_tier2()
    label_svc._registry = None
    yield
    _REGISTRY_PATH.write_text(tier2_content, encoding="utf-8")
    label_svc._registry = None


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_compliance_label_registry_file_exists():
    assert _REGISTRY_PATH.exists(), f"Registry file not found at {_REGISTRY_PATH}"


def test_compliance_label_registry_all_frameworks_at_tier2():
    _reset_registry()
    reg = json.loads(_REGISTRY_PATH.read_text())
    frameworks = reg["frameworks"]
    assert set(frameworks.keys()) == set(_KNOWN_FRAMEWORKS)
    for key, fw in frameworks.items():
        assert fw["tier"] == 2, f"{key} tier should be 2, got {fw['tier']}"
        assert fw["qco_reference"] is None, f"{key} qco_reference should be null"


def test_get_label_returns_tier2_text_when_no_qco():
    _reset_registry()
    label = label_svc.get_label("EU_AI_ACT")
    assert label["tier"] == 2
    assert "EU AI Act" in label["label_text"]


def test_get_label_returns_correct_badge_color_for_tier2():
    _reset_registry()
    label = label_svc.get_label("NIST_AI_RMF")
    assert label["badge_color"] == "#ca8a04"


def test_get_label_raises_for_unknown_framework():
    _reset_registry()
    with pytest.raises(ValueError, match="Unknown framework"):
        label_svc.get_label("INVALID")


def test_get_all_labels_returns_4_entries():
    _reset_registry()
    labels = label_svc.get_all_labels()
    assert len(labels) == 4
    frameworks_returned = {lbl["framework"] for lbl in labels}
    assert frameworks_returned == set(_KNOWN_FRAMEWORKS)


def test_get_disclaimer_returns_non_empty_string():
    _reset_registry()
    disclaimer = label_svc.get_disclaimer()
    assert isinstance(disclaimer, str)
    assert len(disclaimer) > 0


def test_upgrade_to_tier1_updates_registry(tmp_path):
    """
    Verify upgrade_to_tier1 mutates the in-memory registry correctly,
    then restore the original registry file so the test is idempotent.
    """
    # Back up the original registry content
    original_content = _REGISTRY_PATH.read_text(encoding="utf-8")

    _reset_registry()
    try:
        label_svc.upgrade_to_tier1(
            framework="AIGP",
            qco_reference="QCO-TEST-001",
            sme_firm="Test SME Firm",
            qco_expiry="2027-06-04",
        )
        label = label_svc.get_label("AIGP")
        assert label["tier"] == 1
        assert label["qco_reference"] == "QCO-TEST-001"
        assert "EXTERNALLY REVIEWED" == label["badge_short"]
        assert "QCO-TEST-001" in label["label_text"]
    finally:
        # Restore original registry file and clear cache
        _REGISTRY_PATH.write_text(original_content, encoding="utf-8")
        _reset_registry()
