"""
CF-05: Governance Trust Page
=============================
GET /api/v1/governance/docs/nist-self-assessment   — serve NIST PDF
GET /api/v1/governance/docs/eu-ai-act-position     — serve EU AI Act PDF
GET /api/v1/governance/meta                         — document metadata for UI
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from auth import get_current_user, require_role
from models import User
from schemas import GovernanceDocMeta

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
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="CF-05 / SPEC-G4: Governance document metadata including SOC 2 status",
)
def get_governance_meta(
    _current: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return governance document metadata including SOC 2 readiness status (SPEC-G4)."""
    return {
        "nist": _NIST_META.model_dump(),
        "eu_ai_act": _EU_META.model_dump(),
        "soc2": {
            "status": "Readiness assessment in progress",
            "target_date": "2027-Q4",
            "roadmap_url": "/api/v1/governance/docs/soc2-roadmap",
            "current_readiness_pct": 65,
            "note": "SOC 2 Type II certification in progress. See roadmap for full timeline.",
        },
    }


# ── SPEC-G3 / SPEC-G4: DPA and SOC 2 roadmap endpoints ───────────────────────

_DPA_MD = _DOCS_DIR / "legal" / "saro-dpa-template-v1.0.md"
_SOC2_MD = _DOCS_DIR / "soc2-readiness-roadmap-v1.0.md"


@router.get(
    "/docs/dpa-template",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="SPEC-G3: Download GDPR Article 28 DPA template",
)
def get_dpa_template(
    _current: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Serve the DPA template markdown (SPEC-G3 FR-07)."""
    if not _DPA_MD.exists():
        raise HTTPException(
            status_code=404,
            detail="DPA template not yet available. Contact your SARO administrator.",
        )
    content = _DPA_MD.read_bytes()
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="saro-dpa-template-v1.0.md"'},
    )


@router.get(
    "/docs/soc2-roadmap",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="SPEC-G4: Download SOC 2 readiness roadmap",
)
def get_soc2_roadmap(
    _current: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Serve the SOC 2 readiness roadmap markdown (SPEC-G4 FR-07)."""
    if not _SOC2_MD.exists():
        raise HTTPException(
            status_code=404,
            detail="SOC 2 roadmap not yet available. Contact your SARO administrator.",
        )
    content = _SOC2_MD.read_bytes()
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="saro-soc2-readiness-roadmap-v1.0.md"'},
    )
