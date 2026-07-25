#!/usr/bin/env python3
"""Persona UI verification — walk every persona's view of the demo data.

Closes the gap the demo kit left open: `scripts/demo_capture_playwright.py`
verifies the public ``/demo`` flow (DEMO_TABS, demo_viewer token) but nothing
verified the AUTHENTICATED persona views — AI Auditor, Risk Officer,
Compliance Lead, and the rest. This script does, using the product's own
persona switcher (the same control a presenter uses live):

    login as a super_admin verification user
      -> for each persona: switch via the sidebar persona switcher
         -> assert the rendered nav is EXACTLY that persona's PERSONA_TABS
         -> click every tab, screenshot it, and census API responses >= 400

Expected tabs per persona are parsed from ``frontend/src/components/Sidebar.jsx``
at runtime, so this harness follows the frontend — it cannot drift from it.

Prerequisites — a running local stack (backend :8000 + Vite :5173):

    AUTHORITATIVE (Postgres): pwsh scripts/run_local.ps1   # seeds demo data
    FALLBACK (no Docker):     python scripts/run_local_sqlite.py --seed
                              # UI-mechanics smoke only: several API panels 500
                              # under the SQLite stand-in (UUID shim) — expect
                              # census noise there; Postgres is the green gate.

    python scripts/demo_persona_ui_verification.py --ensure-user
    python scripts/demo_persona_ui_verification.py  # the walk

Exit 0 = every persona rendered its exact tab set, every tab captured, zero
API responses >= 400. Anything else = 1, so this can gate demo prep the same
way RB-006 gates the manual run. Screenshots land in artifacts/persona-ui/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDEBAR = ROOT / "frontend" / "src" / "components" / "Sidebar.jsx"

VERIFY_USER_EMAIL = "persona-verify@saro-demo.internal"
# Local verification harness only — same posture as seed_demo's default.
VERIFY_USER_PASSWORD = "SaroPersonaWalk2026!"
DEMO_TENANT_SLUG = "saro-demo"

# The three business personas a demo audience actually plays; --all adds the
# internal ones (admin / super_admin / operator).
DEFAULT_PERSONAS = ["ai_auditor", "risk_officer", "compliance_lead"]


# ── Sidebar.jsx parsing (single source of truth for expectations) ────────────


def parse_sidebar() -> tuple[dict[str, list[str]], dict[str, str], dict[str, str]]:
    """Return (PERSONA_TABS, tab_id -> label, persona -> ROLE_LABEL)."""
    src = SIDEBAR.read_text(encoding="utf-8")

    def block(name: str) -> str:
        m = re.search(rf"const {name} = \{{(.*?)\n\}};", src, re.DOTALL)
        if not m:
            raise SystemExit(f"could not locate {name} in Sidebar.jsx")
        return m.group(1)

    persona_tabs: dict[str, list[str]] = {}
    for m in re.finditer(r"(\w+): \[([^\]]*)\]", block("PERSONA_TABS"), re.DOTALL):
        persona_tabs[m.group(1)] = re.findall(r'"(\w+)"', m.group(2))

    labels: dict[str, str] = {}
    for m in re.finditer(r'(\w+):\s*\{ label: "([^"]+)"', block("TAB_REGISTRY")):
        labels[m.group(1)] = m.group(2)

    role_labels: dict[str, str] = {}
    for m in re.finditer(r'(\w+):\s*"([^"]+)"', block("ROLE_LABELS")):
        role_labels[m.group(1)] = m.group(2)

    return persona_tabs, labels, role_labels


# ── --ensure-user: super_admin verification account (direct DB, like seed) ───


def ensure_user() -> int:
    sys.path.insert(0, str(ROOT))
    from auth import hash_password
    from database import create_all_tables, get_db
    from models import Tenant, User

    create_all_tables()
    db = next(get_db())
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == DEMO_TENANT_SLUG).first()
        if not tenant:
            print("demo tenant missing — run scripts/seed_demo.py first")
            return 1
        user = db.query(User).filter(User.email == VERIFY_USER_EMAIL).first()
        if user:
            user.role = "super_admin"
            user.hashed_password = hash_password(VERIFY_USER_PASSWORD)
        else:
            db.add(
                User(
                    email=VERIFY_USER_EMAIL,
                    hashed_password=hash_password(VERIFY_USER_PASSWORD),
                    role="super_admin",
                    persona_role="super_admin",
                    tenant_id=tenant.id,
                )
            )
        db.commit()
        print(f"verification user ready: {VERIFY_USER_EMAIL} (super_admin)")
        return 0
    finally:
        db.close()


# ── The walk ─────────────────────────────────────────────────────────────────


def walk(
    base_url: str, out_dir: Path, personas: list[str], chromium_path: str | None
) -> int:
    from playwright.sync_api import sync_playwright

    persona_tabs, tab_labels, role_labels = parse_sidebar()
    unknown = [p for p in personas if p not in persona_tabs]
    if unknown:
        print(f"unknown personas {unknown}; valid: {sorted(persona_tabs)}")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    bad: list[tuple[str, int, str]] = []
    problems: list[str] = []
    current_persona: dict[str, str | None] = {"value": None}

    with sync_playwright() as p:
        browser = (
            p.chromium.launch(executable_path=chromium_path)
            if chromium_path
            else p.chromium.launch()
        )
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.on(
            "response",
            lambda r: (
                bad.append((current_persona["value"] or "login", r.status, r.url))
                if "/api/" in r.url and r.status >= 400
                else None
            ),
        )

        # Login
        page.goto(base_url, wait_until="networkidle", timeout=60_000)
        page.locator('input[type="email"]').fill(VERIFY_USER_EMAIL)
        page.locator('input[type="password"]').fill(VERIFY_USER_PASSWORD)
        page.locator('button[type="submit"]').click()
        page.get_by_text(VERIFY_USER_EMAIL).wait_for(timeout=30_000)
        time.sleep(1)

        # First-run onboarding modal (STORY-TAB-008 Dashboard checklist) overlays
        # the whole app after a fresh login — dismiss it like a presenter would.
        cont = page.get_by_text("Continue to App", exact=False)
        if cont.count() > 0:
            cont.first.click()
            time.sleep(0.5)

        for persona in personas:
            current_persona["value"] = persona
            pdir = out_dir / persona
            pdir.mkdir(exist_ok=True)
            for stale in pdir.glob("*.png"):  # never mix runs in one report
                stale.unlink()

            # Switch via the product's own switcher (user chip -> persona entry)
            page.get_by_text(VERIFY_USER_EMAIL).click()
            page.get_by_text("Switch persona").wait_for(timeout=10_000)
            page.get_by_role("button", name=role_labels[persona], exact=True).click()
            page.wait_for_load_state("networkidle", timeout=30_000)
            time.sleep(1.5)
            # The switcher menu stays open over the nav — outside-click closes it.
            page.mouse.click(720, 640)
            time.sleep(0.4)

            # The nav must show EXACTLY this persona's tabs — no more, no less.
            expected = [tab_labels[t] for t in persona_tabs[persona]]
            rendered = [
                t
                for t in tab_labels.values()
                if page.get_by_text(t, exact=True).count() > 0
            ]
            missing = [t for t in expected if t not in rendered]
            extra = [t for t in rendered if t not in expected]
            if missing:
                problems.append(f"{persona}: tabs missing from sidebar: {missing}")
            if extra:
                problems.append(f"{persona}: unexpected tabs visible: {extra}")

            for i, tab in enumerate(persona_tabs[persona], start=1):
                label = tab_labels[tab]
                try:
                    page.get_by_text(label, exact=True).first.click(timeout=10_000)
                    page.wait_for_load_state("networkidle", timeout=30_000)
                    time.sleep(1.2)
                    page.screenshot(
                        path=str(pdir / f"{i:02d}-{tab}.png"), full_page=True
                    )
                    print(f"[{persona}] captured {tab}")
                except Exception as exc:  # noqa: BLE001 — record and keep walking
                    problems.append(f"{persona}/{tab}: {exc}")
                    page.screenshot(path=str(pdir / f"{i:02d}-{tab}-FAILED.png"))

        browser.close()

    print(f"\nscreenshots -> {out_dir}")
    print("\n=== API responses >= 400 during persona walk ===")
    for persona, status, url in bad:
        print(f"[{persona}] {status} {url}")
    if not bad:
        print("(none)")
    for pr in problems:
        print("PROBLEM:", pr)
    summary = {
        "personas": personas,
        "api_errors": [{"persona": pp, "status": s, "url": u} for pp, s, u in bad],
        "problems": problems,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 1 if (bad or problems) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/persona-ui"))
    parser.add_argument(
        "--personas",
        default=",".join(DEFAULT_PERSONAS),
        help="comma-separated persona list (default: the three business personas)",
    )
    parser.add_argument("--all", action="store_true", help="walk all six personas")
    parser.add_argument("--chromium-path", default=None)
    parser.add_argument(
        "--ensure-user",
        action="store_true",
        help="create/refresh the super_admin verification user, then exit",
    )
    args = parser.parse_args()

    if args.ensure_user:
        return ensure_user()

    personas = list(parse_sidebar()[0].keys()) if args.all else args.personas.split(",")
    return walk(args.base_url, args.out_dir, personas, args.chromium_path)


if __name__ == "__main__":
    sys.exit(main())
