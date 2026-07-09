"""FND-049 — `saro ingest` surfaced a raw traceback on a source-discovery failure.

`_run_ingest`'s call to `discover_object_keys(...)` was unguarded — a source-level
failure (bad bucket, permissions, an unreachable local path swapped out from under
the process) propagated as a raw Python exception/traceback through the CLI instead
of AC-1.3's promised clear, operator-facing message. Per-object-key read failures
(inside the discover-then-parse loop) were already handled; the discovery call
itself was not. Found by independent reviewer during STORY-410's verify stage.
Fix: wrap `discover_object_keys(...)` in try/except raising `CliError`.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from click.testing import CliRunner  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import cli as cli_module  # noqa: E402
from database import Base  # noqa: E402
from models import Tenant, User  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fa")
_USER = uuid.UUID("00000000-0000-0000-0000-0000000000fb")


@pytest.mark.regression
def test_discover_object_keys_failure_is_a_cli_error_not_a_traceback(
    tmp_path, monkeypatch
):
    db = _Session()
    try:
        db.query(User).delete()
        db.query(Tenant).delete()
        db.add(Tenant(id=_TENANT, name="FND-049 Test Tenant", slug="fnd-049-tenant"))
        db.add(User(id=_USER, tenant_id=_TENANT, email="fnd-049-test@example.com"))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(cli_module, "_session_factory", lambda: _Session)

    def _broken_discover(*_args, **_kwargs):
        raise RuntimeError("simulated bucket listing failure")

    monkeypatch.setattr(cli_module, "discover_object_keys", _broken_discover)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "ingest",
            "--source",
            str(tmp_path),
            "--tenant",
            str(_TENANT),
            "--window",
            "2026-01-01T00:00:00Z..2026-01-02T00:00:00Z",
        ],
    )

    assert result.exit_code != 0
    assert "failed to discover objects" in result.output
    assert "simulated bucket listing failure" in result.output
    assert "Traceback" not in result.output
