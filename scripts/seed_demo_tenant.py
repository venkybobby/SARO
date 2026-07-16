"""
S-000: SARO Demo Tenant Seed Script
=====================================
Idempotent one-time setup script.  Creates the demo tenant, populates it with
seed AI output audits across all four verticals, and verifies the pipeline end-
to-end before any client demo.

Usage:
    python scripts/seed_demo_tenant.py \
        --database-url $DATABASE_URL \
        --saro-url https://saro-backend.fly.dev

    # Repair/rotate demo login only — skip the 800-record bulk ingest
    # (safe to rerun against a tenant that already has real/demo data):
    python scripts/seed_demo_tenant.py --database-url $DATABASE_URL --skip-ingest

Demo login credentials come from DEMO_USER_EMAIL / DEMO_USER_PASSWORD env vars
if set (highest priority — use this for a CI/Fly secret you want stable
forever), otherwise from a prior run's .env.demo (keeps unattended reruns
stable), otherwise a strong password is generated fresh. Never hardcoded here
— this file is committed to a public repo. Credentials and the JWT/tenant ID
are written to .env.demo (gitignored).

The password is only ever printed to stdout for an interactive run. When
GITHUB_ACTIONS=true (this repo is public — its Actions logs are public too)
the password line is redacted; set DEMO_USER_PASSWORD as a repo secret if you
want the scheduled seed-refresh workflow to use a stable, GitHub-masked value
instead of silently generating and discarding a fresh one every run.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
import time
import uuid

import requests
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import hash_password  # noqa: E402 — needs sys.path insert above

log = structlog.get_logger()


def running_in_public_ci() -> bool:
    """
    True inside a GitHub Actions run. This repo is public, so its Actions
    logs are public too — GitHub only auto-masks values sourced from the
    `secrets.*` context, not a password this script generates itself, so the
    plaintext must never be printed here.
    """
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


DEMO_TENANT_NAME  = "SARO Demo Tenant"
DEMO_TENANT_SLUG  = "saro-demo"
# Not .local/.test/.example — pydantic's EmailStr rejects reserved/special-use
# TLDs, and the backend validates this server-side on every /auth/token call.
DEMO_USER_EMAIL_DEFAULT = "demo@saro-demo.io"

VERTICALS = ["finance", "healthcare", "technology", "government"]

RECORDS_PER_VERTICAL = 200
# Risk distribution per vertical: 0-39=CRITICAL, 40-99=HIGH, 100-159=MEDIUM, 160-199=LOW
RISK_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _risk_level_for_index(idx: int) -> str:
    if idx < 40:
        return "CRITICAL"
    elif idx < 100:
        return "HIGH"
    elif idx < 160:
        return "MEDIUM"
    else:
        return "LOW"


# Base templates per vertical — expanded to 200 records each via synthetic generation
_BASE_TEMPLATES: dict[str, list[dict]] = {
    "finance": [
        {
            "prompt": "Assess credit risk for applicant with DTI {dti} and credit score {score}.",
            "output": (
                "Based on DTI ratio of {dti} and credit score {score}, risk classification is {risk}. "
                "Recommend additional collateral review per SR 11-7 guidelines. Record {idx}."
            ),
        },
        {
            "prompt": "Explain the loan denial decision for application ID {app_id}.",
            "output": (
                "Application {app_id} denied due to: (1) DTI exceeds 43% threshold, "
                "(2) insufficient credit history. SHAP explanation: DTI contributed 0.61 to denial score. "
                "Risk level: {risk}. Record {idx}."
            ),
        },
        {
            "prompt": "What is the fair lending risk in this mortgage portfolio #{idx}?",
            "output": (
                "Disparate impact ratio for minority applicants: 1.19 (threshold 1.15). "
                "Flag for HMDA compliance review. Risk: {risk}. "
                "Recommend model audit per NIST AI RMF MEASURE-2.5. Record {idx}."
            ),
        },
        {
            "prompt": "Review AML screening alert #{idx} for false positive assessment.",
            "output": (
                "AML alert #{idx} reviewed. Transaction velocity score: 0.78. "
                "Recommend SAR filing review. Risk: {risk}. Record {idx}."
            ),
        },
    ],
    "healthcare": [
        {
            "prompt": "Patient #{idx} presents with chest pain, shortness of breath. Recommend triage priority.",
            "output": (
                "PRIORITY assessment for patient #{idx}. Differential: ACS, PE, aortic dissection. "
                "Initiate ECG and troponin. Risk level: {risk}. Record {idx}."
            ),
        },
        {
            "prompt": "Summarise treatment plan for patient #{idx} with HbA1c {hba1c}%.",
            "output": (
                "Recommend: Metformin 1000mg BID, dietary counselling, 3-month HbA1c recheck for patient #{idx}. "
                "Risk: {risk}. Note: AI recommendation — physician review required. Record {idx}."
            ),
        },
        {
            "prompt": "Assess diagnostic support output for radiology scan #{idx}.",
            "output": (
                "Radiology AI output for scan #{idx} reviewed. Confidence: 0.84. "
                "Risk level: {risk}. Human radiologist sign-off required. Record {idx}."
            ),
        },
        {
            "prompt": "Review AI-assisted discharge recommendation for patient #{idx}.",
            "output": (
                "Discharge recommendation for patient #{idx} assessed. Length-of-stay model output reviewed. "
                "Risk: {risk}. Clinical governance evidence generated. Record {idx}."
            ),
        },
    ],
    "technology": [
        {
            "prompt": "Moderate this user comment #{idx} for policy violations.",
            "output": (
                "Content moderation review #{idx}. Toxicity score evaluated (threshold 0.65). "
                "Risk level: {risk}. Recommend human review before publish. Record {idx}."
            ),
        },
        {
            "prompt": "Review API response #{idx} for PII exposure.",
            "output": (
                "PII scan for API response #{idx}. Pattern analysis complete. "
                "GDPR Article 22 automated decision flag assessed. Risk: {risk}. Record {idx}."
            ),
        },
        {
            "prompt": "Perform security analysis on code commit #{idx}.",
            "output": (
                "Security analysis for commit #{idx}. Static analysis complete. "
                "OWASP Top-10 scan performed. Risk level: {risk}. Record {idx}."
            ),
        },
        {
            "prompt": "Review AI code review output for pull request #{idx}.",
            "output": (
                "Code review AI output for PR #{idx} assessed. Logic error detection confidence: 0.77. "
                "Risk: {risk}. Human developer review recommended. Record {idx}."
            ),
        },
    ],
    "government": [
        {
            "prompt": "Assess benefits eligibility determination output for case #{idx}.",
            "output": (
                "Benefits determination output for case #{idx} reviewed. "
                "Age-group disparity ratio within threshold. Risk level: {risk}. "
                "NIST AI RMF GOVERN-1.1 evidence record created. Record {idx}."
            ),
        },
        {
            "prompt": "Review permit processing AI recommendation for application #{idx}.",
            "output": (
                "Permit processing AI output for application #{idx} assessed. "
                "EO 14110 compliance reviewed. Risk: {risk}. "
                "Human oversight requirement verified. Record {idx}."
            ),
        },
        {
            "prompt": "Evaluate policy compliance AI output for regulation check #{idx}.",
            "output": (
                "Policy compliance output for regulation #{idx} reviewed. "
                "NIST RMF mapping: MAP-1.5, MANAGE-3.2. Risk level: {risk}. "
                "Audit trail complete. Record {idx}."
            ),
        },
        {
            "prompt": "Review AI-assisted procurement recommendation #{idx} for federal AI policy.",
            "output": (
                "Procurement AI recommendation #{idx} reviewed per EO 14110. "
                "Human oversight requirement: assessed. Risk: {risk}. Record {idx}."
            ),
        },
    ],
}


def _build_seed_payloads() -> dict[str, list[dict]]:
    """Generate exactly RECORDS_PER_VERTICAL synthetic payloads per vertical."""
    result: dict[str, list[dict]] = {}
    for vertical in VERTICALS:
        templates = _BASE_TEMPLATES[vertical]
        payloads: list[dict] = []
        for idx in range(RECORDS_PER_VERTICAL):
            tmpl = templates[idx % len(templates)]
            risk = _risk_level_for_index(idx)
            fmt_vars = {
                "idx": idx,
                "risk": risk,
                "dti": round(0.30 + (idx % 30) * 0.01, 2),
                "score": 580 + (idx % 200),
                "app_id": 80000 + idx,
                "hba1c": round(6.5 + (idx % 40) * 0.1, 1),
            }
            payloads.append({
                "prompt": tmpl["prompt"].format(**fmt_vars),
                "output": tmpl["output"].format(**fmt_vars),
                "risk_level": risk,
                "seed_index": idx,
            })
        result[vertical] = payloads
    return result


SEED_PAYLOADS: dict[str, list[dict]] = _build_seed_payloads()


# ── Step 1: Create or retrieve demo tenant ────────────────────────────────────


def get_or_create_demo_tenant(session) -> dict:
    row = session.execute(
        text("SELECT id FROM tenants WHERE slug = :slug LIMIT 1"),
        {"slug": DEMO_TENANT_SLUG},
    ).fetchone()
    if row:
        log.info("demo_tenant_exists", tenant_id=str(row[0]))
        return {"tenant_id": str(row[0]), "created": False}

    tenant_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO tenants (id, name, slug, created_at) VALUES (:id, :name, :slug, NOW())"),
        {"id": tenant_id, "name": DEMO_TENANT_NAME, "slug": DEMO_TENANT_SLUG},
    )
    session.execute(
        text(
            "INSERT INTO client_configs "
            "(id, tenant_id, industry, sso_enabled, mfa_required, "
            " allow_magic_link_fallback, warning_banner_active, "
            " scim_enabled, created_at) "
            "VALUES (gen_random_uuid(), :tid, 'multi_vertical', "
            " true, false, true, true, false, NOW()) "
            "ON CONFLICT (tenant_id) DO NOTHING"
        ),
        {"tid": tenant_id},
    )
    session.commit()
    log.info("demo_tenant_created", tenant_id=str(tenant_id))
    return {"tenant_id": str(tenant_id), "created": True}


# ── Step 2: Ensure demo user, then obtain JWT ─────────────────────────────────


_ENV_DEMO_PASSWORD_KEY = "DEMO_USER_PASSWORD"


def _read_env_demo_password(env_demo_path: str) -> str | None:
    """Read a previously-generated DEMO_USER_PASSWORD back out of .env.demo, if any."""
    if not os.path.exists(env_demo_path):
        return None
    prefix = _ENV_DEMO_PASSWORD_KEY + "="
    try:
        with open(env_demo_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith(prefix):
                    return line[len(prefix):].strip() or None
    except OSError:
        return None
    return None


def resolve_demo_credentials(env_demo_path: str = ".env.demo") -> tuple[str, str]:
    """
    Resolve demo login credentials from the environment, generating a strong
    password only the first time. Never hardcode a password here — this file
    is committed to a public repo.

    Precedence: DEMO_USER_PASSWORD env var (explicit override, always wins)
    > password from a prior run's .env.demo (keeps unattended reruns stable —
    ensure_demo_user() resets the DB password every call, so without this an
    unattended rerun would silently rotate a password someone is relying on)
    > freshly generated (first run / .env.demo missing or deleted).
    """
    email = os.getenv("DEMO_USER_EMAIL", DEMO_USER_EMAIL_DEFAULT)
    password = (
        os.getenv("DEMO_USER_PASSWORD")
        or _read_env_demo_password(env_demo_path)
        or secrets.token_urlsafe(18)
    )
    return email, password


def ensure_demo_user(session, tenant_id: str, email: str, password: str) -> dict:
    """
    Idempotently ensure a demo login exists for the tenant: create it if
    missing, otherwise reset its password. Uses the same hash_password()
    the backend's /api/v1/auth/token endpoint verifies against.
    """
    hashed = hash_password(password)
    row = session.execute(
        text("SELECT id FROM users WHERE email = :email LIMIT 1"),
        {"email": email},
    ).fetchone()

    if row:
        session.execute(
            text(
                "UPDATE users SET hashed_password = :pw, tenant_id = :tid, "
                "role = 'super_admin', is_active = true WHERE id = :id"
            ),
            {"pw": hashed, "tid": tenant_id, "id": row[0]},
        )
        session.commit()
        log.info("demo_user_password_reset", user_id=str(row[0]), email=email)
        return {"user_id": str(row[0]), "created": False}

    user_id = uuid.uuid4()
    session.execute(
        text(
            "INSERT INTO users (id, tenant_id, email, hashed_password, role, is_active, created_at) "
            "VALUES (:id, :tid, :email, :pw, 'super_admin', true, NOW())"
        ),
        {"id": user_id, "tid": tenant_id, "email": email, "pw": hashed},
    )
    session.commit()
    log.info("demo_user_created", user_id=str(user_id), email=email)
    return {"user_id": str(user_id), "created": True}


def get_demo_jwt(saro_url: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{saro_url}/api/v1/auth/token",
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token") or resp.json().get("token")
    if not token:
        raise ValueError(f"No token in login response: {resp.json()}")
    log.info("demo_jwt_obtained")
    return token


# ── Step 3: Ingest seed payloads ──────────────────────────────────────────────


def count_existing_audits(saro_url: str, token: str) -> int:
    """Return total_audits count from dashboard — used for idempotency skip."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{saro_url}/api/v1/dashboard/kpis", headers=headers, timeout=10)
        data = resp.json()
        return data.get("total_audits", 0) or data.get("audit_count", 0)
    except Exception:
        return 0


