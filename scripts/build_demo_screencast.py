#!/usr/bin/env python3
"""Build the committed demo screencast from a real demo run.

Runs ``scripts/demo_azure_vertex_e2e.py`` (deterministic, offline), captures
its ANSI-colored output, and renders it as a screen-capture-style animation:

* ``docs/demo/azure-vertex-e2e-screencast.svg``  — pure CSS animation, plays
  inline when the file is viewed on GitHub; no scripts, loops forever.
* ``docs/demo/azure-vertex-e2e-screencast.html`` — self-contained player with
  play/pause/restart and speed controls; open locally in any browser.

Because the demo run is deterministic, both artifacts reproduce exactly, so a
diff in CI or review means the demo's behavior changed — never capture noise.
"""

from __future__ import annotations

import re
import subprocess
import sys
from html import escape
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUT_DIR = _REPO_ROOT / "docs" / "demo"
_DEMO = _REPO_ROOT / "scripts" / "demo_azure_vertex_e2e.py"

COLS = 96  # soft-wrap column, like a 96-col terminal
VISIBLE_ROWS = 24  # viewport height in rows before scrolling starts
LINE_H = 17  # px per row in the SVG
CHAR_W = 7.85  # px per monospace char at 13px
HOLD_SECONDS = 6.0  # freeze on the final frame before the loop restarts

# ANSI SGR code → color (terminal-on-dark palette)
_PALETTE = {
    "1;36": ("#67e8f9", True),  # bright cyan (titles)
    "1;33": ("#fbbf24", True),  # bright yellow (step headers)
    "1;31": ("#f87171", True),  # bright red (HIGH severity)
    "32": ("#4ade80", False),  # green (ok ticks)
    "33": ("#fbbf24", False),  # yellow (warnings / MEDIUM)
    "36": ("#67e8f9", False),  # cyan (LOW)
    "2": ("#8b949e", False),  # dim (INFO)
}
_DEFAULT = ("#e6edf3", False)

_ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")

Span = tuple[str, str, bool]  # text, color, bold


def capture_run() -> str:
    proc = subprocess.run(
        [sys.executable, str(_DEMO)],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
    )
    return proc.stdout


def parse_ansi_line(line: str) -> list[Span]:
    spans: list[Span] = []
    color, bold = _DEFAULT
    pos = 0
    for m in _ANSI_RE.finditer(line):
        if m.start() > pos:
            spans.append((line[pos : m.start()], color, bold))
        code = m.group(1)
        color, bold = _DEFAULT if code in ("", "0") else _PALETTE.get(code, _DEFAULT)
        pos = m.end()
    if pos < len(line):
        spans.append((line[pos:], color, bold))
    return [s for s in spans if s[0]]


def wrap_spans(spans: list[Span], cols: int = COLS) -> list[list[Span]]:
    """Soft-wrap a styled line at ``cols`` chars, terminal-style."""
    rows: list[list[Span]] = [[]]
    used = 0
    for text, color, bold in spans:
        while text:
            room = cols - used
            if room <= 0:
                rows.append([])
                used = 0
                room = cols
            chunk, text = text[:room], text[room:]
            rows[-1].append((chunk, color, bold))
            used += len(chunk)
    return rows


def build_timeline(raw: str) -> list[tuple[list[Span], float]]:
    """(styled row, appearance time) for every wrapped output row."""
    timeline: list[tuple[list[Span], float]] = []
    t = 0.8  # opening beat
    for line in raw.splitlines():
        plain = _ANSI_RE.sub("", line)
        if plain.startswith(("[", "━━")):
            t += 1.1  # dramatic pause before each step header / section
        rows = wrap_spans(parse_ansi_line(line)) if plain else [[]]
        for row in rows:
            timeline.append((row, round(t, 2)))
            t += 0.28
        t += 0.24
    return timeline


# ── SVG renderer ─────────────────────────────────────────────────────────────


