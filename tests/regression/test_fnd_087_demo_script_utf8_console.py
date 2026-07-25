"""FND-087: the demo runner must survive a cp1252 console (Windows default).

`scripts/demo_azure_vertex_e2e.py` prints non-ASCII glyphs (✔ ▲ →). On
Windows, a piped child Python encodes stdout with the locale codec (cp1252),
so the first glyph raised UnicodeEncodeError and the script died with exit 1 —
which failed `test_committed_screencast_is_in_sync_with_the_demo` on every
Windows checkout while Linux CI stayed green (FND-038 class).

The pin forces the failure mode portably: PYTHONIOENCODING=cp1252 gives the
child a cp1252 stdout on ANY platform. The fix (main() reconfigures
stdout/stderr to UTF-8) must win over that initial encoding.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit]

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "demo_azure_vertex_e2e.py"


def test_demo_runner_survives_a_cp1252_console():
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--provider", "azure", "--no-color"],
        capture_output=True,
        cwd=REPO,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, (
        "demo runner crashed on a cp1252 console (FND-087) — stderr:\n"
        + proc.stderr.decode("utf-8", errors="replace")[-2000:]
    )
    out = proc.stdout.decode("utf-8")
    assert "✔" in out, (  # ✔ — proves glyphs came through as real UTF-8
        "demo output lost its status glyphs — stdout is not UTF-8"
    )
