"""Tests for the Azure OpenAI + Vertex AI E2E demo kit.

Pins three properties the demo depends on:

1. The runner walks both adapters offline and its counts match the committed
   corpora exactly (deterministic — the talk track in
   docs/demo/AZURE_VERTEX_E2E_DEMO.md quotes these numbers).
2. The run makes zero network calls and zero writes outside --json-out.
3. The demo's user-facing output stays inside the compliance language boundary
   (docs/COMPLIANCE_CLAIMS_MATRIX.md): evidence-shaped, never a verdict.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_demo_screencast import build_timeline, parse_ansi_line, wrap_spans
from scripts.demo_azure_vertex_e2e import main as demo_main

REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.unit  # no DB, no network (enforced by the no_network fixture)

# Exact expectations, derived from the byte-verified corpora. If these change,
# the corpora changed — update docs/demo/AZURE_VERTEX_E2E_DEMO.md Part 4 too.
EXPECTED = {
    "Azure OpenAI": {
        "records_read": 54,
        "records_normalized": 52,
        "records_skipped": 1,
        "records_rejected": 1,
        "findings_total": 14,
    },
    "Vertex AI": {
        "records_read": 56,
        "records_normalized": 53,
        "records_skipped": 1,
        "records_rejected": 2,
        "findings_total": 66,
    },
}

# Vocabulary the demo output must never use: verdict language (claims matrix
# "Forbidden" column) plus ANY framework-alignment reference — EVF status is
# Internal Review Only, so demo materials are Tier 3 (no framework claims).
FORBIDDEN_OUTPUT_PHRASES = (
    "compliant",
    "certified",
    "audit passed",
    "audit: passed",
    "compliance score",
    "compliance_fix",
    "guarantee",
    "tamper-proof",
    "nist",
    "ai rmf",
    "eu ai act",
    "iso 42001",
    "aigp",
)


@pytest.fixture()
def no_network(monkeypatch):
    """The demo is offline by contract — fail loudly if anything dials out."""

    def _blocked(*args, **kwargs):
        raise AssertionError("demo runner attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _run(tmp_path: Path, capsys, extra: list[str] | None = None) -> tuple[dict, str]:
    json_out = tmp_path / "summary.json"
    rc = demo_main(["--no-color", "--json-out", str(json_out), *(extra or [])])
    assert rc == 0
    return json.loads(json_out.read_text()), capsys.readouterr().out


def test_both_providers_match_the_committed_corpora(tmp_path, capsys, no_network):
    summary, out = _run(tmp_path, capsys)
    by_provider = {p["provider"]: p for p in summary["providers"]}
    assert set(by_provider) == set(EXPECTED)
    for provider, expected in EXPECTED.items():
        got = {k: by_provider[provider][k] for k in expected}
        assert got == expected, f"{provider} counts drifted from the corpus"

    # The high-signal demo moment: out-of-scope tool invocations are surfaced.
    assert "delete_patient_record" in out
    assert "purge_audit_log" in out
    assert "TOOL-SCOPE-VIOLATION-1" in out


def test_run_is_deterministic(tmp_path, capsys, no_network):
    first, out_first = _run(tmp_path / "a", capsys)
    second, out_second = _run(tmp_path / "b", capsys)
    assert first == second

    # Terminal output identical except the echoed --json-out path.
    def strip(o: str) -> list[str]:
        return [ln for ln in o.splitlines() if not ln.startswith("JSON summary")]

    assert strip(out_first) == strip(out_second)


def test_single_provider_selection(tmp_path, capsys, no_network):
    summary, _ = _run(tmp_path, capsys, ["--provider", "azure"])
    assert [p["provider"] for p in summary["providers"]] == ["Azure OpenAI"]


def test_output_stays_inside_the_claims_boundary(tmp_path, capsys, no_network):
    _, out = _run(tmp_path, capsys)
    lowered = out.lower()
    for phrase in FORBIDDEN_OUTPUT_PHRASES:
        assert phrase not in lowered, (
            f"forbidden verdict language in demo output: {phrase!r}"
        )
    # The required disclaimer is present and evidence framing is explicit.
    assert "human review" in lowered
    assert "does not constitute regulatory certification" in lowered


def test_pack_hashes_are_reported_for_provenance(tmp_path, capsys, no_network):
    summary, _ = _run(tmp_path, capsys)
    for provider in summary["providers"]:
        refs = {p["ref"] for p in provider["packs"]}
        assert refs == {"RP-OBS-COMPLETE@1.0.0", "RP-TOOL-SCOPE@1.0.0"}
        assert all(len(p["hash"]) == 64 for p in provider["packs"])


# ── Screencast builder ───────────────────────────────────────────────────────


def test_ansi_parse_and_wrap_preserve_text():
    line = "\x1b[1;33m[1/5] Read export\x1b[0m plain tail"
    spans = parse_ansi_line(line)
    assert "".join(t for t, _c, _b in spans) == "[1/5] Read export plain tail"
    assert spans[0][2] is True  # bold step header

    long = [("x" * 250, "#fff", False)]
    rows = wrap_spans(long, cols=96)
    assert [sum(len(t) for t, *_ in r) for r in rows] == [96, 96, 58]


def test_committed_screencast_is_in_sync_with_the_demo():
    """The committed SVG/HTML must reproduce from the current demo output.

    Mirrors the corpus builders' --check discipline: a demo change without a
    regenerated screencast (python scripts/build_demo_screencast.py) fails here.
    """
    import subprocess

    from scripts.build_demo_screencast import render_html, render_svg

    raw = subprocess.run(
        [sys.executable, str(REPO / "scripts/demo_azure_vertex_e2e.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",  # runner emits UTF-8 on every platform (FND-087)
        check=True,
        cwd=REPO,
    ).stdout
    timeline = build_timeline(raw)
    assert (
        REPO / "docs/demo/azure-vertex-e2e-screencast.svg"
    ).read_text(encoding="utf-8") == render_svg(timeline)
    assert (
        REPO / "docs/demo/azure-vertex-e2e-screencast.html"
    ).read_text(encoding="utf-8") == render_html(timeline)
