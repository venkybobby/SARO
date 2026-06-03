"""
EVF Sprint 3 — Validation Status service (FR-EVF-11).

Returns the current EVF validation label for each framework, following the
three-tier language policy (FR-EVF-16):

  Tier 1 — QCO issued and active (not expired, not superseded):
    "Externally Reviewed — QCO {ref} | {sme_firm} | {issue_date}"

  Tier 2 — Under active SME review (engagement in [SOW_ISSUED,
            REVIEW_IN_PROGRESS, DRAFT_QCO_RECEIVED, QCO_APPROVED]):
    "SARO is undergoing independent review for {framework} coverage.
     Claims will be published upon QCO completion."

  Tier 3 — Not assessed / current state (no active engagement or
            engagement in [SHORTLISTED, COI_CLEARED]):
    No compliance alignment reference permitted in external materials.

Expired QCOs fall back to Tier 2 ("Under Review") pending renewal.

The /api/v1/evf/validation-status endpoint returns these labels so
reports, dashboards, and demo environments can stamp the correct tier.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models import EVFFramework, QCORegistry, SMEEngagement, SMEEngagementState

# ── Tier constants ────────────────────────────────────────────────────────────

TIER_1 = "tier_1"  # QCO issued and active
TIER_2 = "tier_2"  # under active SME review
TIER_3 = "tier_3"  # not assessed

# Engagement states that qualify for Tier 2
_TIER_2_STATES = {
    SMEEngagementState.SOW_ISSUED.value,
    SMEEngagementState.REVIEW_IN_PROGRESS.value,
    SMEEngagementState.DRAFT_QCO_RECEIVED.value,
    SMEEngagementState.QCO_APPROVED.value,
}

# Approved label templates (FR-EVF-16)
_TIER_1_TEMPLATE = (
    "Externally Reviewed — QCO {ref} | {sme_firm} | {issue_date}"
)
_TIER_2_TEMPLATE = (
    "SARO is undergoing independent review for {framework} coverage. "
    "Claims will be published upon QCO completion."
)
_TIER_3_LABEL = (
    "Internal Review Only — Not for External Claim"
)

_FRAMEWORK_DISPLAY = {
    "EU_AI_ACT":   "EU AI Act",
    "NIST_AI_RMF": "NIST AI RMF 1.0",
    "AIGP":        "AIGP",
    "ISO_42001":   "ISO 42001",
}


# ── Core query ────────────────────────────────────────────────────────────────

def get_validation_status(db: Session, framework: str) -> dict:
    """
    Return the current validation status dict for a single framework.

    Shape:
    {
        "framework":        "EU_AI_ACT",
        "tier":             "tier_1" | "tier_2" | "tier_3",
        "label":            "<approved display text>",
        "qco_reference":    "SARO-QCO-EU_AI_ACT-2026-001" | None,
        "qco_expiry_date":  "2027-06-01" | None,
        "expires_in_days":  364 | None,
        "checked_at":       "<ISO UTC timestamp>",
    }
    """
    today = date.today()
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── Tier 1 check: active published QCO ───────────────────────────────────
    active_qco: Optional[QCORegistry] = (
        db.query(QCORegistry)
        .filter(
            QCORegistry.framework_covered == framework,
            QCORegistry.published.is_(True),
            QCORegistry.superseded_by_qco_id.is_(None),
        )
        .order_by(QCORegistry.published_at.desc())
        .first()
    )

    if active_qco:
        expiry = active_qco.expiry_date
        if expiry:
            # Handle both date and datetime returns (SQLite vs PostgreSQL)
            if isinstance(expiry, datetime):
                expiry = expiry.date()
            expires_in = (expiry - today).days
        else:
            expires_in = None

        # QCO is active if not expired
        if expiry is None or expiry >= today:
            issue = active_qco.issue_date
            if isinstance(issue, datetime):
                issue = issue.date()

            return {
                "framework":       framework,
                "tier":            TIER_1,
                "label":           _TIER_1_TEMPLATE.format(
                    ref=active_qco.qco_reference_number,
                    sme_firm=active_qco.sme_firm,
                    issue_date=str(issue) if issue else "—",
                ),
                "qco_reference":   active_qco.qco_reference_number,
                "qco_expiry_date": str(expiry) if expiry else None,
                "expires_in_days": expires_in,
                "checked_at":      now_iso,
            }

        # QCO is expired — falls to Tier 2 "Under Review"
        return {
            "framework":       framework,
            "tier":            TIER_2,
            "label":           _TIER_2_TEMPLATE.format(
                framework=_FRAMEWORK_DISPLAY.get(framework, framework)
            ),
            "qco_reference":   active_qco.qco_reference_number,
            "qco_expiry_date": str(expiry) if expiry else None,
            "expires_in_days": expires_in,
            "checked_at":      now_iso,
            "note":            "QCO expired — renewal in progress",
        }

    # ── Tier 2 check: engagement in active review states ─────────────────────
    active_engagement: Optional[SMEEngagement] = (
        db.query(SMEEngagement)
        .filter(
            SMEEngagement.framework == framework,
            SMEEngagement.state.in_(list(_TIER_2_STATES)),
        )
        .order_by(SMEEngagement.updated_at.desc())
        .first()
    )

    if active_engagement:
        return {
            "framework":       framework,
            "tier":            TIER_2,
            "label":           _TIER_2_TEMPLATE.format(
                framework=_FRAMEWORK_DISPLAY.get(framework, framework)
            ),
            "qco_reference":   None,
            "qco_expiry_date": None,
            "expires_in_days": None,
            "checked_at":      now_iso,
        }

    # ── Tier 3: not assessed ─────────────────────────────────────────────────
    return {
        "framework":       framework,
        "tier":            TIER_3,
        "label":           _TIER_3_LABEL,
        "qco_reference":   None,
        "qco_expiry_date": None,
        "expires_in_days": None,
        "checked_at":      now_iso,
    }


def get_all_framework_statuses(db: Session) -> list[dict]:
    """Return validation status for all four in-scope frameworks."""
    return [get_validation_status(db, fw.value) for fw in EVFFramework]
