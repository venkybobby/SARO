"""Playwright demo-capture walk — screenshots + red-row census for the /demo flow.

Automates RB-006 §H ("Browser pass"): opens the public /demo entry, waits for the
demo session to authenticate, clicks every DEMO_TABS page, screenshots each one,
opens the first TRACE detail, and reports every API response >= 400 seen during
the walk. Zero red rows is the pass condition, mirroring the manual checklist.

Usage:
    python scripts/demo_capture_playwright.py                      # local dev (Vite on :5173)
    python scripts/demo_capture_playwright.py --base-url https://sarofrontend.fly.dev
    python scripts/demo_capture_playwright.py --out-dir artifacts/demo-capture

Requires: pip install playwright && playwright install chromium
(CI already installs both for the e2e job — see .github/workflows/ci.yml.)

Exit code 0 = all tabs captured and zero API responses >= 400; 1 otherwise, so
this can gate a pre-demo pipeline the same way RB-006 gates the manual run.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEMO_TABS_PATH = ROOT / "frontend" / "src" / "config" / "demoTabs.json"

# Sidebar labels for each DEMO_TABS id (Sidebar.jsx NAV definitions).
TAB_LABELS: dict[str, str] = {
    "dashboard": "Dashboard",
    "trace_view": "TRACE View",
    "compliance_hub": "Compliance Hub",
    "reports": "Reports",
}


def capture(base_url: str, out_dir: Path, chromium_path: str | None) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    demo_tabs: list[str] = json.loads(DEMO_TABS_PATH.read_text())
    bad_responses: list[tuple[int, str]] = []
    failures: list[str] = []

    with sync_playwright() as p:
        if chromium_path:
            browser = p.chromium.launch(executable_path=chromium_path)
        else:
            browser = p.chromium.launch()
        page: Page = browser.new_context(
            viewport={"width": 1440, "height": 900}
        ).new_page()
        page.on(
            "response",
            lambda r: bad_responses.append((r.status, r.url))
            if "/api/" in r.url and r.status >= 400
            else None,
        )

        page.goto(f"{base_url}/demo", wait_until="networkidle", timeout=60_000)
        time.sleep(2)
        page.screenshot(path=str(out_dir / "01-demo-entry.png"))

        for i, tab in enumerate(demo_tabs, start=2):
            label = TAB_LABELS.get(tab, tab)
            try:
                page.get_by_text(label, exact=True).first.click(timeout=10_000)
                page.wait_for_load_state("networkidle", timeout=30_000)
                time.sleep(1.5)
                page.screenshot(path=str(out_dir / f"{i:02d}-{tab}.png"), full_page=True)
                print(f"captured {tab}")
            except Exception as exc:  # noqa: BLE001 — record and keep walking
                failures.append(f"{tab}: {exc}")
                page.screenshot(path=str(out_dir / f"{i:02d}-{tab}-FAILED.png"))

        # TRACE detail: load the first Recent Traces chip so the capture includes
        # the 6-step timeline (the RB-006 §H "open one TRACE detail" line item).
        try:
            page.get_by_text(TAB_LABELS["trace_view"], exact=True).first.click()
            page.wait_for_load_state("networkidle", timeout=30_000)
            time.sleep(1)
            page.locator("button:has-text('…')").first.click(timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
            time.sleep(2)
            page.screenshot(path=str(out_dir / "06-trace-detail.png"), full_page=True)
            print("captured trace detail")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"trace-detail: {exc}")

        browser.close()

    print(f"\nscreenshots -> {out_dir}")
    print("\n=== API responses >= 400 during demo walk ===")
    for status, url in bad_responses:
        print(status, url)
    if not bad_responses:
        print("(none — RB-006 §H zero-red-rows check passed)")
    for f in failures:
        print("CAPTURE FAILURE:", f)
    return 1 if (bad_responses or failures) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/demo-capture"))
    parser.add_argument(
        "--chromium-path",
        default=None,
        help="Explicit chromium executable (for environments with a pre-installed browser)",
    )
    args = parser.parse_args()
    return capture(args.base_url, args.out_dir, args.chromium_path)


if __name__ == "__main__":
    sys.exit(main())
