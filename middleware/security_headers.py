"""Security response headers (STORY-365 hardening pass).

Adds browser-hardening headers to every response. The API serves JSON, so the
CSP is deny-everything — EXCEPT on the interactive docs pages (/docs, /redoc),
which need Swagger/ReDoc's own scripts and styles; those two paths get a
relaxed CSP instead of none at all.

HSTS is emitted only when the request arrived over HTTPS (directly or via the
Fly edge's X-Forwarded-Proto) so local HTTP development doesn't pin browsers.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_API_CSP = "default-src 'none'; frame-ancestors 'none'"
_DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
)
_DOCS_PATHS = ("/docs", "/redoc")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

        path = request.url.path
        csp = _DOCS_CSP if any(path.startswith(p) for p in _DOCS_PATHS) else _API_CSP
        headers.setdefault("Content-Security-Policy", csp)

        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https":
            headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
