#!/usr/bin/env python3
"""Patch-only dependency sweeper for SARO.

Loop: dependency-sweeper (see loops/registry.yaml). Scans requirements.txt for
EXACT pins (``name==X.Y.Z``) and bumps each to the latest available PATCH release
within the same major.minor line. It NEVER bumps minor or major versions, never
touches ``>=`` floors or extras-only lines, and never auto-merges — the workflow
opens a PR for human review and the full pytest suite must pass first.

This is deliberately conservative: patch releases are backwards-compatible bug/
security fixes, so the blast radius is small and the change is easy to verify.

Usage:
    # Show proposed patch bumps as JSON (no file written):
    python scripts/dependency_sweeper.py --json

    # Rewrite requirements.txt in place with the patch bumps:
    python scripts/dependency_sweeper.py --apply

Exit 0 = success (with or without updates). Exit 1 = error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
PYPI_URL = "https://pypi.org/pypi/{name}/json"

# Matches an exact pin like ``package[extra]==1.2.3`` capturing name (with any
# extras) and the version. Lines with >=, <=, ~=, ranges, comments, or no
# specifier are intentionally left untouched.
_EXACT_PIN = re.compile(r"^(?P<pkg>[A-Za-z0-9._-]+(?:\[[^\]]+\])?)==(?P<version>[^\s#;]+)\s*$")


def parse_exact_pin(line: str) -> tuple[str, str] | None:
    """Return (package_with_extras, version) for an exact pin, else None."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    m = _EXACT_PIN.match(stripped)
    if not m:
        return None
    return m.group("pkg"), m.group("version")


def package_name(pkg_with_extras: str) -> str:
    """Strip any ``[extras]`` suffix to get the bare PyPI project name."""
    return pkg_with_extras.split("[", 1)[0]


def latest_patch(current: str, available: list[str]) -> str | None:
    """Highest available version sharing current's major.minor and a strictly
    greater patch. Pre-releases and non-final versions are ignored. Returns the
    new version string, or None if nothing newer in the same minor line."""
    try:
        cur = Version(current)
    except InvalidVersion:
        return None
    best: Version | None = None
    for raw in available:
        try:
            v = Version(raw)
        except InvalidVersion:
            continue
        if v.is_prerelease or v.is_devrelease:
            continue
        if (v.major, v.minor) != (cur.major, cur.minor):
            continue
        if v <= cur:
            continue
        if best is None or v > best:
            best = v
    return str(best) if best is not None else None


def compute_updates(
    requirements_text: str,
    version_lookup,
) -> tuple[str, list[dict]]:
    """Apply patch bumps to the requirements text.

    version_lookup(name) -> list[str] of available versions (injected so the
    pure logic is testable without network access).

    Returns (new_text, updates) where updates is a list of
    {"package", "from", "to"} dicts.
    """
    out_lines: list[str] = []
    updates: list[dict] = []
    for line in requirements_text.splitlines():
        pin = parse_exact_pin(line)
        if pin is None:
            out_lines.append(line)
            continue
        pkg, current = pin
        available = version_lookup(package_name(pkg)) or []
        new_version = latest_patch(current, available)
        if new_version is None:
            out_lines.append(line)
            continue
        out_lines.append(f"{pkg}=={new_version}")
        updates.append({"package": pkg, "from": current, "to": new_version})
    new_text = "\n".join(out_lines)
    if requirements_text.endswith("\n"):
        new_text += "\n"
    return new_text, updates


def fetch_versions(name: str) -> list[str]:
    """Query PyPI for all released versions of a project (network)."""
    url = PYPI_URL.format(name=name)
    with urllib.request.urlopen(url, timeout=20) as resp:  # noqa: S310 (trusted host)
        data = json.load(resp)
    return list(data.get("releases", {}).keys())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Patch-only dependency sweeper.")
    parser.add_argument("--requirements", default=str(REQUIREMENTS),
                        help="Path to requirements.txt")
    parser.add_argument("--apply", action="store_true",
                        help="Rewrite the requirements file in place.")
    parser.add_argument("--json", action="store_true",
                        help="Emit the proposed updates as JSON to stdout.")
    args = parser.parse_args(argv)

    req_path = Path(args.requirements)
    if not req_path.exists():
        print(f"error: {req_path} not found", file=sys.stderr)
        return 1

    text = req_path.read_text()
    new_text, updates = compute_updates(text, fetch_versions)

    if args.json:
        print(json.dumps({"updates": updates}, indent=2))
    else:
        if updates:
            for u in updates:
                print(f"  {u['package']}: {u['from']} -> {u['to']}")
        else:
            print("No patch updates available.")

    if args.apply and updates:
        req_path.write_text(new_text)
        print(f"Updated {req_path} ({len(updates)} package(s)).", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
