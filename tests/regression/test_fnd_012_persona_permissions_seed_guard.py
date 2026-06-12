"""
FND-012: migrations/004_add_persona_permissions.sql seeded persona_permissions
with an unconditional INSERT that assumed the legacy table shape (SERIAL id,
denied_actions/trace_mode columns). On the app-startup path, create_all_tables()
builds persona_permissions from the ORM model (UUID id with no SERIAL default,
no denied_actions/trace_mode) BEFORE the migration runs, so the seed failed with
`column "denied_actions" does not exist` / `null value in column "id"` and the
runner hard-refused to serve traffic — the backend never started on a fresh DB.

Fix: guard the legacy seed so it only runs when the table has the legacy shape
(denied_actions column present — the raw-psql/CI path). On the ORM-shaped table
the seed is skipped; the runtime seed_persona_permissions() populates it instead.

This pins (static check of the migration SQL — no live DB required) that the
INSERT lives inside a guard that tests for the denied_actions column, so it can
never again fire unconditionally against the ORM-shaped table.
"""

from __future__ import annotations

import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).parents[2]
MIGRATION = REPO_ROOT / "migrations" / "004_add_persona_permissions.sql"


def _read() -> str:
    return MIGRATION.read_text(encoding="utf-8")


class TestPersonaPermissionsSeedIsGuarded:
    def test_migration_file_exists(self):
        assert MIGRATION.exists(), f"{MIGRATION} not found"

    def test_seed_insert_is_wrapped_in_a_denied_actions_guard(self):
        sql = _read()

        insert_match = re.search(
            r"INSERT\s+INTO\s+persona_permissions", sql, re.IGNORECASE
        )
        assert insert_match, (
            "Expected an INSERT INTO persona_permissions seed in migration 004"
        )

        # The seed INSERT must sit inside a DO $$ ... END $$ block.
        do_block = re.search(r"DO\s+\$\$.*?END\s+\$\$", sql, re.IGNORECASE | re.DOTALL)
        assert do_block, (
            "migration 004 seeds persona_permissions with an unguarded INSERT. "
            "On the app-startup path create_all_tables() builds the ORM-shaped "
            "table first and the legacy seed fails (FND-012). Wrap the seed in a "
            "DO $$ ... END $$ guard."
        )
        assert (
            insert_match.start() > do_block.start()
            and insert_match.end() <= do_block.end()
        ), (
            "The persona_permissions seed INSERT must live INSIDE the DO $$ guard "
            "block, not before/after it (FND-012)."
        )

        # The guard must condition on the denied_actions column existing, so the
        # seed only runs against the legacy table shape (not the ORM shape).
        guard = do_block.group(0)
        assert (
            re.search(r"information_schema\.columns", guard, re.IGNORECASE)
            and "persona_permissions" in guard
            and "denied_actions" in guard
        ), (
            "The DO $$ guard must check information_schema.columns for the "
            "persona_permissions.denied_actions column before seeding, so the legacy "
            "seed is skipped on the ORM-shaped table created by create_all_tables() (FND-012)."
        )
