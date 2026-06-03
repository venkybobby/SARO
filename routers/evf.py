"""
EVF Sprint 1 router — SME Engagement (FR-EVF-05) + Validation Gate (FR-EVF-08).

All endpoints require authentication. Write endpoints additionally require
super_admin role (Product Owner, Legal, Sales Leadership use super_admin in
the current two-role model; persona_role differentiation is Sprint 2 scope).

Prefix: /api/v1/evf
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import SMEEngagementState, EVFFramework, ValidationGate
from services.evf_engagement_service import (
    create_engagement,
    get_engagement,
    list_engagements,
    list_transitions,
    transition_engagement,
)
from services.evf_gate_service import GATE_ITEMS, get_gate, lock_gate, update_gate

router = APIRouter(prefix="/api/v1/evf", tags=["EVF"])

_VALID_FRAMEWORKS = {f.value for f in EVFFramework}
_VALID_STATES = {s.value for s in SMEEngagementState}


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class EngagementCreate(BaseModel):
    sme_firm_name: str = Field(..., min_length=1, max_length=255)
    framework: str = Field(..., description="One of: EU_AI_ACT, NIST_AI_RMF, AIGP, ISO_42001")
    sme_key_contact: Optional[str] = Field(None, max_length=255)
    sme_credential: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None

    @field_validator("framework")
    @classmethod
    def validate_framework(cls, v: str) -> str:
        if v not in _VALID_FRAMEWORKS:
            raise ValueError(f"framework must be one of {sorted(_VALID_FRAMEWORKS)}")
        return v


class TransitionRequest(BaseModel):
    to_state: str = Field(..., description="Target state")
    reason: Optional[str] = Field(None, max_length=1000)

    @field_validator("to_state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if v not in _VALID_STATES:
            raise ValueError(f"to_state must be one of {sorted(_VALID_STATES)}")
        return v


class GatePatch(BaseModel):
    coi_declared_approved: Optional[bool] = None
    coi_evidence_ref: Optional[str] = Field(None, max_length=500)
    sow_executed: Optional[bool] = None
    sow_evidence_ref: Optional[str] = Field(None, max_length=500)
    evidence_package_delivered: Optional[bool] = None
    evidence_package_ref: Optional[str] = Field(None, max_length=500)
    product_demo_completed: Optional[bool] = None
    product_demo_ref: Optional[str] = Field(None, max_length=500)
    draft_qco_received: Optional[bool] = None
    draft_qco_ref: Optional[str] = Field(None, max_length=500)
    saro_legal_review_completed: Optional[bool] = None
    legal_signoff_ref: Optional[str] = Field(None, max_length=500)
    qco_approved_ref_assigned: Optional[bool] = None
    qco_ref: Optional[str] = Field(None, max_length=100)


class EngagementOut(BaseModel):
    id: uuid.UUID
    sme_firm_name: str
    sme_key_contact: Optional[str]
    sme_credential: Optional[str]
    framework: str
    state: str
    state_entered_at: datetime
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TransitionOut(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    from_state: str
    to_state: str
    actor_user_id: Optional[uuid.UUID]
    reason: Optional[str]
    event_hash: Optional[str]
    prev_hash: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class GateOut(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    coi_declared_approved: bool
    coi_evidence_ref: Optional[str]
    sow_executed: bool
    sow_evidence_ref: Optional[str]
    evidence_package_delivered: bool
    evidence_package_ref: Optional[str]
    product_demo_completed: bool
    product_demo_ref: Optional[str]
    draft_qco_received: bool
    draft_qco_ref: Optional[str]
    saro_legal_review_completed: bool
    legal_signoff_ref: Optional[str]
    qco_approved_ref_assigned: bool
    qco_ref: Optional[str]
    locked: bool
    locked_at: Optional[datetime]
    all_passed: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_computed(cls, gate: ValidationGate) -> "GateOut":
        data = {c.name: getattr(gate, c.name) for c in gate.__table__.columns}
        data["all_passed"] = all(getattr(gate, item) for item in GATE_ITEMS)
        return cls(**data)


# ── Engagement endpoints ──────────────────────────────────────────────────────


@router.post(
    "/engagements",
    response_model=EngagementOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Create a new SME engagement (FR-EVF-05)",
)
async def create_engagement_endpoint(
    body: EngagementCreate,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EngagementOut:
    eng = create_engagement(
        db,
        sme_firm_name=body.sme_firm_name,
        framework=body.framework,
        created_by_user_id=current_user.id,
        sme_key_contact=body.sme_key_contact,
        sme_credential=body.sme_credential,
        notes=body.notes,
    )
    return EngagementOut.model_validate(eng)


@router.get(
    "/engagements",
    response_model=list[EngagementOut],
    dependencies=[Depends(get_current_user)],
    summary="List SME engagements (FR-EVF-05)",
)
async def list_engagements_endpoint(
    framework: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[EngagementOut]:
    if framework and framework not in _VALID_FRAMEWORKS:
        raise HTTPException(status_code=422, detail=f"framework must be one of {sorted(_VALID_FRAMEWORKS)}")
    if state and state not in _VALID_STATES:
        raise HTTPException(status_code=422, detail=f"state must be one of {sorted(_VALID_STATES)}")
    return [EngagementOut.model_validate(e) for e in list_engagements(db, framework=framework, state=state)]


@router.get(
    "/engagements/{engagement_id}",
    response_model=EngagementOut,
    dependencies=[Depends(get_current_user)],
    summary="Get a single SME engagement",
)
async def get_engagement_endpoint(
    engagement_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EngagementOut:
    return EngagementOut.model_validate(get_engagement(db, engagement_id))


@router.post(
    "/engagements/{engagement_id}/transition",
    response_model=EngagementOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Advance engagement state (FR-EVF-05)",
)
async def transition_endpoint(
    engagement_id: uuid.UUID,
    body: TransitionRequest,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> EngagementOut:
    eng = transition_engagement(
        db,
        engagement_id,
        to_state=body.to_state,
        actor_user_id=current_user.id,
        reason=body.reason,
    )
    return EngagementOut.model_validate(eng)


@router.get(
    "/engagements/{engagement_id}/transitions",
    response_model=list[TransitionOut],
    dependencies=[Depends(get_current_user)],
    summary="Get hash-chained transition history for an engagement",
)
async def list_transitions_endpoint(
    engagement_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[TransitionOut]:
    return [TransitionOut.model_validate(t) for t in list_transitions(db, engagement_id)]


# ── Gate endpoints ────────────────────────────────────────────────────────────


@router.get(
    "/engagements/{engagement_id}/gate",
    response_model=GateOut,
    dependencies=[Depends(get_current_user)],
    summary="Get validation gate status for an engagement (FR-EVF-08)",
)
async def get_gate_endpoint(
    engagement_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> GateOut:
    gate = get_gate(db, engagement_id)
    return GateOut.from_orm_with_computed(gate)


@router.patch(
    "/engagements/{engagement_id}/gate",
    response_model=GateOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Update validation gate items with evidence (FR-EVF-08)",
)
async def patch_gate_endpoint(
    engagement_id: uuid.UUID,
    body: GatePatch,
    db: Session = Depends(get_db),
) -> GateOut:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    gate = update_gate(db, engagement_id, updates=updates)
    return GateOut.from_orm_with_computed(gate)


@router.post(
    "/engagements/{engagement_id}/gate/lock",
    response_model=GateOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Lock the validation gate when all 7 items are complete (FR-EVF-08)",
)
async def lock_gate_endpoint(
    engagement_id: uuid.UUID,
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> GateOut:
    gate = lock_gate(db, engagement_id, locked_by_user_id=current_user.id)
    return GateOut.from_orm_with_computed(gate)
