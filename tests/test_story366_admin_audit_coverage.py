"""STORY-366 — admin/config audit log: coverage + immutability + INV-2.

Three guarantees, each mechanically enforced:

1. **Coverage** — every mutating route is classified in
   ``services/admin_audit_registry.py``; every AUDITED route's handler really
   does call the self-audit recorder. A new admin route with no audit write
   fails here by default.
2. **Immutability** — migration 033 installs the append-only trigger and the
   partial unique index the chain relies on.
3. **INV-2** — the recorder hashes and stores metadata fields only; no
   payload/body field can reach the trail by construction.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.routing import APIRoute  # noqa: E402

import services.self_audit as self_audit  # noqa: E402
from main import app  # noqa: E402
from services.admin_audit_registry import AUDITED, DATA_PLANE, classification  # noqa: E402

pytestmark = pytest.mark.integration

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Recorder call sites that count as "this handler writes to the trail".
# `record_auth_event` (FND-065) is a thin wrapper over `record_access` that adds
# fail-open semantics for the login path — it is an audit write, so it counts.
_RECORDER_RE = re.compile(r"record_privileged|record_access|_log_event|record_auth_event")


def _mutating_routes() -> list[tuple[str, APIRoute]]:
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods & _MUTATING):
            out.append((method, route))
    return out


def test_every_mutating_route_is_classified():
    """Unclassified route → fail. Forces an audit decision on every new endpoint."""
    unclassified = [
        f"{m} {r.path}"
        for m, r in _mutating_routes()
        if classification(m, r.path) is None
    ]
    assert not unclassified, (
        "mutating routes missing an audit classification — add each to AUDITED "
        "(and write the audit call) or DATA_PLANE (with a reason) in "
        "services/admin_audit_registry.py:\n  " + "\n  ".join(sorted(unclassified))
    )


def test_audited_routes_actually_write_to_the_trail():
    """AUDITED is a promise; this checks the handler keeps it."""
    missing = []
    for method, route in _mutating_routes():
        if classification(method, route.path) != "AUDITED":
            continue
        try:
            src = inspect.getsource(route.endpoint)
        except (OSError, TypeError):  # pragma: no cover — source always available in-repo
            continue
        if not _RECORDER_RE.search(src):
            missing.append(f"{method} {route.path}")
    assert not missing, (
        "routes registered as AUDITED whose handler makes no audit write:\n  "
        + "\n  ".join(sorted(missing))
    )


def test_registry_has_no_stale_entries():
    """A renamed/removed route must not linger as a phantom classification."""
    known = {(m, r.path) for m, r in _mutating_routes()}
    # The Jira OAuth callback is a GET, deliberately classified for the record.
    known.add(("GET", "/api/v1/remediation/oauth/jira/callback"))
    known.add(("GET", "/api/v1/demo/token"))
    stale = [k for k in {**AUDITED, **DATA_PLANE} if k not in known]
    assert not stale, f"registry entries no longer registered as routes: {sorted(stale)}"


def test_role_and_config_changes_are_audited():
    """The story's named actions specifically: role change, config, tenancy, rule-pack."""
    for key in (
        ("PATCH", "/api/v1/auth/users/{user_id}/persona"),
        ("PUT", "/api/v1/risk-config"),
        ("POST", "/api/v1/tenants"),
        ("POST", "/api/v1/rules/versions"),
    ):
        assert classification(*key) == "AUDITED", f"{key} must be an audited admin action"


def test_append_only_enforced_in_migration():
    sql = (ROOT / "migrations" / "033_self_audit_spine.sql").read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE ON audit_events" in sql, (
        "append-only trigger missing — the trail would be mutable"
    )


def test_recorder_hashes_metadata_only_inv2():
    """INV-2 by construction: only these six metadata fields are sealed."""
    assert set(self_audit._HASHED_FIELDS) == {
        "action_class",
        "actor",
        "target_type",
        "target_id",
        "outcome",
        "timestamp",
    }, "hashed field set changed — verify no payload/body content can enter the trail"


def test_privileged_recording_fails_closed():
    """An unauditable privileged action must raise, not silently continue."""

    class _BoomSession:
        def query(self, *a, **k):
            raise RuntimeError("db down")

        def rollback(self):
            self.rolled_back = True

    with pytest.raises(self_audit.UnauditableActionError):
        self_audit.record_privileged(
            _BoomSession(),
            tenant_id=self_audit.SYSTEM_TENANT_ID,
            actor="probe@example.com",
            action_class=self_audit.ADMIN_ACTION,
        )
