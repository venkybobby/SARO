"""PT-010: tenant risk weights — degenerate-set rejection + Risk Officer write access."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from routers.risk_config import _require_risk_config_writer
from schemas import RiskConfigIn

pytestmark = pytest.mark.unit


def test_valid_distinct_weights_accepted():
    cfg = RiskConfigIn(domain_weights={"Privacy & Security": 0.85, "Socioeconomic & Environmental": 0.5})
    assert cfg.domain_weights["Privacy & Security"] == 0.85


def test_out_of_bounds_rejected():
    with pytest.raises(ValidationError):
        RiskConfigIn(domain_weights={"Privacy & Security": 1.5})


def test_all_zero_weights_rejected():
    with pytest.raises(ValidationError) as e:
        RiskConfigIn(domain_weights={"A": 0.0, "B": 0.0})
    assert "all domain weights are 0.0" in str(e.value)


def test_all_one_weights_rejected():
    with pytest.raises(ValidationError) as e:
        RiskConfigIn(domain_weights={"A": 1.0, "B": 1.0})
    assert "all domain weights are 1.0" in str(e.value)


def test_single_weight_at_extreme_allowed():
    # A single domain at 0.0 is a legitimate suppression, not a degenerate set.
    assert RiskConfigIn(domain_weights={"A": 0.0}).domain_weights == {"A": 0.0}


def _call_writer(user):
    return asyncio.run(_require_risk_config_writer(user))


def test_super_admin_can_write():
    assert _call_writer(SimpleNamespace(role="super_admin", persona_role=None)) is not None


def test_risk_officer_persona_can_write():
    assert _call_writer(SimpleNamespace(role="operator", persona_role="risk_officer")) is not None


@pytest.mark.parametrize("user", [
    SimpleNamespace(role="operator", persona_role="ai_auditor"),
    SimpleNamespace(role="operator", persona_role=None),
    SimpleNamespace(role="operator", persona_role="compliance_lead"),
])
def test_others_denied(user):
    with pytest.raises(HTTPException) as e:
        _call_writer(user)
    assert e.value.status_code == 403


def test_cap_justification_documented():
    from pathlib import Path
    doc = (Path(__file__).resolve().parent.parent / "docs" / "how-saro-reasons.md").read_text()
    assert "0.80" in doc and "statistical power" in doc
