"""Rule pack management API — versioned YAML rule packs with drift alerting."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services.rule_service import check_drift, get_pack_by_name, list_rule_packs

router = APIRouter(prefix="/api/v1/rules", tags=["rule-packs"])

# Known latest framework versions (in production fetched from live feeds)
FRAMEWORK_VERSIONS = {
    "NIST-AI-RMF": "1.0.0",
    "EU-AI-ACT-2024": "1.0.0",
    "AIGP": "2.0.0",
    "ISO-42001": "2023.0",
}


@router.get("/packs")
def get_rule_packs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return all available rule packs with metadata, versions, and changelogs."""
    packs = list_rule_packs()
    return {"packs": packs, "total": len(packs)}


@router.get("/packs/{framework}")
def get_rule_pack(
    framework: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a specific rule pack by framework ID."""
    pack = get_pack_by_name(framework)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Rule pack for {framework} not found")
    return pack


def _build_drift_response() -> dict:
    """Shared logic: compare active rule packs against latest known framework versions."""
    alerts = []
    current_versions: dict[str, Optional[str]] = {}

    for pack in list_rule_packs():
        framework = pack.get("framework")
        current = pack.get("version")
        if framework:
            current_versions[framework] = current
        latest = FRAMEWORK_VERSIONS.get(framework) if framework else None
        if latest and current:
            alert = check_drift(framework, current, latest)
            if alert:
                alerts.append(alert)

    return {
        "alerts": alerts,
        "alert_count": len(alerts),
        "current_versions": current_versions,
        "latest_known_versions": FRAMEWORK_VERSIONS,
        "checked_at": datetime.utcnow().isoformat(),
    }


@router.get("/drift-alerts")
def get_drift_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Check all active rule packs against latest framework versions for drift."""
    return _build_drift_response()


@router.get("/drift-check")
def drift_check(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Alias for /drift-alerts — used by the Streamlit drift tab."""
    return _build_drift_response()
