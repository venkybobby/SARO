"""FND-069 — route enumeration in tests must recurse into nested sub-routers.

Root cause: Starlette differs by version in how included-router routes appear
in ``app.routes`` — flattened as top-level ``APIRoute`` objects, or nested
inside a path-less sub-router. Four route-registration tests iterated
``app.routes`` with a top-level ``isinstance(r, APIRoute)`` filter, so they
passed on the locally-pinned Starlette (flattening) and failed in CI (fresh
install of unpinned ``fastapi>=0.111.0`` → nesting), which reported the whole
app as a two-route (``/`` + ``/health``) app.

This pins the fix deterministically: an app whose only API route lives inside a
NESTED sub-router (the shape CI produced). The shared ``iter_api_routes`` helper
must find it; the naive top-level filter must not (that miss is the bug).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fastapi import FastAPI  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from starlette.routing import Mount  # noqa: E402

from _route_utils import iter_api_routes, method_path_pairs  # noqa: E402

pytestmark = pytest.mark.regression


def _app_with_nested_router() -> FastAPI:
    inner = FastAPI()

    @inner.get("/api/v1/deep-thing")
    def _deep():  # pragma: no cover - never invoked
        return {}

    app = FastAPI()

    @app.get("/health")
    def _health():  # pragma: no cover - never invoked
        return {}

    # Nest, don't flatten: the included routes live inside a sub-router object.
    app.router.routes.append(Mount("/mnt", app=inner))
    return app


def test_naive_top_level_filter_misses_nested_routes():
    """The original failure mode: a top-level filter sees only /health."""
    app = _app_with_nested_router()
    top_level = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/deep-thing" not in top_level
    assert "/health" in top_level


def test_iter_api_routes_recurses_into_nested_routers():
    app = _app_with_nested_router()
    paths = {r.path for r in iter_api_routes(app)}
    assert "/api/v1/deep-thing" in paths, "helper must recurse into nested routers"
    assert "/health" in paths


def test_method_path_pairs_includes_nested_routes():
    app = _app_with_nested_router()
    pairs = method_path_pairs(app, drop=frozenset())
    assert ("GET", "/api/v1/deep-thing") in pairs
    assert ("GET", "/health") in pairs


def test_helper_works_on_the_real_app():
    """Against the real app, the helper finds far more than the 2 top-level
    routes — the concrete regression guard for the four repaired tests."""
    import main

    routes = iter_api_routes(main.app)
    paths = {r.path for r in routes}
    assert len(routes) > 50
    assert "/api/v1/feedback" in paths
    assert "/metrics" in paths
