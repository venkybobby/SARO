"""STORY-106: the legacy VeriAegis landing site is evicted.

Pins that the veriaegis-landing/ Next.js app is gone and the foreign "VeriAegis"
brand no longer appears in live application source (React app + backend). Historical
audit records (docs/evf/*.json) are intentionally NOT rewritten — they record what
was true at the time.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent


@pytest.mark.unit
def test_veriaegis_landing_dir_removed():
    assert not (_ROOT / "veriaegis-landing").exists(), "veriaegis-landing/ must be removed"


@pytest.mark.unit
def test_no_veriaegis_brand_in_live_source():
    offenders = []
    for base in ("frontend/src", "routers", "services"):
        d = _ROOT / base
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".jsx", ".js", ".ts", ".tsx", ".css"}:
                if "veriaegis" in p.read_text(encoding="utf-8", errors="ignore").lower():
                    offenders.append(str(p.relative_to(_ROOT)))
    assert not offenders, f"VeriAegis brand still in live source: {offenders}"
