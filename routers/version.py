"""Version endpoint (STORY-375).

Public and unauthenticated: a customer's own change-management process needs to
read which SARO version is running without holding a credential. It exposes the
SemVer plus the build commit (from the ``SARO_GIT_SHA`` env var the deploy
pipeline sets) — enough to answer "what is deployed right now", nothing more.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from _version import __version__

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/version", summary="Running SARO version (public)")
def version() -> dict:
    return {
        "version": __version__,
        # Set by the release pipeline; "unknown" in local/dev where it is unset.
        "commit": os.environ.get("SARO_GIT_SHA", "unknown"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
    }
