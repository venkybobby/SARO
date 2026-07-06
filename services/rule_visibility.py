"""Rule-pack validation-status visibility policy (STORY-CHUB-011).

Single source of truth for which rule rows are visible on customer-facing surfaces.
Enforced SERVER-SIDE so draft/retired regulatory mappings are never presented as
authoritative. Fail-closed: an unknown or NULL status is treated as draft (hidden).

Vocabulary (migration radar_scan1_validation_status_columns):
  LEGACY_UNREVIEWED | DRAFT_UNVALIDATED | SME_VALIDATED | RETIRED
"""

from __future__ import annotations

from config import settings

SME_VALIDATED = "SME_VALIDATED"
DRAFT_UNVALIDATED = "DRAFT_UNVALIDATED"
LEGACY_UNREVIEWED = "LEGACY_UNREVIEWED"
RETIRED = "RETIRED"

# Never in a default customer view, regardless of any flag.
HIDDEN_BY_DEFAULT = frozenset({DRAFT_UNVALIDATED, RETIRED})

# Badge codes surfaced to internal personas only (the draft toggle view).
BADGE_DRAFT = "DRAFT"
BADGE_RETIRED = "RETIRED"
BADGE_PENDING_VALIDATION = "PENDING_VALIDATION"


def default_visible_statuses(include_legacy: bool | None = None) -> tuple[str, ...]:
    """The statuses shown in a default (customer) view.

    SME_VALIDATED always; LEGACY_UNREVIEWED only when the show-legacy flag is on.
    DRAFT/RETIRED/NULL are excluded (NULL because it is not in this allow-list).
    """
    if include_legacy is None:
        include_legacy = settings.saro_show_legacy_rules
    statuses = [SME_VALIDATED]
    if include_legacy:
        statuses.append(LEGACY_UNREVIEWED)
    return tuple(statuses)


def is_visible_by_default(
    status: str | None, include_legacy: bool | None = None
) -> bool:
    """True if a row with ``status`` appears in a default customer view (fail-closed)."""
    return status in default_visible_statuses(include_legacy)


def badge_for(status: str | None) -> str | None:
    """Internal-only badge for a row's status (None for plain SME-validated rows)."""
    if status == DRAFT_UNVALIDATED or status is None:
        return BADGE_DRAFT
    if status == RETIRED:
        return BADGE_RETIRED
    if status == LEGACY_UNREVIEWED:
        return BADGE_PENDING_VALIDATION
    return None
