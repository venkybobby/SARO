"""
S-001: HuggingFace Sample Queue — model and migration tests.

Tests that:
  1. HFSampleQueue ORM model imports and has the correct fields.
  2. HFSampleStatus enum has the expected values.
  3. Migration SQL file 007 exists and is well-formed.
  4. database.py _APP_TABLE_EXPECTED_COLS includes hf_sample_queue.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestHFSampleQueueModel:
    def test_import(self):
        from models import HFSampleQueue, HFSampleStatus
        assert HFSampleQueue.__tablename__ == "hf_sample_queue"

    def test_status_enum_values(self):
        import enum as py_enum
        from models import HFSampleStatus
        assert set(m.value for m in HFSampleStatus) == {
            "pending", "processing", "processed", "failed"
        }

    def test_required_columns_present(self):
        from sqlalchemy import inspect as sa_inspect
        from models import HFSampleQueue
        mapper = HFSampleQueue.__mapper__
        col_names = {c.key for c in mapper.columns}
        required = {
            "id", "tenant_id", "vertical", "source_dataset",
            "prompt_text", "raw_output_text", "source_model",
            "status", "audit_id", "error_message", "retry_count",
            "sampled_at", "processed_at", "updated_at",
        }
        assert required <= col_names, f"Missing columns: {required - col_names}"

    def test_default_status_is_pending(self):
        from models import HFSampleQueue
        # Column-level INSERT defaults (applied at DB INSERT, not Python construction)
        status_col = HFSampleQueue.__mapper__.columns["status"]
        retry_col = HFSampleQueue.__mapper__.columns["retry_count"]
        source_col = HFSampleQueue.__mapper__.columns["source_model"]
        assert status_col.default.arg == "pending"
        assert retry_col.default.arg == 0
        assert source_col.default.arg == "unknown"


class TestHFQueueMigration:
    def test_migration_007_exists(self):
        migration_path = os.path.join(_REPO_ROOT, "migrations", "007_hf_sample_queue.sql")
        assert os.path.exists(migration_path), "Migration 007 not found"

    def test_migration_007_content(self):
        migration_path = os.path.join(_REPO_ROOT, "migrations", "007_hf_sample_queue.sql")
        content = open(migration_path).read()
        assert "CREATE TABLE IF NOT EXISTS hf_sample_queue" in content
        assert "hf_sample_status" in content
        assert "BEGIN;" in content
        assert "COMMIT;" in content

    def test_migration_008_audit_text_fields(self):
        migration_path = os.path.join(_REPO_ROOT, "migrations", "008_audit_text_fields.sql")
        assert os.path.exists(migration_path), "Migration 008 not found"
        content = open(migration_path).read()
        assert "prompt_text" in content
        assert "raw_output_text" in content


class TestDatabaseExpectedCols:
    def test_hf_sample_queue_in_expected_cols(self):
        from database import _APP_TABLE_EXPECTED_COLS
        assert "hf_sample_queue" in _APP_TABLE_EXPECTED_COLS
        expected = _APP_TABLE_EXPECTED_COLS["hf_sample_queue"]
        assert "tenant_id" in expected
        assert "prompt_text" in expected
        assert "raw_output_text" in expected
        assert "status" in expected
