"""FND-091: `database.py`'s startup self-heal mechanism
(`_APP_TABLE_EXPECTED_COLS` / `_SAFE_ALTER_COLS`) had no `"tenants"` entry in
either dict, despite the code's own comment claiming coverage for "precious
tables (users, tenants)". `_APP_TABLE_EXPECTED_COLS` is what `ensure_app_schema()`
iterates to *detect* drift at startup -- with no `tenants` key, tenant column
drift (e.g. FND-090's `settings_json`, FND-067's `security_contact_email`) was
structurally invisible to the detector. `_SAFE_ALTER_COLS["tenants"]` existed
as an empty dict -- already drop-exempt via the Step-2 `table_name not in
_SAFE_ALTER_COLS` check -- but had nothing to ALTER even in the rare case the
healer ran off some other table's drift.

Fix: populate both dicts for `tenants`, matching the pattern already used for
`users`/`audit_traces`/`audits`/`scan_reports`.
"""

from __future__ import annotations

import database
import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit]


class TestDatabaseExpectedCols:
    def test_tenants_in_expected_cols(self):
        assert "tenants" in database._APP_TABLE_EXPECTED_COLS, (
            "tenants missing from _APP_TABLE_EXPECTED_COLS -- ensure_app_schema() "
            "can never detect tenant column drift"
        )

    def test_tenants_expected_cols_matches_orm_model(self):
        # models.Tenant's mapped_column fields (excludes relationship()s).
        expected_orm_columns = {
            "id",
            "name",
            "slug",
            "settings_json",
            "security_contact_email",
            "created_at",
        }
        cols = database._APP_TABLE_EXPECTED_COLS["tenants"]
        assert cols == expected_orm_columns, (
            f"_APP_TABLE_EXPECTED_COLS['tenants'] {cols} does not match "
            f"models.Tenant's columns {expected_orm_columns} -- missing columns "
            "would never be checked for drift; extra columns would falsely "
            "flag drift against a healthy DB"
        )


class TestDatabaseSafeAlterCols:
    def test_tenants_in_safe_alter_cols(self):
        assert "tenants" in database._SAFE_ALTER_COLS

    def test_settings_json_in_safe_alter_cols(self):
        """FND-090's column: must be ALTER-healable, not just drop-exempt."""
        alter_cols = database._SAFE_ALTER_COLS["tenants"]
        assert "settings_json" in alter_cols, (
            "settings_json missing from _SAFE_ALTER_COLS['tenants'] -- the "
            "self-heal has nothing to ADD even if it detects tenants drift"
        )
        assert alter_cols["settings_json"] == "JSON"

    def test_security_contact_email_in_safe_alter_cols(self):
        """FND-067's column: same blind spot as settings_json."""
        alter_cols = database._SAFE_ALTER_COLS["tenants"]
        assert "security_contact_email" in alter_cols
        assert alter_cols["security_contact_email"] == "VARCHAR(320)"

    def test_tenants_is_drop_exempt(self):
        """tenants must never be in the DROP path -- it holds live data."""
        assert "tenants" in database._SAFE_ALTER_COLS
