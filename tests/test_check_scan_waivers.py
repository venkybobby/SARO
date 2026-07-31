"""scripts/check_scan_waivers.py routes waiver IDs to the right scanner by prefix.

Added alongside the starlette CVE waiver (security/scan-waivers.md): before this,
--pip-args emitted every row unfiltered and Trivy had no waiver mechanism wired up
at all, so a documented waiver silenced pip-audit but Trivy would still gate-fail
on the same accepted risk. PYSEC-*/GHSA-* -> pip-audit --ignore-vuln, CVE-* -> the
Trivy ignore file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_scan_waivers.py"


def _run(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_pip_args_only_includes_pysec_and_ghsa_ids():
    out = _run("--pip-args")
    assert "--ignore-vuln PYSEC-2026-1325" in out
    assert "--ignore-vuln PYSEC-2026-161" in out
    assert "CVE-2026-48818" not in out
    assert "CVE-2026-54283" not in out


def test_trivyignore_only_includes_cve_ids():
    out = _run("--trivyignore")
    assert "CVE-2026-48818" in out
    assert "CVE-2026-54283" in out
    assert "PYSEC-2026-1325" not in out


def test_expiry_check_still_passes_with_no_args():
    out = _run()
    assert "EXPIRED WAIVER" not in out
    assert "scan-waivers OK" in out
