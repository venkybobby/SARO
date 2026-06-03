"""
EVF Sprint 1 tests — FR-EVF-05 (SME Engagement) + FR-EVF-08 (Validation Gate).

All tests use in-memory SQLite so no live DB is required.
Covers:
  - Valid forward transitions accepted
  - Illegal (skip/backward) transitions rejected with 409
  - RENEWAL_TRIGGERED reachable from any state
  - Transition writes a hash-chained row; chain is verifiable
  - Gate PATCH accepted on unlocked gate
  - Gate locked only when all 7 items are True
  - Locked gate rejects PATCH (409)
  - Lock rejected if any item is still False
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for unit tests — no live Supabase required
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

# Patch PostgreSQL-specific UUID type before model import
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import sqlalchemy.types as sa_types

_orig_uuid_init = PG_UUID.__init__
def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)
PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]

# Patch JSON dialect type to Text for SQLite
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]

from database import Base

from models import (
    EVFFramework, SMEEngagementState, SMEEngagement,
)
Base.metadata.create_all(engine)  # create tables after all models are registered

from services.evf_engagement_service import (
    create_engagement, list_transitions, transition_engagement,
    _allowed_transitions, _compute_transition_hash,
)
from services.evf_gate_service import (
    GATE_ITEMS, get_gate, update_gate, lock_gate, gate_is_locked,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _session():
    return next(_db())


ACTOR = uuid.uuid4()


def _make_engagement(db, framework: str = "EU_AI_ACT") -> SMEEngagement:
    return create_engagement(
        db,
        sme_firm_name="Acme Legal LLP",
        framework=framework,
        created_by_user_id=ACTOR,
        sme_key_contact="Jane Smith",
        sme_credential="CIPP/E",
    )


# ── FR-EVF-05: State Machine Tests ───────────────────────────────────────────

class TestAllowedTransitions:
    def test_forward_chain_is_complete(self):
        forward_states = [
            SMEEngagementState.SHORTLISTED,
            SMEEngagementState.COI_CLEARED,
            SMEEngagementState.SOW_ISSUED,
            SMEEngagementState.REVIEW_IN_PROGRESS,
            SMEEngagementState.DRAFT_QCO_RECEIVED,
            SMEEngagementState.QCO_APPROVED,
            SMEEngagementState.PUBLISHED,
        ]
        for i, s in enumerate(forward_states[:-1]):
            allowed = _allowed_transitions(s)
            assert forward_states[i + 1] in allowed, f"{s} should allow {forward_states[i+1]}"

    def test_renewal_reachable_from_any_non_terminal_state(self):
        for s in SMEEngagementState:
            if s is SMEEngagementState.RENEWAL_TRIGGERED:
                continue
            assert SMEEngagementState.RENEWAL_TRIGGERED in _allowed_transitions(s)

    def test_renewal_triggered_has_no_forward(self):
        allowed = _allowed_transitions(SMEEngagementState.RENEWAL_TRIGGERED)
        assert len(allowed) == 0


class TestCreateEngagement:
    def test_create_sets_shortlisted_state(self):
        db = _session()
        eng = _make_engagement(db)
        assert eng.state == SMEEngagementState.SHORTLISTED.value
        db.close()

    def test_create_writes_genesis_transition(self):
        db = _session()
        eng = _make_engagement(db)
        transitions = list_transitions(db, eng.id)
        assert len(transitions) == 1
        assert transitions[0].from_state == "GENESIS"
        assert transitions[0].to_state == SMEEngagementState.SHORTLISTED.value
        db.close()

    def test_create_initialises_gate(self):
        db = _session()
        eng = _make_engagement(db)
        gate = get_gate(db, eng.id)
        assert gate is not None
        assert gate.locked is False
        db.close()

    def test_all_frameworks_accepted(self):
        db = _session()
        for fw in EVFFramework:
            eng = _make_engagement(db, framework=fw.value)
            assert eng.framework == fw.value
        db.close()


class TestTransitions:
    def test_valid_forward_transition(self):
        db = _session()
        eng = _make_engagement(db)
        updated = transition_engagement(db, eng.id, to_state="COI_CLEARED", actor_user_id=ACTOR)
        assert updated.state == "COI_CLEARED"
        db.close()

    def test_invalid_skip_transition_raises_409(self):
        import fastapi
        db = _session()
        eng = _make_engagement(db)
        try:
            transition_engagement(db, eng.id, to_state="SOW_ISSUED", actor_user_id=ACTOR)
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 409
        db.close()

    def test_backward_transition_raises_409(self):
        import fastapi
        db = _session()
        eng = _make_engagement(db)
        transition_engagement(db, eng.id, to_state="COI_CLEARED", actor_user_id=ACTOR)
        try:
            transition_engagement(db, eng.id, to_state="SHORTLISTED", actor_user_id=ACTOR)
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 409
        db.close()

    def test_renewal_from_intermediate_state(self):
        db = _session()
        eng = _make_engagement(db)
        transition_engagement(db, eng.id, to_state="COI_CLEARED", actor_user_id=ACTOR)
        updated = transition_engagement(db, eng.id, to_state="RENEWAL_TRIGGERED", actor_user_id=ACTOR)
        assert updated.state == "RENEWAL_TRIGGERED"
        db.close()

    def test_transition_writes_new_row(self):
        db = _session()
        eng = _make_engagement(db)
        transition_engagement(db, eng.id, to_state="COI_CLEARED", actor_user_id=ACTOR)
        transitions = list_transitions(db, eng.id)
        assert len(transitions) == 2  # genesis + COI_CLEARED
        assert transitions[-1].to_state == "COI_CLEARED"
        db.close()


class TestTransitionHashChain:
    def test_genesis_prev_hash_is_none(self):
        db = _session()
        eng = _make_engagement(db)
        transitions = list_transitions(db, eng.id)
        assert transitions[0].prev_hash is None
        db.close()

    def test_second_transition_prev_hash_equals_first_event_hash(self):
        db = _session()
        eng = _make_engagement(db)
        transition_engagement(db, eng.id, to_state="COI_CLEARED", actor_user_id=ACTOR)
        transitions = list_transitions(db, eng.id)
        assert transitions[1].prev_hash == transitions[0].event_hash
        db.close()

    def test_hash_is_reproducible(self):
        from datetime import timezone as _tz
        db = _session()
        eng = _make_engagement(db)
        transitions = list_transitions(db, eng.id)
        t = transitions[0]
        # Normalise created_at the same way the service does (UTC-aware ISO string)
        dt = t.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        payload = {
            "id": str(t.id),
            "engagement_id": str(t.engagement_id),
            "from_state": t.from_state,
            "to_state": t.to_state,
            "actor_user_id": str(t.actor_user_id) if t.actor_user_id else "",
            "reason": t.reason or "",
            "created_at": dt.astimezone(_tz.utc).isoformat(),
        }
        recomputed = _compute_transition_hash(payload, t.prev_hash)
        assert recomputed == t.event_hash
        db.close()

    def test_tampered_hash_detected(self):
        db = _session()
        eng = _make_engagement(db)
        transition_engagement(db, eng.id, to_state="COI_CLEARED", actor_user_id=ACTOR)
        transitions = list_transitions(db, eng.id)
        # Simulate tampering: recompute second hash with a modified prev_hash
        _t1, t2 = transitions[0], transitions[1]
        tampered_prev = "0" * 64
        payload = {
            "id": str(t2.id),
            "engagement_id": str(t2.engagement_id),
            "from_state": t2.from_state,
            "to_state": t2.to_state,
            "actor_user_id": str(t2.actor_user_id) if t2.actor_user_id else "",
            "reason": t2.reason or "",
            "created_at": t2.created_at.isoformat(),
        }
        recomputed = _compute_transition_hash(payload, tampered_prev)
        assert recomputed != t2.event_hash  # chain is broken
        db.close()


# ── FR-EVF-08: Validation Gate Tests ─────────────────────────────────────────

class TestValidationGate:
    def _full_patch(self) -> dict:
        return {
            "coi_declared_approved": True,
            "coi_evidence_ref": "COI-2026-001",
            "sow_executed": True,
            "sow_evidence_ref": "SOW-2026-001",
            "evidence_package_delivered": True,
            "evidence_package_ref": "EP-2026-001",
            "product_demo_completed": True,
            "product_demo_ref": "DEMO-2026-001",
            "draft_qco_received": True,
            "draft_qco_ref": "DQCO-2026-001",
            "saro_legal_review_completed": True,
            "legal_signoff_ref": "LEGAL-2026-001",
            "qco_approved_ref_assigned": True,
            "qco_ref": "SARO-QCO-EU_AI_ACT-2026-001",
        }

    def test_initial_gate_all_false(self):
        db = _session()
        eng = _make_engagement(db)
        gate = get_gate(db, eng.id)
        for item in GATE_ITEMS:
            assert getattr(gate, item) is False
        db.close()

    def test_patch_single_item(self):
        db = _session()
        eng = _make_engagement(db)
        gate = update_gate(db, eng.id, updates={"coi_declared_approved": True, "coi_evidence_ref": "ref-001"})
        assert gate.coi_declared_approved is True
        assert gate.coi_evidence_ref == "ref-001"
        db.close()

    def test_all_items_false_means_not_all_passed(self):
        db = _session()
        eng = _make_engagement(db)
        gate = get_gate(db, eng.id)
        all_passed = all(getattr(gate, item) for item in GATE_ITEMS)
        assert all_passed is False
        db.close()

    def test_all_items_true_means_all_passed(self):
        db = _session()
        eng = _make_engagement(db)
        update_gate(db, eng.id, updates=self._full_patch())
        gate = get_gate(db, eng.id)
        all_passed = all(getattr(gate, item) for item in GATE_ITEMS)
        assert all_passed is True
        db.close()

    def test_lock_requires_all_7_items(self):
        import fastapi
        db = _session()
        eng = _make_engagement(db)
        # Only 6 of 7 items set
        patch = self._full_patch()
        patch.pop("qco_approved_ref_assigned")
        update_gate(db, eng.id, updates=patch)
        try:
            lock_gate(db, eng.id, locked_by_user_id=ACTOR)
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 422
            assert "qco_approved_ref_assigned" in exc.detail
        db.close()

    def test_lock_succeeds_when_all_7_true(self):
        db = _session()
        eng = _make_engagement(db)
        update_gate(db, eng.id, updates=self._full_patch())
        gate = lock_gate(db, eng.id, locked_by_user_id=ACTOR)
        assert gate.locked is True
        assert gate.locked_at is not None
        db.close()

    def test_locked_gate_rejects_patch(self):
        import fastapi
        db = _session()
        eng = _make_engagement(db)
        update_gate(db, eng.id, updates=self._full_patch())
        lock_gate(db, eng.id, locked_by_user_id=ACTOR)
        try:
            update_gate(db, eng.id, updates={"coi_declared_approved": False})
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 409
        db.close()

    def test_double_lock_raises_409(self):
        import fastapi
        db = _session()
        eng = _make_engagement(db)
        update_gate(db, eng.id, updates=self._full_patch())
        lock_gate(db, eng.id, locked_by_user_id=ACTOR)
        try:
            lock_gate(db, eng.id, locked_by_user_id=ACTOR)
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 409
        db.close()

    def test_gate_is_locked_utility(self):
        db = _session()
        eng = _make_engagement(db)
        assert gate_is_locked(db, eng.id) is False
        update_gate(db, eng.id, updates=self._full_patch())
        lock_gate(db, eng.id, locked_by_user_id=ACTOR)
        assert gate_is_locked(db, eng.id) is True
        db.close()

    def test_gate_items_count_is_7(self):
        assert len(GATE_ITEMS) == 7
