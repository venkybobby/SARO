"""First-party, PHI-free product analytics (STORY-381).

Roadmap decisions want behaviour data, but an analytics event is a classic
place for PII to leak in as a "just this once" free-text property. So this is
PHI-free **by construction**, the same discipline as usage metering: a closed
event-name vocabulary, a closed property-key allowlist, bounded scalar values,
and no free-text field anywhere. A caller cannot smuggle content in — there is
nowhere to put it.

Emission is **fail-open**: a product-analytics write must never break or delay a
real request. A lost event is acceptable; a 500 on login because the analytics
insert failed is not.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Closed vocabularies (docs/analytics/event-schema.md) ────────────────────

LOGIN = "login"
ATTESTATION_VIEWED = "attestation_viewed"
RULE_PACK_SUBSCRIBED = "rule_pack_subscribed"
FIRST_EVALUATION = "first_evaluation"
HUB_ARTIFACT_VIEWED = "compliance_hub_artifact_viewed"

EVENT_NAMES = frozenset(
    {LOGIN, ATTESTATION_VIEWED, RULE_PACK_SUBSCRIBED, FIRST_EVALUATION, HUB_ARTIFACT_VIEWED}
)

# Property keys allowed on an event. Nothing that could carry content or PII.
PROPERTY_KEYS = frozenset({"persona", "surface", "artifact_type", "adapter_id", "outcome"})

# Per-key closed value allow-lists where the value space is bounded (None = any
# bounded scalar under the length cap).
_PROPERTY_VALUES: dict[str, Optional[frozenset]] = {
    "surface": frozenset({"web", "api", "cli"}),
    "outcome": frozenset({"success", "failure"}),
    "persona": None,
    "artifact_type": None,
    "adapter_id": None,
}
_MAX_VALUE_LEN = 64


class AnalyticsError(Exception):
    """A closed-vocabulary violation — a coding error, surfaced loudly."""


def _validate(event_name: str, properties: dict) -> None:
    if event_name not in EVENT_NAMES:
        raise AnalyticsError(f"unknown event_name: {event_name!r}")
    unknown = set(properties) - PROPERTY_KEYS
    if unknown:
        raise AnalyticsError(f"free-text/unknown property keys forbidden: {sorted(unknown)}")
    for key, value in properties.items():
        if not isinstance(value, (str, int, bool)):
            raise AnalyticsError(
                f"property {key!r} must be a bounded scalar, not {type(value).__name__}"
            )
        allowed = _PROPERTY_VALUES.get(key)
        if allowed is not None and str(value) not in allowed:
            raise AnalyticsError(f"property {key!r} value not in the closed allow-list")
        if isinstance(value, str) and len(value) > _MAX_VALUE_LEN:
            raise AnalyticsError(
                f"property {key!r} value exceeds {_MAX_VALUE_LEN} chars "
                "(possible payload smuggling — rejected)"
            )


def record(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    event_name: str,
    properties: Optional[dict] = None,
) -> None:
    """Record one product-analytics event. Validates, then inserts.

    Raises AnalyticsError on a vocabulary violation (a bug — surfaced loudly,
    never silently storing garbage). This is the strict form; hot paths use
    :func:`safe_record`.
    """
    from models import ProductEvent

    properties = dict(properties or {})
    _validate(event_name, properties)
    db.add(ProductEvent(tenant_id=tenant_id, event_name=event_name, properties=properties))
    db.commit()


def safe_record(db: Session, **kwargs) -> None:
    """Fail-open emission for request paths — analytics never breaks a request."""
    try:
        record(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 — analytics must not break the caller
        db.rollback()
        logger.warning("product analytics event dropped (continuing): %s", exc)
