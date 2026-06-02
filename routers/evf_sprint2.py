"""
EVF Sprint 2 router — QCO Registry (FR-EVF-10) + Publication Audit (FR-EVF-20/21).

Prefix: /api/v1/evf

Endpoints added:
  POST   /qco                            — create draft QCO (gate must be locked)
  GET    /qco                            — list QCOs (filter: framework, active_only)
  GET    /qco/{qco_id}                   — get by UUID
  GET    /qco/by-ref/{ref}               — get by reference number
  PATCH  /qco/{qco_id}                   — update draft fields (immutable after publish)
  POST   /qco/{qco_id}/publish           — publish (locks record, emits audit event)
  POST   /qco/{qco_id}/renew             — create renewal draft from published QCO
  GET    /qco/{qco_id}/document          — get signed document URL (legal/admin only)
  POST   /publications                   — record an external publication event
  GET    /publications                   — list publication events (filter + paginate)
  GET    /publications/verify-chain      — verify hash-chain integrity of all events
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import EVFFramework, QCORegistry, QCOPublicationEvent
from services.evf_qco_service import (
    QCOImmutableError,
    create_qco_draft,
    get_qco,
    get_qco_by_ref,
    list_qcos,
    publish_qco,
    renew_qco,
    update_qco_draft,
)
from services.evf_publication_service import (
    list_publication_events,
    record_publication_event,
    verify_publication_chain,
)

router = APIRouter(prefix="/api/v1/evf", tags=["EVF"])

_VALID_FRAMEWORKS = {f.value for f in EVFFramework}
_VALID_CHANNELS = {"API", "REPORT_PDF", "DASHBOARD", "SALES_DECK", "WEBSITE", "PARTNER_PORTAL"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class QCOCreate(BaseModel):
    engagement_id: uuid.UUID
    framework_covered: str
    saro_version_assessed: str = Field(..., max_length=50)
    sme_firm: str = Field(..., min_length=1, max_length=255)
    sme_credential: Optional[str] = Field(None, max_length=255)
    scope_boundary_summary: Optional[str] = None
    document_url: Optional[str] = Field(None, max_length=2048)
    document_sha256: Optional[str] = Field(None, min_length=64, max_length=64)

    @field_validator("framework_covered")
    @classmethod
    def validate_framework(cls, v: str) -> str:
        if v not in _VALID_FRAMEWORKS:
            raise ValueError(f"framework_covered must be one of {sorted(_VALID_FRAMEWORKS)}")
        return v


class QCOPatch(BaseModel):
    saro_version_assessed: Optional[str] = Field(None, max_length=50)
    sme_firm: Optional[str] = Field(None, min_length=1, max_length=255)
    sme_credential: Optional[str] = Field(None, max_length=255)
    scope_boundary_summary: Optional[str] = None
    document_url: Optional[str] = Field(None, max_length=2048)
    document_sha256: Optional[str] = Field(None, min_length=64, max_length=64)


class QCOPublishRequest(BaseModel):
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None


class QCORenewRequest(BaseModel):
    saro_version_assessed: Optional[str] = Field(None, max_length=50)
    scope_boundary_summary: Optional[str] = None
    document_url: Optional[str] = Field(None, max_length=2048)
    document_sha256: Optional[str] = Field(None, min_length=64, max_length=64)


class PublicationEventCreate(BaseModel):
    qco_reference_number: str = Field(..., max_length=100)
    artefact_identifier: str = Field(..., min_length=1, max_length=500)
    distribution_channel: str

    @field_validator("distribution_channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        if v not in _VALID_CHANNELS:
            raise ValueError(f"distribution_channel must be one of {sorted(_VALID_CHANNELS)}")
        return v


class QCOOut(BaseModel):
    id: uuid.UUID
    qco_reference_number: str
    framework_covered: str
    saro_version_assessed: str
    sme_firm: str
    sme_credential: Optional[str]
    issue_date: Optional[date]
    expiry_date: Optional[date]
    scope_boundary_summary: Optional[str]
    document_sha256: Optional[str]
    engagement_id: Optional[uuid.UUID]
    published: bool
    published_at: Optional[datetime]
    record_hash: Optional[str]
    prev_hash: Optional[str]
    renews_qco_id: Optional[uuid.UUID]
    superseded_by_qco_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class QCODocumentOut(BaseModel):
    qco_reference_number: str
    document_url: Optional[str]
    document_sha256: Optional[str]


class PublicationEventOut(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    artefact_identifier: str
    qco_reference_number: str
    publisher_user_id: Optional[uuid.UUID]
    distribution_channel: str
    event_hash: Optional[str]
    prev_hash: Optional[str]

    model_config = {"from_attributes": True}


# ── QCO Registry endpoints ────────────────────────────────────────────────────


@router.post(
    "/qco",
    response_model=QCOOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Create a draft QCO — gate must be locked (FR-EVF-10)",
)
async def create_qco_endpoint(
    body: QCOCreate,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> QCOOut:
    qco = create_qco_draft(
        db,
        engagement_id=body.engagement_id,
        framework_covered=body.framework_covered,
        saro_version_assessed=body.saro_version_assessed,
        sme_firm=body.sme_firm,
        sme_credential=body.sme_credential,
        scope_boundary_summary=body.scope_boundary_summary,
        document_url=body.document_url,
        document_sha256=body.document_sha256,
        created_by_user_id=current_user.id,
    )
    return QCOOut.model_validate(qco)


@router.get(
    "/qco",
    response_model=list[QCOOut],
    dependencies=[Depends(get_current_user)],
    summary="List QCOs (FR-EVF-10)",
)
async def list_qcos_endpoint(
    framework: Optional[str] = Query(None),
    active_only: bool = Query(False, description="Return only published, non-expired, non-superseded QCOs"),
    db: Session = Depends(get_db),
) -> list[QCOOut]:
    if framework and framework not in _VALID_FRAMEWORKS:
        raise HTTPException(status_code=422, detail=f"framework must be one of {sorted(_VALID_FRAMEWORKS)}")
    return [QCOOut.model_validate(q) for q in list_qcos(db, framework=framework, active_only=active_only)]


@router.get(
    "/qco/by-ref/{ref}",
    response_model=QCOOut,
    dependencies=[Depends(get_current_user)],
    summary="Get QCO by reference number",
)
async def get_qco_by_ref_endpoint(ref: str, db: Session = Depends(get_db)) -> QCOOut:
    return QCOOut.model_validate(get_qco_by_ref(db, ref))


@router.get(
    "/qco/{qco_id}",
    response_model=QCOOut,
    dependencies=[Depends(get_current_user)],
    summary="Get QCO by UUID",
)
async def get_qco_endpoint(qco_id: uuid.UUID, db: Session = Depends(get_db)) -> QCOOut:
    return QCOOut.model_validate(get_qco(db, qco_id))


@router.patch(
    "/qco/{qco_id}",
    response_model=QCOOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Update draft QCO fields — 409 if already published (FR-EVF-10)",
)
async def patch_qco_endpoint(
    qco_id: uuid.UUID,
    body: QCOPatch,
    db: Session = Depends(get_db),
) -> QCOOut:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    qco = update_qco_draft(db, qco_id, updates=updates)
    return QCOOut.model_validate(qco)


@router.post(
    "/qco/{qco_id}/publish",
    response_model=QCOOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Publish QCO — immutable after this, emits publication event (FR-EVF-10, FR-EVF-21)",
)
async def publish_qco_endpoint(
    qco_id: uuid.UUID,
    body: QCOPublishRequest,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> QCOOut:
    qco = publish_qco(
        db,
        qco_id,
        published_by_user_id=current_user.id,
        issue_date=body.issue_date,
        expiry_date=body.expiry_date,
    )
    return QCOOut.model_validate(qco)


@router.post(
    "/qco/{qco_id}/renew",
    response_model=QCOOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Create renewal draft from a published QCO (FR-EVF-13)",
)
async def renew_qco_endpoint(
    qco_id: uuid.UUID,
    body: QCORenewRequest,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> QCOOut:
    renewal = renew_qco(
        db,
        qco_id,
        created_by_user_id=current_user.id,
        saro_version_assessed=body.saro_version_assessed,
        scope_boundary_summary=body.scope_boundary_summary,
        document_url=body.document_url,
        document_sha256=body.document_sha256,
    )
    return QCOOut.model_validate(renewal)


@router.get(
    "/qco/{qco_id}/document",
    response_model=QCODocumentOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Get document URL for a QCO — super_admin only (FR-EVF-22)",
)
async def get_qco_document_endpoint(
    qco_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> QCODocumentOut:
    qco = get_qco(db, qco_id)
    if not qco.published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document URL is only available for published QCOs.",
        )
    return QCODocumentOut(
        qco_reference_number=qco.qco_reference_number,
        document_url=qco.document_url,
        document_sha256=qco.document_sha256,
    )


# ── Publication audit endpoints ───────────────────────────────────────────────


@router.post(
    "/publications",
    response_model=PublicationEventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Record an external compliance claim publication event (FR-EVF-21)",
)
async def create_publication_event_endpoint(
    body: PublicationEventCreate,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Query(None, max_length=255),
) -> PublicationEventOut:
    event = record_publication_event(
        db,
        qco_reference_number=body.qco_reference_number,
        artefact_identifier=body.artefact_identifier,
        publisher_user_id=current_user.id,
        distribution_channel=body.distribution_channel,
        idempotency_key=idempotency_key,
    )
    return PublicationEventOut.model_validate(event)


@router.get(
    "/publications",
    response_model=list[PublicationEventOut],
    dependencies=[Depends(get_current_user)],
    summary="List publication events — filter by QCO ref or channel (FR-EVF-21)",
)
async def list_publications_endpoint(
    qco_ref: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[PublicationEventOut]:
    if channel and channel not in _VALID_CHANNELS:
        raise HTTPException(status_code=422, detail=f"channel must be one of {sorted(_VALID_CHANNELS)}")
    events = list_publication_events(
        db,
        qco_reference_number=qco_ref,
        distribution_channel=channel,
        limit=limit,
        offset=offset,
    )
    return [PublicationEventOut.model_validate(e) for e in events]


@router.get(
    "/publications/verify-chain",
    dependencies=[Depends(require_role("super_admin"))],
    summary="Verify SHA-256 hash-chain integrity of all publication events (FR-EVF-21 / AC-21b)",
)
async def verify_publication_chain_endpoint(
    db: Session = Depends(get_db),
) -> dict:
    return verify_publication_chain(db)
