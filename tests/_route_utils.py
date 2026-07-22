"""Version-robust route enumeration for tests (FND-069).

Starlette differs across versions in how included-router routes appear in
``app.routes``: some versions FLATTEN them into the top level as ``APIRoute``
objects, others NEST them inside path-less sub-router objects. A test that
iterates ``app.routes`` and filters ``isinstance(r, APIRoute)`` at the top
level therefore sees *every* route on a flattening version but only the app's
own ``@app.get`` routes (``/`` and ``/health``) on a nesting version.

That is exactly how FND-069 hid: four route-registration tests passed on the
locally-pinned Starlette (flattening) and failed in CI (fresh install of an
unpinned ``fastapi>=0.111.0`` → a nesting Starlette), reporting the full app as
a two-route app. ``test_sar010_controls`` had already dodged this by reading
``app.openapi()``, but the OpenAPI schema omits ``include_in_schema=False``
routes (e.g. ``/metrics``), so recursion over ``app.routes`` is the general
fix. Always enumerate routes through this helper, never a top-level filter.
"""

from __future__ import annotations

from fastapi.routing import APIRoute


def iter_api_routes(app) -> list[APIRoute]:
    """Every ``APIRoute`` in ``app``, recursing through nested sub-routers.

    Correct under both the flattening and nesting Starlette behaviors.
    """
    found: list[APIRoute] = []

    def _walk(routes) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                found.append(route)
            sub = getattr(route, "routes", None)
            # An APIRoute has no ``.routes``; a Mount/sub-router does.
            if sub and not isinstance(route, APIRoute):
                _walk(sub)

    _walk(app.routes)
    return found


def method_path_pairs(app, *, drop: frozenset[str] = frozenset({"HEAD", "OPTIONS"})):
    """``{(METHOD, path)}`` across all registered API routes (recursively)."""
    return {
        (method, route.path)
        for route in iter_api_routes(app)
        for method in ((route.methods or set()) - drop)
    }
