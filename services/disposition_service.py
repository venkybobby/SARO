"""Finding disposition lifecycle (STORY-DISP-001).

Forward-only state machine with an append-only, hash-chained transition log — reuses
the evf_engagement_service discipline (event_hash = SHA-256(payload + prev_hash)). A
failed evaluation becomes an OPEN disposition; every transition is actor+timestamp
stamped and sealed. De-identified by construction (INV-2 — never observed content).

An expired WAIVED disposition auto-reopens to OPEN (the transition log is the lineage)
and emits a notification — the first real consumer of the notifications table.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import Disposition, DispositionTransition, Notification

logger = logging.getLogger(__name__)

OPEN = "OPEN"
ACKNOWLEDGED = "ACKNOWLEDGED"
REMEDIATED = "REMEDIATED"
WAIVED = "WAIVED"
ESCALATED = "ESCALATED"
GENESIS = "GENESIS"

# Forward-only, user-initiated transitions. WAIVED -> OPEN is system-only (expiry reopen).
_ALLOWED: dict[str, set[str]] = {
    OPEN: {ACKNOWLEDGED},
    ACKNOWLEDGED: {REMEDIATED, WAIVED, ESCALATED},
    REMEDIATED: set(),
    WAIVED: set(),
    ESCALATED: set(),
}
# A finding is still "active" (recurrence links to it) until closed.
_ACTIVE_STATES = {OPEN, ACKNOWLEDGED, WAIVED}


class DispositionError(Exception):
    """Base for disposition errors."""


class IllegalTransitionError(DispositionError):
    """Requested state transition is not permitted from the current state."""


class WaiverRequirementError(DispositionError):
    """A WAIVE is missing required justification/approver/expiry, or violates four-eyes."""


# ── hash chain (evf pattern) ────────────────────────────────────────────────────
def _transition_payload(t: dict, prev_hash: Optional[str]) -> dict:
    return {
        "disposition_id": str(t.get("disposition_id", "")),
        "seq": t.get("seq", 0),
        "from_state": str(t.get("from_state", "")),
        "to_state": str(t.get("to_state", "")),
        "actor": str(t.get("actor") or ""),
        "reason": str(t.get("reason") or ""),
        "prev_hash": prev_hash or GENESIS,
    }


def _transition_hash(t: dict, prev_hash: Optional[str]) -> str:
    return hashlib.sha256(
        json.dumps(_transition_payload(t, prev_hash), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _chain_tail(db: Session, disposition_id: uuid.UUID) -> tuple[Optional[str], int]:
    row = (
        db.query(DispositionTransition.event_hash, DispositionTransition.seq)
        .filter(DispositionTransition.disposition_id == disposition_id)
        .order_by(DispositionTransition.seq.desc())
        .with_for_update()
        .first()
    )
    return (row[0], row[1]) if row else (None, 0)


def _append_transition(
    db: Session,
    disposition: Disposition,
    *,
    from_state: str,
    to_state: str,
    actor: Optional[str],
    reason: Optional[str],
) -> DispositionTransition:
    prev_hash, last_seq = _chain_tail(db, disposition.id)
    seq = last_seq + 1
    payload = {
        "disposition_id": disposition.id,
        "seq": seq,
        "from_state": from_state,
        "to_state": to_state,
        "actor": actor,
        "reason": reason,
    }
    event_hash = _transition_hash(payload, prev_hash)
    tr = DispositionTransition(
        disposition_id=disposition.id,
        seq=seq,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        reason=reason,
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    db.add(tr)
    return tr


def _audit(
    db: Session, disposition: Disposition, to_state: str, actor: Optional[str]
) -> None:
    """Mirror the transition into the META-001 self-audit spine (fail-open)."""
    try:
        import services.self_audit as self_audit

        self_audit.record_access(
            db,
            tenant_id=disposition.tenant_id,
            actor=actor or "system",
            action_class=self_audit.DISPOSITION_ACTION,
            target_type="disposition",
            target_id=str(disposition.id),
            metadata={"to_state": to_state},
        )
    except Exception as exc:  # noqa: BLE001 — self-audit must never break the lifecycle
        logger.warning("disposition self-audit failed (continuing): %s", exc)


# ── create (AC-1) ────────────────────────────────────────────────────────────────
def create_disposition(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    evidence_record_id: Optional[uuid.UUID] = None,
    rule_id: Optional[str] = None,
    gate_id: Optional[str] = None,
    system_id: Optional[str] = None,
    severity: Optional[str] = None,
    actor: Optional[str] = None,
) -> Disposition:
    """Create an OPEN disposition for a failing finding (AC-1).

    Recurrence (edge): if an ACTIVE disposition already exists for the same
    (tenant, rule_id, system_id), increment its recurrence_count and return it —
    a recurring finding links to the prior chain rather than spawning duplicates.
    """
    if rule_id and system_id:
        existing = (
            db.query(Disposition)
            .filter(
                Disposition.tenant_id == tenant_id,
                Disposition.rule_id == rule_id,
                Disposition.system_id == system_id,
                Disposition.state.in_(_ACTIVE_STATES),
            )
            .order_by(Disposition.created_at.desc())
            .first()
        )
        if existing is not None:
            existing.recurrence_count += 1
            existing.updated_at = datetime.now(tz=timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing

    disp = Disposition(
        tenant_id=tenant_id,
        evidence_record_id=evidence_record_id,
        rule_id=rule_id,
        gate_id=gate_id,
        system_id=system_id,
        severity=severity,
        state=OPEN,
    )
    db.add(disp)
    db.flush()  # get id
    _append_transition(
        db,
        disp,
        from_state=GENESIS,
        to_state=OPEN,
        actor=actor,
        reason="Finding opened",
    )
    db.commit()
    db.refresh(disp)
    _audit(db, disp, OPEN, actor)
    return disp


# ── transition (AC-2/AC-5) ──────────────────────────────────────────────────────
def transition(
    db: Session,
    disposition: Disposition,
    to_state: str,
    *,
    actor: Optional[str],
    reason: Optional[str] = None,
    waiver_justification: Optional[str] = None,
    waiver_approver: Optional[str] = None,
    waiver_expiry: Optional[date] = None,
) -> Disposition:
    """Apply a user-initiated state transition with an append-only log entry."""
    from_state = disposition.state
    if to_state not in _ALLOWED.get(from_state, set()):
        raise IllegalTransitionError(f"{from_state} -> {to_state} is not permitted")

    if to_state == WAIVED:
        if not (waiver_justification and waiver_approver and waiver_expiry):
            raise WaiverRequirementError(
                "WAIVE requires justification, approver, and expiry"
            )
        # A waiver may not indefinitely suppress a finding (security review): expiry
        # must be in the future and within the configured max horizon.
        today = datetime.now(tz=timezone.utc).date()
        max_expiry = today + timedelta(days=settings.saro_disposition_max_waiver_days)
        if waiver_expiry <= today:
            raise WaiverRequirementError("waiver expiry must be a future date")
        if waiver_expiry > max_expiry:
            raise WaiverRequirementError(
                f"waiver expiry exceeds the max horizon of "
                f"{settings.saro_disposition_max_waiver_days} days"
            )
        # Four-eyes: the approver must differ from BOTH the acknowledger (spec) and the
        # actor invoking the waive (self-approval guard).
        if settings.saro_disposition_four_eyes:
            forbidden = {a for a in (disposition.acknowledged_by, actor) if a}
            if waiver_approver in forbidden:
                raise WaiverRequirementError(
                    "four-eyes: waiver approver must differ from the acknowledger and the actor"
                )
        disposition.waiver_justification = waiver_justification
        disposition.waiver_approver = waiver_approver
        disposition.waiver_expiry = waiver_expiry

    if to_state == ACKNOWLEDGED:
        disposition.acknowledged_at = datetime.now(tz=timezone.utc)
        disposition.acknowledged_by = actor

    disposition.state = to_state
    disposition.updated_at = datetime.now(tz=timezone.utc)
    _append_transition(
        db,
        disposition,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        reason=reason,
    )
    db.commit()
    db.refresh(disposition)
    _audit(db, disposition, to_state, actor)
    return disposition


def acknowledge(db, disposition, *, actor, reason=None):
    return transition(db, disposition, ACKNOWLEDGED, actor=actor, reason=reason)


def remediate(db, disposition, *, actor, reason=None):
    return transition(db, disposition, REMEDIATED, actor=actor, reason=reason)


def escalate(db, disposition, *, actor, reason=None):
    return transition(db, disposition, ESCALATED, actor=actor, reason=reason)


def waive(db, disposition, *, actor, justification, approver, expiry, reason=None):
    return transition(
        db,
        disposition,
        WAIVED,
        actor=actor,
        reason=reason,
        waiver_justification=justification,
        waiver_approver=approver,
        waiver_expiry=expiry,
    )


# ── waiver expiry auto-reopen (AC-3) ────────────────────────────────────────────
def expire_waivers(
    db: Session, *, tenant_id: Optional[uuid.UUID] = None, now: Optional[date] = None
) -> list[Disposition]:
    """Auto-reopen WAIVED dispositions whose expiry has passed; emit a notification each.

    Same-row reopen (WAIVED -> OPEN): the transition log carries the lineage to the
    expired waiver. Emits a Notification (first real consumer of the notifications table).
    """
    today = now or datetime.now(tz=timezone.utc).date()
    q = db.query(Disposition).filter(
        Disposition.state == WAIVED,
        Disposition.waiver_expiry.isnot(None),
        Disposition.waiver_expiry < today,
    )
    if tenant_id is not None:
        q = q.filter(Disposition.tenant_id == tenant_id)

    reopened: list[Disposition] = []
    for disp in q.all():
        expired_on = disp.waiver_expiry.isoformat() if disp.waiver_expiry else "unknown"
        disp.state = OPEN
        disp.updated_at = datetime.now(tz=timezone.utc)
        _append_transition(
            db,
            disp,
            from_state=WAIVED,
            to_state=OPEN,
            actor="system:waiver-expiry",
            reason=f"Waiver expired {expired_on} — auto-reopened",
        )
        db.add(
            Notification(
                tenant_id=disp.tenant_id,
                type="disposition_reopened",
                title="Waiver expired — finding reopened",
                body=f"Disposition {disp.id} waiver expired on {expired_on} "
                f"and was auto-reopened to OPEN.",
                severity="high",
            )
        )
        db.commit()
        db.refresh(disp)
        _audit(db, disp, OPEN, "system:waiver-expiry")
        reopened.append(disp)
    return reopened


# ── verify + report (AC-4) ──────────────────────────────────────────────────────
def verify_transition_chain(db: Session, disposition_id: uuid.UUID) -> dict:
    trs = (
        db.query(DispositionTransition)
        .filter(DispositionTransition.disposition_id == disposition_id)
        .order_by(DispositionTransition.seq.asc())
        .all()
    )
    prev_hash: Optional[str] = None
    for i, tr in enumerate(trs):
        payload = {
            "disposition_id": tr.disposition_id,
            "seq": tr.seq,
            "from_state": tr.from_state,
            "to_state": tr.to_state,
            "actor": tr.actor,
            "reason": tr.reason,
        }
        expected = _transition_hash(payload, prev_hash)
        if tr.seq != i + 1 or tr.prev_hash != prev_hash or tr.event_hash != expected:
            return {"valid": False, "break_at_seq": tr.seq}
        prev_hash = tr.event_hash
    return {"valid": True, "transitions_checked": len(trs)}


def disposition_report(db: Session, tenant_id: uuid.UUID) -> dict:
    """Examiner artifact (AC-4): counts, state breakdown, mean time-to-ack, waivers, lineage."""
    dispositions = (
        db.query(Disposition).filter(Disposition.tenant_id == tenant_id).all()
    )
    breakdown: dict[str, int] = {}
    ack_deltas: list[float] = []
    waivers: list[dict] = []
    reopened_lineage: list[dict] = []
    for d in dispositions:
        breakdown[d.state] = breakdown.get(d.state, 0) + 1
        if d.acknowledged_at and d.created_at:
            ack_deltas.append((d.acknowledged_at - d.created_at).total_seconds())
        # Active waivers only (state == WAIVED) — a reopened row keeps its historical
        # waiver fields but must not be double-counted here (it is in the lineage below).
        if d.state == WAIVED and d.waiver_justification:
            waivers.append(
                {
                    "disposition_id": str(d.id),
                    "approver": d.waiver_approver,
                    "expiry": d.waiver_expiry.isoformat() if d.waiver_expiry else None,
                    "justification": d.waiver_justification,
                    "state": d.state,
                }
            )
        # Reopened-from-waiver lineage: a currently-OPEN disposition that carries waiver fields
        # has been through a waive->expire cycle (the transition log holds the detail).
        if d.state == OPEN and d.waiver_justification:
            reopened_lineage.append(
                {
                    "disposition_id": str(d.id),
                    "previously_waived_until": d.waiver_expiry.isoformat()
                    if d.waiver_expiry
                    else None,
                }
            )
    mean_ttk = round(sum(ack_deltas) / len(ack_deltas), 1) if ack_deltas else None
    return {
        "findings_count": len(dispositions),
        "state_breakdown": breakdown,
        "mean_time_to_acknowledge_seconds": mean_ttk,
        "waivers": waivers,
        "reopened_waiver_lineage": reopened_lineage,
    }
