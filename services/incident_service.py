"""S-1106 / FB-019 — incident fix-state mutations with an audit trail.

The corpus's ``is_fixed`` boolean previously carried no provenance. These helpers
are the *single write path* for that flag: every change to ``is_fixed`` records
``fixed_by`` and ``fixed_at`` together, so a resolved incident always says who
resolved it and when (and clearing it wipes both, leaving no stale attribution).

Callers must mutate ``is_fixed`` through these helpers, never by assigning the
column directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import AIIncident


def set_incident_fixed(
    db: Session,
    incident: AIIncident,
    *,
    fixed: bool,
    actor: str,
    commit: bool = True,
) -> AIIncident:
    """Set ``incident.is_fixed`` and write the audit fields atomically.

    Args:
        db: active session.
        incident: the AIIncident row to mutate.
        fixed: target state of ``is_fixed``.
        actor: identity recorded in ``fixed_by`` (user id/email/"system seed").
        commit: commit the session (default True); pass False to batch.

    Returns:
        The same incident, with ``is_fixed`` and the audit fields updated.

    When ``fixed`` is True, ``fixed_by``/``fixed_at`` are stamped. When False,
    both are cleared so a re-opened incident keeps no stale attribution.
    """
    incident.is_fixed = fixed
    if fixed:
        incident.fixed_by = actor
        incident.fixed_at = datetime.now(timezone.utc)
    else:
        incident.fixed_by = None
        incident.fixed_at = None

    db.add(incident)
    if commit:
        db.commit()
        db.refresh(incident)
    return incident
