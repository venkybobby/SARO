"""FND-016: FastAPI dependency_overrides must not leak across tests.

A leaked override (authenticated get_current_user, or a removed get_db) caused
unrelated auth tests to fail or hit the real DB depending on collection order.
The root conftest autouse fixture snapshots+restores the override map per test.
These two tests run in definition order: the first dirties the map, the second
asserts it was restored — proving leakage is contained.
"""
import pytest

from main import app

pytestmark = pytest.mark.regression

_SENTINEL = object()


def _marker():
    return _SENTINEL


def test_a_dirties_dependency_overrides():
    app.dependency_overrides[_marker] = lambda: "leaked"
    assert _marker in app.dependency_overrides


def test_b_sees_clean_dependency_overrides():
    assert _marker not in app.dependency_overrides, (
        "dependency_overrides leaked from a previous test — FND-016 isolation broken"
    )
