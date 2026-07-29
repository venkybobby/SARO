"""FND-090: `models.Tenant.settings_json` had no corresponding SQL migration
reaching production -- `migrations/000_create_core_tables.sql` was edited to
add the column to its CREATE TABLE *after* 000 had already been applied to
prod (an already-applied migration file must never be edited; see
docs/engineering-standards.md). `db.get(Tenant, id)` selects every ORM-mapped
column, so the drift turned FND-088's graceful "demo tenant misconfigured"
503 into an unhandled 500 on every call to GET /api/v1/demo/token.

This test can't reproduce the drift itself (pytest's SQLite fixtures build
tables straight from the current ORM metadata, which is exactly why local/CI
suites never caught it) -- it instead pins the *contract*: every column
`models.Tenant` declares must be reachable by grepping the SQL migration set,
so a future ORM-only column addition fails loud here instead of silently
drifting from a fresh Postgres migration chain (which
quality-gates.yml's "Migrations Apply Cleanly" job builds and CI validates).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit]

_ROOT = Path(__file__).parent.parent.parent
_MIGRATIONS_DIR = _ROOT / "migrations"


def _tenant_orm_columns() -> set[str]:
    """Real DB columns on models.Tenant (`mapped_column(...)`), excluding
    ORM-only `relationship(...)` attributes, which have no backing column."""
    src = (_ROOT / "models.py").read_text(encoding="utf-8")
    m = re.search(r"class Tenant\(Base\):.*?(?=\nclass \w+\(Base\):)", src, re.DOTALL)
    assert m, "models.Tenant class body not found"
    body = m.group(0)

    # Split into per-attribute chunks: each starts at a 4-space-indented
    # `name: Mapped[...]` line and runs until the next such line.
    starts = list(re.finditer(r"^\s{4}(\w+):\s*Mapped\[", body, re.MULTILINE))
    columns = set()
    for i, m2 in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        chunk = body[m2.start():end]
        if "mapped_column(" in chunk:
            columns.add(m2.group(1))
    return columns


def _migrations_mentioning_tenants() -> str:
    """Concatenated text of every .sql migration that touches `tenants`."""
    chunks = []
    for f in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        text = f.read_text(encoding="utf-8")
        if re.search(r"\btenants\b", text, re.IGNORECASE):
            chunks.append(text)
    return "\n".join(chunks)


def test_every_tenant_orm_column_has_a_migration():
    orm_columns = _tenant_orm_columns()
    migration_text = _migrations_mentioning_tenants()

    missing = [
        col
        for col in orm_columns
        if not re.search(rf"\b{re.escape(col)}\b", migration_text)
    ]
    assert not missing, (
        f"models.Tenant declares column(s) with no matching SQL migration: {missing} "
        "-- a fresh/production Postgres schema built from migrations/*.sql would "
        "be missing them, and any `db.get(Tenant, ...)` (SELECT *) call would 500."
    )


def test_settings_json_specifically_has_a_migration():
    """The exact FND-090 regression: settings_json reaching migrations/*.sql."""
    migration_text = _migrations_mentioning_tenants()
    assert re.search(r"\bsettings_json\b", migration_text), (
        "settings_json is declared on models.Tenant but no migrations/*.sql file "
        "adds it to the `tenants` table -- see migrations/043_tenants_settings_json.sql"
    )
