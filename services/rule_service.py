"""Rule pack management service — versioned YAML rule packs with changelog tracking."""
import re
from pathlib import Path
from typing import Optional
import yaml

RULE_PACKS_DIR = Path(__file__).parent.parent / "rule_packs"
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def load_rule_pack(pack_file: Path) -> dict:
    """Load a single rule pack YAML file."""
    with open(pack_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_rule_packs() -> list[dict]:
    """Return metadata for all available rule packs."""
    if not RULE_PACKS_DIR.exists():
        return []

    packs = []
    for yaml_file in sorted(RULE_PACKS_DIR.glob("*.yaml")):
        try:
            pack = load_rule_pack(yaml_file)
            packs.append({
                "name": pack.get("name"),
                "version": pack.get("version"),
                "framework": pack.get("framework"),
                "last_updated": pack.get("last_updated"),
                "status": pack.get("status", "active"),
                "rule_count": len(pack.get("rules", [])),
                "changelog": pack.get("changelog", []),
                "file": yaml_file.name,
            })
        except Exception:
            continue
    return packs


def get_pack_by_name(framework: str) -> Optional[dict]:
    """Find a rule pack by framework identifier."""
    for pack in list_rule_packs():
        if pack.get("framework", "").lower() == framework.lower():
            return pack
    return None


def validate_semver(version: str) -> bool:
    """Validate that a version string follows MAJOR.MINOR.PATCH format."""
    return bool(SEMVER_PATTERN.match(str(version)))


def parse_changelog(pack: dict) -> list[dict]:
    """Extract changelog entries from a rule pack."""
    return pack.get("changelog", [])


def check_drift(framework: str, current_version: str, latest_version: str) -> Optional[dict]:
    """Compare current and latest framework versions to detect drift.

    Returns an alert dict if drift detected, None if up-to-date.
    """
    if current_version == latest_version:
        return None
    return {
        "framework": framework,
        "current_version": current_version,
        "latest_version": latest_version,
        "alert_type": "version_drift",
        "message": f"{framework} has updated to {latest_version} (you have {current_version})",
    }
