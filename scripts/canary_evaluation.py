#!/usr/bin/env python3
"""Synthetic canary: one known-good evaluation, end to end (STORY-368 AC-4).

Health probes prove the process is listening. This proves the thing customers
actually pay for still works: authenticate, submit a fixed benign prompt/output
pair, and confirm a well-formed risk score and TRACE reference come back.

Deliberately a **known-good, benign** sample: the canary is checking that the
pipeline runs, not asserting a particular score. Pinning an exact score would
make every legitimate scoring change look like an outage.

Exits non-zero with a runbook pointer on failure — the workflow failing is the
alert (docs/ops/alerts.md §3).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import NoReturn

BASE_URL = os.environ.get("SARO_URL", "https://saro-backend.fly.dev").rstrip("/")
EMAIL = os.environ.get("DEMO_EMAIL", "")
PASSWORD = os.environ.get("DEMO_PASSWORD", "")
TIMEOUT = 30

RUNBOOK = "docs/ops/runbooks.md#a6--canary-evaluation-failed-api-healthy"

# Fixed, benign, synthetic. No PHI, no customer content (INV-2).
CANARY_PROMPT = "Summarize the appointment scheduling policy for a clinic."
CANARY_OUTPUT = (
    "Appointments may be booked during business hours. Staff confirm availability "
    "before scheduling. No patient information is included in this summary."
)


def _fail(message: str) -> NoReturn:
    print(f"::error::A6 canary evaluation failed — {message} (runbook: {RUNBOOK})")
    sys.exit(1)


def _post(path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300]
        return exc.code, {"error": detail}
    except Exception as exc:  # noqa: BLE001
        _fail(f"request to {path} raised {type(exc).__name__}: {exc}")
        raise  # unreachable


def main() -> int:
    if not EMAIL or not PASSWORD:
        _fail("demo credentials not configured")

    status, body = _post("/api/v1/auth/token", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        _fail(f"login returned {status}: {str(body)[:200]}")
    token = body.get("access_token") or body.get("token")
    if not token:
        _fail(f"login succeeded but returned no token (keys: {sorted(body)})")

    status, result = _post(
        "/api/v1/scan",
        {"prompt": CANARY_PROMPT, "raw_output": CANARY_OUTPUT, "vertical": "general"},
        token=token,
    )
    if status not in (200, 201):
        _fail(f"evaluation returned {status}: {str(result)[:200]}")

    # Contract checks only — never an exact score (see module docstring).
    score = result.get("risk_score", result.get("overall_risk_score"))
    if score is None:
        _fail(f"evaluation produced no risk score (keys: {sorted(result)})")
    try:
        score_value = float(score)
    except (TypeError, ValueError):
        _fail(f"risk score is not numeric: {score!r}")
    if not 0 <= score_value <= 100:
        _fail(f"risk score {score_value} outside the documented 0-100 range")

    audit_ref = result.get("audit_id") or result.get("id") or result.get("trace_id")
    if not audit_ref:
        _fail(f"evaluation produced no audit/TRACE reference (keys: {sorted(result)})")

    print(f"canary OK — score={score_value} audit={audit_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
