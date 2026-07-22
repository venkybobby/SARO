"""Validation completion-bar loader (STORY-377).

Reads the completion bar and answers one question the rest of the system needs:
**is a bar in force, and if so what are its thresholds?** The safety property
lives here: an unsigned proposal is never in force. A caller that asks
``active_thresholds()`` on an unsigned bar gets ``None`` — there is no code path
by which SARO enforces a bar it set for itself without an owner's signature.

The signed bar lives at ``quality/validation/completion-bar.yaml``; until it
exists the proposal at ``completion-bar.proposed.yaml`` is loaded, and its
``status`` (``PROPOSED_AWAITING_SIGNOFF``) keeps it inert.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

_DIR = Path(__file__).resolve().parents[1] / "quality" / "validation"
_SIGNED = _DIR / "completion-bar.yaml"
_PROPOSED = _DIR / "completion-bar.proposed.yaml"

SIGNED = "SIGNED"
PROPOSED = "PROPOSED_AWAITING_SIGNOFF"


def _load_raw() -> Optional[dict[str, Any]]:
    # A signed bar, once it exists, takes precedence over the proposal.
    path = _SIGNED if _SIGNED.exists() else _PROPOSED
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def is_in_force() -> bool:
    """True only if a bar exists AND is signed. A proposal is never in force."""
    raw = _load_raw()
    return bool(raw) and raw.get("status") == SIGNED


def status() -> str:
    raw = _load_raw()
    if not raw:
        return "ABSENT"
    return str(raw.get("status", "UNKNOWN"))


def active_thresholds() -> Optional[dict[str, Any]]:
    """The thresholds to enforce, or ``None`` when no signed bar is in force.

    ``None`` is the whole point: STORY-378's harness reads this, and when it is
    ``None`` the harness reports rates without pass/fail — it cannot enforce a
    bar that does not exist or was never signed.
    """
    if not is_in_force():
        return None
    raw = _load_raw() or {}
    profile_key = raw.get("chosen_profile")
    profiles = raw.get("profiles", {})
    # A signed bar names its chosen profile; fall back to a top-level thresholds
    # block if a future signed file inlines them directly.
    if profile_key and profile_key in profiles:
        return profiles[profile_key].get("thresholds")
    return raw.get("thresholds")


def proposal_summary() -> dict[str, Any]:
    """Human-facing: what is proposed and whether it is signed. Never enforcing."""
    raw = _load_raw() or {}
    return {
        "status": raw.get("status", "ABSENT"),
        "in_force": is_in_force(),
        "strategy_version": raw.get("strategy_version"),
        "profiles": sorted((raw.get("profiles") or {}).keys()),
        "chosen_profile": raw.get("chosen_profile"),
    }