def ingest_seed_payloads(saro_url: str, token: str, tenant_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    results: dict = {"success": 0, "failed": 0, "skipped": 0, "audit_ids": []}

    # Idempotency: skip ingestion entirely if already seeded to >= 800
    existing = count_existing_audits(saro_url, token)
    if existing >= 800:
        log.info("seed_already_complete", existing_audits=existing)
        results["skipped"] = existing
        return results

    for vertical, payloads in SEED_PAYLOADS.items():
        for p in payloads:
            try:
                resp = requests.post(
                    f"{saro_url}/api/v1/ingest",
                    json={
                        "source_model": "internal",
                        "prompt":       p["prompt"],
                        "raw_output":   p["output"],
                        "vertical":     vertical,
                        "tenant_id":    tenant_id,
                        "risk_level":   p.get("risk_level"),
                        "seed_index":   p.get("seed_index"),
                    },
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code == 201:
                    results["success"] += 1
                    results["audit_ids"].append(resp.json()["audit_id"])
                else:
                    results["failed"] += 1
                    log.warning("ingest_failed", status=resp.status_code, body=resp.text[:200])
            except Exception as exc:
                results["failed"] += 1
                log.error("ingest_error", error=str(exc))
            time.sleep(0.2)

    return results


# ── Step 4: Wait for engine ───────────────────────────────────────────────────


def wait_for_audits(saro_url: str, token: str, audit_ids: list, timeout_s: int = 120) -> dict:
    headers  = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout_s
    pending  = set(audit_ids)
    completed = failed = 0

    while pending and time.time() < deadline:
        time.sleep(2)
        for aid in list(pending):
            try:
                resp = requests.get(
                    f"{saro_url}/api/v1/ingest/{aid}",
                    headers=headers, timeout=10,
                )
                s = resp.json().get("status")
                if s == "completed":
                    completed += 1
                    pending.discard(aid)
                elif s == "failed":
                    failed += 1
                    pending.discard(aid)
            except Exception:
                pass

    return {"completed": completed, "failed": failed, "timed_out": len(pending)}


# ── Step 5: Write .env.demo ───────────────────────────────────────────────────


def write_env_demo(
    tenant_id: str,
    token: str,
    saro_url: str,
    demo_email: str | None = None,
    demo_password: str | None = None,
) -> None:
    with open(".env.demo", "w") as f:
        f.write(f"SARO_DEMO_TENANT_ID={tenant_id}\n")
        f.write(f"SARO_DEMO_TOKEN={token}\n")
        f.write(f"SARO_DEMO_URL={saro_url}\n")
        # Persisted so resolve_demo_credentials() can reuse the same password
        # on the next unattended run instead of rotating it every time.
        if demo_email:
            f.write(f"DEMO_USER_EMAIL={demo_email}\n")
        if demo_password:
            f.write(f"DEMO_USER_PASSWORD={demo_password}\n")
    log.info("env_demo_written", path=".env.demo")


# ── Step 6: Verify dashboard ──────────────────────────────────────────────────


def verify_dashboard(saro_url: str, token: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{saro_url}/api/v1/dashboard/kpis", headers=headers, timeout=10)
    data = resp.json()
    count = data.get("total_audits", 0) or data.get("audit_count", 0)
    log.info("dashboard_verified", total_audits=count)
    return count >= 800


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="SARO Demo Tenant Seed Script")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--saro-url", default="https://saro-backend.fly.dev")
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help=(
            "Stop after Step 2 (tenant + demo user + JWT). Use this to repair "
            "demo login credentials without inserting up to 800 more synthetic "
            "audit records into a tenant that already has real/demo data."
        ),
    )
    args = parser.parse_args()

    if not args.database_url:
        log.error("DATABASE_URL required")
        sys.exit(1)

    eng     = create_engine(args.database_url)
    Session = sessionmaker(bind=eng)

    demo_email, demo_password = resolve_demo_credentials()

    print("\n=== SARO Demo Tenant Seed Script ===")

    print("Step 1: Create or retrieve demo tenant...")
    with Session() as session:
        tenant = get_or_create_demo_tenant(session)
    print(f"  Tenant ID: {tenant['tenant_id']} (created={tenant['created']})")

    print("Step 2: Ensure demo user...")
    with Session() as session:
        user = ensure_demo_user(session, tenant["tenant_id"], demo_email, demo_password)
    print(f"  User: {demo_email} (created={user['created']})")

    print("Step 2b: Obtain JWT...")
    token = get_demo_jwt(args.saro_url, demo_email, demo_password)

    if args.skip_ingest:
        print("Step 3-4: Skipped (--skip-ingest)")
    else:
        print("Step 3: Ingest seed payloads...")
        results = ingest_seed_payloads(args.saro_url, token, tenant["tenant_id"])
        print(f"  Ingested: {results['success']} / Failed: {results['failed']}")

        print("Step 4: Waiting for engine (up to 120s)...")
        completion = wait_for_audits(args.saro_url, token, results["audit_ids"])
        print(
            f"  Completed: {completion['completed']}  "
            f"Failed: {completion['failed']}  "
            f"Timed out: {completion['timed_out']}"
        )

    print("Step 5: Writing .env.demo...")
    write_env_demo(tenant["tenant_id"], token, args.saro_url, demo_email, demo_password)

    if args.skip_ingest:
        print("Step 6: Skipped (--skip-ingest) — dashboard count check requires the full seed")
    else:
        print("Step 6: Verifying dashboard...")
        ok = verify_dashboard(args.saro_url, token)
        if not ok:
            print("  WARNING: Dashboard shows 0 audits — check engine logs")
        else:
            print("  Dashboard verified — demo tenant is ready")

    print("\n=== SEED COMPLETE ===")
    print(f"Demo tenant ID : {tenant['tenant_id']}")
    print(f"Demo URL       : {args.saro_url}/demo")
    print(f"Login email    : {demo_email}")
    if running_in_public_ci():
        print("Login password : <redacted — this is a public repo's Actions log>")
        print(
            "                 Set DEMO_USER_PASSWORD as a repo secret for a "
            "stable value, or read it from .env.demo / Fly secrets."
        )
    else:
        print(f"Login password : {demo_password}")
    print("Token/.env     : .env.demo")
    print("Next step      : Add SARO_DEMO_TENANT_ID to GitHub / Fly.io secrets")


if __name__ == "__main__":
    main()
