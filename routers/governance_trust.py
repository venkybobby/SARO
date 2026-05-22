"""
CF-05: Governance Trust Page
=============================
GET /api/v1/governance/docs/nist-self-assessment   — serve NIST PDF
GET /api/v1/governance/docs/eu-ai-act-position     — serve EU AI Act PDF
GET /api/v1/governance/meta                         — document metadata for UI
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from auth import get_current_user, require_role
from models import User
from schemas import GovernanceDocMeta, GovernanceMetaOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/governance", tags=["governance-trust"])

_DOCS_DIR = Path(__file__).parent.parent / "docs"

_NIST_PDF = _DOCS_DIR / "saro-nist-ai-rmf-self-assessment-v1.0.pdf"
_EU_PDF = _DOCS_DIR / "saro-eu-ai-act-position-v1.0.pdf"

# Metadata (updated manually when documents are revised)
_NIST_META = GovernanceDocMeta(
    version="1.0.0",
    reviewed_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
    reviewer="Venky (Lead Engineer) & Jordan Lee (Backend/Infra)",
)
_EU_META = GovernanceDocMeta(
    version="1.0.0",
    reviewed_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
    reviewer="Venky (Lead Engineer)",
)


def _serve_pdf(path: Path, filename: str) -> Response:
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Governance document not yet available: {filename}. Contact your SARO administrator.",
        )
    content = path.read_bytes()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/docs/nist-self-assessment",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-05: Download SARO NIST AI RMF 1.0 self-assessment PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_nist_self_assessment(
    _current: Annotated[User, Depends(get_current_user)],
) -> Response:
    return _serve_pdf(_NIST_PDF, "saro-nist-ai-rmf-self-assessment-v1.0.pdf")


@router.get(
    "/docs/eu-ai-act-position",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-05: Download SARO EU AI Act position statement PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_eu_ai_act_position(
    _current: Annotated[User, Depends(get_current_user)],
) -> Response:
    return _serve_pdf(_EU_PDF, "saro-eu-ai-act-position-v1.0.pdf")


@router.get(
    "/meta",
    response_model=GovernanceMetaOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-05: Governance document metadata for UI rendering",
)
def get_governance_meta(
    _current: Annotated[User, Depends(get_current_user)],
) -> GovernanceMetaOut:
    return GovernanceMetaOut(nist=_NIST_META, eu_ai_act=_EU_META)
