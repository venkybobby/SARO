"""FND-010 (PT-009): LIKE wildcard injection in risks.py risk-id prefix lookup.

Root cause: ``_find_audit_with_meta`` stripped ``R-`` and passed user input into
``cast(Audit.id, String).like(f"{prefix}%")`` unescaped — ``%``/``_`` matched
arbitrary same-tenant audits nondeterministically on read/PATCH/DELETE paths.
Fixed by validating the stripped prefix is hex (``_HEX_PREFIX``) like insights.
"""
from unittest.mock import MagicMock

import pytest

from routers.risks import _HEX_PREFIX, _find_audit_with_meta

pytestmark = pytest.mark.regression


@pytest.mark.parametrize("evil", ["%", "_", "a%", "a_b", "R-%", "R-_", "ZZZ", "1; DROP"])
def test_wildcard_prefix_rejected_before_query(evil):
    db = MagicMock()
    assert _find_audit_with_meta(db, "tenant", evil) is None
    # Crucially: rejected BEFORE building any LIKE query.
    db.query.assert_not_called()


@pytest.mark.parametrize("ok", ["R-abc123", "deadbeef", "0a1b2c"])
def test_valid_hex_prefix_builds_query(ok):
    db = MagicMock()
    q = db.query.return_value
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.first.return_value = None
    assert _find_audit_with_meta(db, "tenant", ok) is None
    db.query.assert_called_once()


def test_hex_regex_rejects_wildcards():
    assert _HEX_PREFIX.fullmatch("abc123")
    assert not _HEX_PREFIX.fullmatch("a%")
    assert not _HEX_PREFIX.fullmatch("a_")
    assert not _HEX_PREFIX.fullmatch("")
