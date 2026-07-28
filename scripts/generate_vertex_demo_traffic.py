#!/usr/bin/env python3
"""Generate a varied Vertex AI GenerateContent corpus for the SARO demo.

Issues ~100 real Vertex calls in the CUSTOMER's own GCP project so the Cloud
Logging audit sink delivers a richer export for SARO to read (more findings:
provider errors, region spread, streaming). The scenario mix is deterministic
by index so ``--dry-run`` and the unit test can verify it without touching GCP.

    ┌─────────────────────────── IDENTITY BOUNDARY ───────────────────────────┐
    │ This script CALLS Vertex — it needs an invoke principal with            │
    │ roles/aiplatform.user (your own ADC, or a dedicated SA). That is NOT    │
    │ saro-reader, which is read-only storage (roles/storage.objectViewer)    │
    │ and cannot invoke models. Keep the two separate: the reader reads logs, │
    │ this generator writes traffic.                                          │
    └─────────────────────────────────────────────────────────────────────────┘

This is DEMO TOOLING, not part of SARO. SARO's scoring never calls a model
(INV-1); this generator only produces the customer-side traffic whose *logs*
SARO later reads.

Auth: Application Default Credentials with the cloud-platform scope —
    gcloud auth application-default login        (as an aiplatform.user principal)
  or
    $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\\path\\to\\invoke-sa-key.json"

Usage:
    # dry run — see the plan, no calls, no auth:
    python scripts/generate_vertex_demo_traffic.py --project <PROJECT> --dry-run

    # generate 100 calls (default) into your project:
    python scripts/generate_vertex_demo_traffic.py --project <PROJECT>

    python scripts/generate_vertex_demo_traffic.py --project <PROJECT> \\
        --count 100 --model gemini-2.0-flash --regions us-central1,europe-west4

Then wait for the hourly sink delivery and re-run the reader:
    python scripts/demo_vertex_to_ui.py --tenant <UUID> --system gemini-prod \\
        --source gs://<export-bucket> --allowed-tool lookup_care_pathway
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# Vertex generative traffic that maps to SARO's four demo verticals. Content is
# benign — the point is to produce audit-log ENTRIES, not to exercise the model.
_VERTICAL_PROMPTS = {
    "healthcare": "Summarize triage priority for chest pain and shortness of breath.",
    "finance": "List the key factors in a consumer credit decision.",
    "government": "Draft eligibility criteria for a housing benefit program.",
    "technology": "Classify this forum post for content moderation: great product.",
}
_VERTICALS = list(_VERTICAL_PROMPTS)


@dataclass(frozen=True)
class Call:
    """One planned Vertex call. ``category`` drives the expected audit outcome."""

    category: str  # happy | stream | bad_model | malformed
    region: str
    model: str
    method: str  # generateContent | streamGenerateContent
    prompt: str
    expect_error: bool


# ── Deterministic scenario plan (testable without GCP) ───────────────────────


def build_plan(count: int, model: str, regions: list[str]) -> list[Call]:
    """Deterministic mix by index — ~70% happy, 15% stream, 8% bad-model, 7% malformed.

    Deterministic (no randomness) so --dry-run and the unit test see the exact
    same plan the live run would issue.
    """
    plan: list[Call] = []
    for i in range(count):
        region = regions[i % len(regions)]
        vertical = _VERTICALS[i % len(_VERTICALS)]
        prompt = _VERTICAL_PROMPTS[vertical]
        bucket = i % 100  # percentage bucket → category
        if bucket < 70:
            plan.append(Call("happy", region, model, "generateContent", prompt, False))
        elif bucket < 85:
            plan.append(
                Call("stream", region, model, "streamGenerateContent", prompt, False)
            )
        elif bucket < 93:
            # A model id that does not exist → NOT_FOUND (OBS-ERROR-INVOCATION).
            plan.append(
                Call(
                    "bad_model",
                    region,
                    "no-such-model-999",
                    "generateContent",
                    prompt,
                    True,
                )
            )
        else:
            # Malformed request → INVALID_ARGUMENT (OBS-ERROR-INVOCATION).
            plan.append(Call("malformed", region, model, "generateContent", "", True))
    return plan


def plan_summary(plan: list[Call]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in plan:
        out[c.category] = out.get(c.category, 0) + 1
    return dict(sorted(out.items()))


# ── Live issuance (needs GCP creds) ──────────────────────────────────────────


def _access_token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Generating traffic needs google-auth (installed with "
            "google-cloud-storage): pip install google-cloud-storage"
        ) from exc
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return str(creds.token)


def _body(call: Call) -> dict:
    if call.category == "malformed":
        return {"contents": "this-is-not-the-right-shape"}
    return {"contents": [{"role": "user", "parts": [{"text": call.prompt}]}]}


def _issue(call: Call, project: str, token: str) -> int:
    url = (
        f"https://{call.region}-aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{call.region}/publishers/google/models/{call.model}:{call.method}"
    )
    data = json.dumps(_body(call)).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)  # 4xx/5xx are expected for the error scenarios
    except urllib.error.URLError:
        return 0  # network-level failure; still logged as no-status


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True, help="GCP project id that owns Vertex")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--model", default="gemini-2.0-flash")
    ap.add_argument(
        "--regions", default="us-central1,europe-west4", help="comma-separated"
    )
    ap.add_argument("--pace", type=float, default=0.25, help="seconds between calls")
    ap.add_argument(
        "--dry-run", action="store_true", help="print the plan; no auth, no calls"
    )
    args = ap.parse_args(argv)

    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    plan = build_plan(args.count, args.model, regions)
    summary = plan_summary(plan)

    print(f"Plan: {args.count} Vertex calls in project {args.project}")
    print(f"  regions: {regions} · model: {args.model}")
    print(f"  mix: {summary}")
    print(
        "  expected findings: OBS-ERROR-INVOCATION on the "
        f"{summary.get('bad_model', 0) + summary.get('malformed', 0)} error calls; "
        "OBS-TOKEN-COUNTS (INFO) on every record."
    )

    if args.dry_run:
        print("\n--dry-run: no calls issued. Sample of first 5:")
        for c in plan[:5]:
            print(f"  {c.category:<9} {c.method:<22} {c.region:<14} {c.model}")
        return 0

    print("\nAuthenticating (ADC, cloud-platform scope)…")
    token = _access_token()
    print("Issuing calls (audit logs land in the sink; delivery is ~hourly)…")
    codes: dict[int, int] = {}
    for i, call in enumerate(plan, start=1):
        code = _issue(call, args.project, token)
        codes[code] = codes.get(code, 0) + 1
        if i % 10 == 0 or i == len(plan):
            print(
                f"  {i}/{len(plan)} issued · status counts so far: {dict(sorted(codes.items()))}"
            )
        if args.pace:
            time.sleep(args.pace)

    print(f"\nDone. HTTP status distribution: {dict(sorted(codes.items()))}")
    print(
        "Wait for the sink to deliver, then read with scripts/demo_vertex_to_ui.py "
        "(--source gs://<bucket>)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
