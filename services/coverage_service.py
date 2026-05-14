"""AI system coverage gap analysis service."""
from datetime import datetime, timedelta
from typing import Optional


DEFAULT_OVERDUE_DAYS = 60


def calculate_coverage_status(last_audit_date: Optional[str],
                               overdue_threshold_days: int = DEFAULT_OVERDUE_DAYS) -> str:
    """Determine coverage status for an AI system.

    Returns: 'GREEN' (recently audited), 'AMBER' (approaching overdue),
             'RED' (overdue), or 'NEVER_AUDITED'
    """
    if last_audit_date is None:
        return "NEVER_AUDITED"

    try:
        if isinstance(last_audit_date, str):
            last_dt = datetime.fromisoformat(last_audit_date.split("T")[0])
        else:
            last_dt = last_audit_date
    except (ValueError, AttributeError):
        return "NEVER_AUDITED"

    days_since = (datetime.utcnow() - last_dt).days

    if days_since <= overdue_threshold_days * 0.5:
        return "GREEN"
    elif days_since < overdue_threshold_days:
        return "AMBER"
    return "RED"


def build_coverage_report(ai_systems: list[dict],
                           overdue_threshold_days: int = DEFAULT_OVERDUE_DAYS) -> list[dict]:
    """Build coverage report for all registered AI systems.

    Args:
        ai_systems: List of {name, vendor, owner, last_audit_date, ...}
        overdue_threshold_days: Days without audit before system is flagged

    Returns:
        List of systems with added coverage_status, days_since_audit, is_overdue
    """
    result = []
    for system in ai_systems:
        last = system.get("last_audit_date")
        status = calculate_coverage_status(last, overdue_threshold_days)

        days_since = None
        if last:
            try:
                dt = datetime.fromisoformat(str(last).split("T")[0])
                days_since = (datetime.utcnow() - dt).days
            except ValueError:
                pass

        result.append({
            **system,
            "coverage_status": status,
            "days_since_audit": days_since,
            "is_overdue": status in ("RED", "NEVER_AUDITED"),
            "overdue_threshold_days": overdue_threshold_days,
        })

    return result
