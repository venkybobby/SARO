"""PT-001: QCO records are pinned to the rule-pack hash they were reviewed against.

A QCO validates the current configuration only while its pinned rule_pack_hash
matches the active engine hash; a changed hash invalidates that coverage.
"""
from types import SimpleNamespace

import pytest

from services.evf_qco_service import (
    current_rule_pack_hash,
    qco_rule_pack_is_current,
)

pytestmark = pytest.mark.unit


def test_current_rule_pack_hash_is_sha256():
    h = current_rule_pack_hash()
    assert h is not None and len(h) == 64


def test_qco_with_matching_hash_is_current():
    qco = SimpleNamespace(rule_pack_hash=current_rule_pack_hash())
    assert qco_rule_pack_is_current(qco) is True


def test_qco_with_stale_hash_is_not_current():
    qco = SimpleNamespace(rule_pack_hash="0" * 64)
    assert qco_rule_pack_is_current(qco) is False


def test_qco_without_pinned_hash_is_not_current():
    assert qco_rule_pack_is_current(SimpleNamespace(rule_pack_hash=None)) is False


def test_model_has_pinning_columns():
    from models import QCORegistry
    cols = QCORegistry.__table__.columns.keys()
    assert "rule_pack_hash" in cols
    assert "findings_summary" in cols


def test_migration_file_present():
    from pathlib import Path
    mig = Path(__file__).resolve().parent.parent / "migrations" / "022_qco_rule_pack_pinning.sql"
    sql = mig.read_text(encoding="utf-8")
    assert "rule_pack_hash" in sql and "findings_summary" in sql
    assert "IF NOT EXISTS" in sql
