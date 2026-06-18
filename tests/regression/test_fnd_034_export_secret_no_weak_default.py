"""FND-034: signed evidence exports must not fall back to a guessable HMAC secret.

`routers/trace_view.py`, `routers/trace_export.py` and `routers/risk_dashboard.py`
previously resolved their export-signing secret as::

    os.environ.get("SARO_EXPORT_SECRET", "saro-default-export-secret")

i.e. a publicly-known literal default. If the secret was unset in an environment,
every signed TRACE/risk export was HMAC-signed with that known key, so anyone could
forge a valid ``_signature`` / ``export_hash`` on an evidence pack — defeating the
tamper-evidence the artifact claims to provide.

Fix: signing resolves through ``config.require_export_secret``, which fails closed
(raises) when the secret is unset instead of using a default. This test pins both:

  1. ``require_export_secret`` raises in a production-like config (secret unset),
     and never returns a guessable literal.
  2. The router source no longer contains a hardcoded fallback secret literal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config import require_export_secret

pytestmark = [pytest.mark.regression, pytest.mark.unit]

_ROUTERS = Path(__file__).resolve().parents[2] / "routers"

# The exact weak literals that used to ship as defaults. None may reappear.
_FORBIDDEN_LITERALS = (
    "saro-default-export-secret",
    "saro-default-hmac-secret-change-in-prod",
)


def test_require_export_secret_fails_closed_when_unset():
    """Unset secret (production-like) must raise, not return a default."""
    with pytest.raises(RuntimeError) as exc:
        require_export_secret(None, env_var="SARO_EXPORT_SECRET")
    # The error names the env var so operators know what to set.
    assert "SARO_EXPORT_SECRET" in str(exc.value)

    with pytest.raises(RuntimeError):
        require_export_secret("", env_var="EXPORT_HMAC_SECRET")


def test_require_export_secret_returns_configured_value():
    """A configured secret is returned verbatim (and is never a guessable literal)."""
    secret = require_export_secret("a-real-injected-secret", env_var="SARO_EXPORT_SECRET")
    assert secret == "a-real-injected-secret"
    assert secret not in _FORBIDDEN_LITERALS


def test_no_router_ships_a_hardcoded_default_secret():
    """No router (current or future) may ship a guessable fallback secret literal.

    Globbed rather than hardcoded so a *new* export-signing router that
    reintroduces the pattern is caught too (security-auditor Finding 2).
    """
    offenders = []
    for path in _ROUTERS.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for literal in _FORBIDDEN_LITERALS:
            if literal in source:
                offenders.append(f"{path.name} -> {literal!r}")
    assert not offenders, (
        "router(s) reintroduced a guessable default export secret: "
        f"{offenders}; signing must fail closed via config.require_export_secret instead."
    )
