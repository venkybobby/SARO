"""FND-048 — `saro demo reset` left AuditEvent/Notification rows behind.

STORY-410's `saro demo reset` originally deleted only Audit/Disposition/
ObservationCheckpoint/ObservationGap for the target tenant. Disposition actions
write AuditEvent rows via the self-audit spine (services/disposition_service.py),
and threshold/drift alerts write Notification rows — neither was cleared, so a
rehearsal that included a disposition/acknowledgment step would leave a stale
self-audit/notification trail behind after reset, violating AC-4.4 ("reset ->
re-ingest reproduces a first-run ingest"). Found by independent reviewer during
STORY-410's verify stage. Fix: `demo_reset`'s tenant-scoped delete set now
includes AuditEvent and Notification.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from click.testing import CliRunner  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import cli as cli_module  # noqa: E402
from database import Base  # noqa: E402
from models import AuditEvent, Notification, Tenant, User  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_DEMO_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000f8")
_DEMO_USER = uuid.UUID("00000000-0000-0000-0000-0000000000f9")


@pytest.mark.regression
def test_demo_reset_deletes_audit_event_and_notification_rows(monkeypatch):
    db = _Session()
    try:
        db.query(AuditEvent).delete()
        db.query(Notification).delete()
        db.query(User).delete()
        db.query(Tenant).delete()
        db.add(Tenant(id=_DEMO_TENANT, name="SARO Demo Tenant", slug="saro-demo"))
        db.add(
            User(
                id=_DEMO_USER,
                tenant_id=_DEMO_TENANT,
                email="fnd-048-test@example.com",
            )
        )
        db.add(
            AuditEvent(
                tenant_id=_DEMO_TENANT,
                user_id=_DEMO_USER,
                event_type="disposition_action",
                event_data={"seed": True},
            )
        )
        db.add(
            Notification(
                tenant_id=_DEMO_TENANT, type="system", title="seed", body="seed"
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(cli_module, "_session_factory", lambda: _Session)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli, ["demo", "reset", "--tenant", str(_DEMO_TENANT), "--yes"]
    )
    assert result.exit_code == 0, result.output

    db = _Session()
    try:
        assert db.query(AuditEvent).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        assert db.query(Notification).filter_by(tenant_id=_DEMO_TENANT).count() == 0
    finally:
        db.close()