def render_svg(timeline: list[tuple[list[Span], float]]) -> str:
    total = timeline[-1][1] + HOLD_SECONDS
    width = int(COLS * CHAR_W + 44)
    height = VISIBLE_ROWS * LINE_H + 74

    def pct(t: float) -> float:
        return round(max(0.0, min(100.0, t / total * 100)), 3)

    mono = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
    css: list[str] = [
        ".r{opacity:0;animation:a var(--T) linear infinite}",
        f"text{{font-family:{mono};font-size:13px;white-space:pre}}",
    ]
    # per-row reveal keyframes (shared duration → clean infinite loop)
    frames: list[str] = []
    for i, (_row, t) in enumerate(timeline):
        p = pct(t)
        frames.append(
            f"@keyframes r{i}{{0%,{p}%{{opacity:0}}{pct(t + 0.05)}%,100%{{opacity:1}}}}"
        )
        css.append(f"#l{i}{{animation:r{i} {total}s linear infinite}}")

    # scroll keyframes: jump the content group up as rows pass the viewport
    scroll_stops: list[tuple[float, int]] = [(0.0, 0)]
    for i, (_row, t) in enumerate(timeline):
        if i >= VISIBLE_ROWS:
            scroll_stops.append((t, (i - VISIBLE_ROWS + 1) * LINE_H))
    scroll_kf = ["0%{transform:translateY(0)}"]
    for t, off in scroll_stops[1:]:
        scroll_kf.append(f"{pct(t - 0.18)}%{{transform:translateY(-{off - LINE_H}px)}}")
        scroll_kf.append(f"{pct(t)}%{{transform:translateY(-{off}px)}}")
    scroll_kf.append(f"100%{{transform:translateY(-{scroll_stops[-1][1]}px)}}")
    frames.append("@keyframes scroll{" + "".join(scroll_kf) + "}")
    css.append(f"#content{{animation:scroll {total}s linear infinite}}")

    rows_svg: list[str] = []
    for i, (row, _t) in enumerate(timeline):
        y = 14 + i * LINE_H
        bold_attr = ' font-weight="bold"'
        tspans = (
            "".join(
                f'<tspan fill="{c}"{bold_attr if b else ""}>{escape(txt)}</tspan>'
                for txt, c, b in row
            )
            or " "
        )
        rows_svg.append(
            f'<text id="l{i}" class="r" x="0" y="{y}" xml:space="preserve">{tspans}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    {"".join(frames)}
    {"".join(css)}
  </style>
  <rect width="{width}" height="{height}" rx="10" fill="#0d1117"/>
  <rect width="{width}" height="34" rx="10" fill="#161b22"/>
  <rect y="24" width="{width}" height="10" fill="#161b22"/>
  <circle cx="20" cy="17" r="5.5" fill="#f87171"/>
  <circle cx="40" cy="17" r="5.5" fill="#fbbf24"/>
  <circle cx="60" cy="17" r="5.5" fill="#4ade80"/>
  <text x="{width // 2}" y="21" text-anchor="middle" fill="#8b949e"
        font-family="monospace" font-size="12">saro-demo — python scripts/demo_azure_vertex_e2e.py</text>
  <svg x="22" y="48" width="{width - 44}" height="{VISIBLE_ROWS * LINE_H + 8}">
    <g id="content">{"".join(rows_svg)}</g>
  </svg>
</svg>
"""


# ── HTML player renderer ─────────────────────────────────────────────────────


def render_html(timeline: list[tuple[list[Span], float]]) -> str:
    import json

    data = [
        {"t": t, "s": [[txt, c, int(b)] for txt, c, b in row]} for row, t in timeline
    ]
    payload = json.dumps(data).replace("</", "<\\/")
    return """<!-- Generated by scripts/build_demo_screencast.py — do not hand-edit. -->
<title>SARO — Azure OpenAI + Vertex AI E2E Demo Screencast</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; padding: 24px 12px; display: flex; flex-direction: column;
         align-items: center; gap: 14px; background: #f3f4f6;
         font-family: system-ui, sans-serif; }
  @media (prefers-color-scheme: dark) { body { background: #010409; } }
  :root[data-theme="dark"] body { background: #010409; }
  :root[data-theme="light"] body { background: #f3f4f6; }
  h1 { font-size: 15px; color: #6b7280; font-weight: 600; margin: 0; }
  #frame { width: min(100%, 860px); background: #0d1117; border-radius: 10px;
           box-shadow: 0 12px 40px rgba(0,0,0,.35); overflow: hidden; }
  #bar { display: flex; align-items: center; gap: 7px; padding: 10px 14px;
         background: #161b22; }
  #bar i { width: 11px; height: 11px; border-radius: 50%; display: block; }
  #bar .t { flex: 1; text-align: center; color: #8b949e; font: 12px monospace; }
  #screen { height: 430px; overflow-y: auto; padding: 12px 18px;
            font: 13px/1.35 "SFMono-Regular", Consolas, Menlo, monospace;
            white-space: pre; color: #e6edf3; }
  #screen div { min-height: 17.5px; }
  #controls { display: flex; gap: 8px; }
  button { border: 1px solid #d1d5db; background: #fff; color: #111827;
           border-radius: 8px; padding: 6px 16px; font-size: 13px; cursor: pointer; }
  @media (prefers-color-scheme: dark) {
    button { background: #161b22; color: #e6edf3; border-color: #30363d; } }
  button.on { outline: 2px solid #67e8f9; }
</style>
<h1>SARO &mdash; Azure OpenAI + Vertex AI end-to-end demo (screen capture)</h1>
<div id="frame">
  <div id="bar"><i style="background:#f87171"></i><i style="background:#fbbf24"></i>
    <i style="background:#4ade80"></i>
    <span class="t">saro-demo &mdash; python scripts/demo_azure_vertex_e2e.py</span></div>
  <div id="screen"></div>
</div>
<div id="controls">
  <button id="play">&#9208; Pause</button>
  <button id="restart">&#8635; Replay</button>
  <button data-v="1" class="spd on">1&times;</button>
  <button data-v="2" class="spd">2&times;</button>
  <button data-v="4" class="spd">4&times;</button>
</div>
<script>
const ROWS = __DATA__;
const screen = document.getElementById("screen");
let speed = 1, playing = true, clock = 0, idx = 0, last = null;
function reset() { screen.innerHTML = ""; clock = 0; idx = 0; }
function tick(now) {
  if (last !== null && playing) {
    clock += (now - last) / 1000 * speed;
    while (idx < ROWS.length && ROWS[idx].t <= clock) {
      const div = document.createElement("div");
      for (const [txt, color, bold] of ROWS[idx].s) {
        const sp = document.createElement("span");
        sp.textContent = txt; sp.style.color = color;
        if (bold) sp.style.fontWeight = "bold";
        div.appendChild(sp);
      }
      if (!ROWS[idx].s.length) div.innerHTML = "&nbsp;";
      screen.appendChild(div);
      screen.scrollTop = screen.scrollHeight;
      idx++;
    }
  }
  last = now; requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
document.getElementById("play").onclick = (e) => {
  playing = !playing;
  e.target.innerHTML = playing ? "&#9208; Pause" : "&#9654; Play";
};
document.getElementById("restart").onclick = () => reset();
for (const b of document.querySelectorAll(".spd")) b.onclick = () => {
  speed = +b.dataset.v;
  document.querySelectorAll(".spd").forEach(x => x.classList.toggle("on", x === b));
};
</script>
""".replace("__DATA__", payload)


def main() -> int:
    raw = capture_run()
    timeline = build_timeline(raw)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = _OUT_DIR / "azure-vertex-e2e-screencast.svg"
    html_path = _OUT_DIR / "azure-vertex-e2e-screencast.html"
    svg_path.write_text(render_svg(timeline))
    html_path.write_text(render_html(timeline))
    dur = timeline[-1][1] + HOLD_SECONDS
    print(f"rows={len(timeline)} duration={dur:.1f}s")
    print(f"wrote {svg_path.relative_to(_REPO_ROOT)}")
    print(f"wrote {html_path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
