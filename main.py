"""
SARO FastAPI Application Entry Point
=====================================
Smart AI Risk Orchestrator — production-grade FastAPI backend.

Startup (standalone repo / Railway):
    uvicorn main:app --host 0.0.0.0 --port $PORT

Environment variables (see .env.example):
    DATABASE_URL, JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    MIN_BATCH_SAMPLES, INCIDENT_TOP_K, BAYESIAN_PRIOR_ALPHA, CONFIDENCE_THRESHOLD
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
import time
from datetime import datetime

# Ensure the repo root is on sys.path so that sibling modules (database,
# models, auth, engine, schemas) and the routers sub-package are importable
# regardless of whether uvicorn is invoked as `uvicorn main:app` (Railway /
# standalone) or `uvicorn backend.main:app` (monorepo local dev).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import apply_pending_migrations, create_all_tables, ensure_app_schema, engine, health_check, seed_persona_permissions, verify_migration_objects
from routers.aims import router as aims_router
from routers.auth import router as auth_router
from routers.auth import tenants_router
from routers.clients import audit_events_router, router as clients_router
from routers.dashboard import router as dashboard_router
from routers.github_integration import router as github_router
from routers.governance_trust import router as governance_trust_router
from routers.output_audit import router as output_audit_router
from routers.demo import router as demo_router
from routers.reports import router as reports_router
from routers.scan import router as scan_router
from routers.trace_export import router as trace_export_router
from routers.traces import router as traces_router
from routers.audit_chain import router as audit_chain_router
from routers.governance import router as governance_router
from routers.risk_dashboard import router as risk_dashboard_router
from routers.trace_view import router as trace_view_router
from routers.rule_packs import router as rule_packs_router, _alias_router as rule_packs_alias_router
from routers.sso import router as sso_router
from routers.remediation import router as remediation_router
from routers.compliance_hub import router as compliance_hub_router
from routers.risk_config import router as risk_config_router
from routers.compliance_matrix import router as compliance_matrix_router
from routers.notifications import router as notifications_router
from routers.engine_status import router as engine_status_router
from routers.hf_processor import router as hf_processor_router
from routers.ingest import router as ingest_router
from routers.fe_dashboard import router as fe_dashboard_router
from routers.evf import router as evf_router
from routers.evf_sprint2 import router as evf_sprint2_router
from routers.evf_sprint3 import router as evf_sprint3_router
from routers.evaluations import router as evaluations_router
from routers.systems import router as systems_router
from routers.controls import router as controls_router
from routers.onboarding import router as onboarding_router
from routers.risks import router as risks_router
from routers.insights import router as insights_router
from middleware.rate_limiter import RateLimiterMiddleware

# ── Structured logging setup ──────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: DB schema creation ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    On startup: create any missing tables (idempotent — existing tables are
    never dropped).  On shutdown: dispose the engine connection pool.
    """
    logger.info("SARO starting up — environment=%s", os.environ.get("ENVIRONMENT", "development"))

    # SARO-H11 / G-07: an open CORS policy (allow_origins=["*"]) is acceptable
    # in dev but must not go unnoticed in production — flag it loudly so it
    # gets caught in deploy logs even though the app continues to start.
    if os.environ.get("ENVIRONMENT", "development") == "production":
        if not os.environ.get("ALLOWED_ORIGINS", "").strip():
            logger.critical(
                "SECURITY: ALLOWED_ORIGINS is not set in production. "
                "CORS is open to all origins (allow_origins=['*']). "
                "Set ALLOWED_ORIGINS=https://saro.vercel.app in Railway."
            )

    _db_health = health_check()
    if not _db_health["ok"]:
        # Log a warning but do NOT crash — the process must bind its port so
        # Railway's health check can pass.  Individual requests will fail with
        # 503 only if the DB is still unreachable when they arrive, which is
        # a much better failure mode than never starting at all.
        _db_err = _db_health.get("error", "unknown")
        _db_detail = _db_health.get("detail", "")
        if _db_err == "auth_failure":
            logger.error(
                "Database authentication failed at startup (error_class=auth_failure). "
                "Supabase pooler 'Tenant or user not found' means the DATABASE_URL username "
                "is wrong or missing the project-ref suffix. "
                "Required format: postgres://<user>.<project-ref>:<password>@*.pooler.supabase.com:5432/<db>. "
                "Update DATABASE_URL in Railway → Variables. "
                "detail=%s", _db_detail,
            )
        else:
            logger.warning(
                "Database unreachable at startup (error_class=%s). "
                "Check DATABASE_URL secret in Railway. "
                "API will return 503 on DB-dependent endpoints until the DB is reachable. "
                "detail=%s", _db_err, _db_detail,
            )
    else:
        # 1. Self-heal audits/scan_reports if their columns are out of date
        #    (drops + recreates them when any column is missing).
        ensure_app_schema()
        # 2. Create any other tables that don't exist yet (reference tables, etc.)
        create_all_tables()
        # 3. Apply all pending SQL migrations (idempotent — tracked in schema_migrations).
        #    apply_pending_migrations() executes migrations/000, 001, 002, … in order,
        #    skipping any already recorded in schema_migrations.  This is the primary
        #    fix for psycopg2.errors.UndefinedColumn when a migration file ships with
        #    the code but was never applied to the production database.
        try:
            _newly_applied = apply_pending_migrations(applied_by="startup")
            if _newly_applied:
                logger.info("SQL migrations applied at startup: %s", _newly_applied)
            else:
                logger.info("All SQL migrations already applied — schema up to date")
        except Exception as _exc:
            # A migration failure means the schema is in an unknown state.
            # Log the error clearly and re-raise so Railway restarts the container
            # rather than serving traffic on a mismatched schema.
            logger.error(
                "FATAL: SQL migration failed at startup — refusing to serve traffic "
                "to prevent schema mismatch errors: %s", _exc
            )
            raise
        # 3b. Assert that DB objects created by migrations actually exist.
        #     Raises RuntimeError (→ hard startup fail) if any are absent.
        verify_migration_objects()
        # 3c. Python migrations not covered by apply_pending_migrations() (no .sql file).
        #     Run via importlib — each upgrade() must be idempotent.
        for _py_migration in (
            ("migration_008", "008_remediation_note.py", "remediation_note column"),
            ("migration_009", "009_hash_chain_columns.py", "hash chain backfill"),
        ):
            _mig_name, _mig_file, _mig_desc = _py_migration
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location(
                    _mig_name,
                    pathlib.Path(__file__).parent / "migrations" / _mig_file,
                )
                _mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
                _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
                _mod.upgrade()
                logger.info("Python migration %s (%s) applied", _mig_name, _mig_desc)
            except Exception as _exc:
                logger.warning("Python migration %s skipped (non-fatal): %s", _mig_name, _exc)
        # 4. Seed persona permissions (idempotent — skips existing rows)
        seed_persona_permissions()
        # 4b. SAR-010: seed unified control library (idempotent — skips existing controls)
        try:
            from scripts.seed_control_library import seed_controls  # type: ignore[attr-defined]
            seeded = seed_controls()
            if seeded:
                logger.info("Control library seeded: %d controls added", seeded)
            else:
                logger.info("Control library already seeded — no changes")
        except Exception as _exc:
            logger.warning("Control library seed skipped (non-fatal): %s", _exc)
        logger.info("Database schema synchronised")
        # SPEC-E3: Initialise SARoEngine singleton with TF-IDF index
        try:
            from database import get_db
            from engine import SARoEngine
            db = next(get_db())
            try:
                app.state.engine = SARoEngine(db)
                app.state.engine_index_count = len(app.state.engine._incidents)
                app.state.engine_index_built_at = datetime.utcnow().isoformat()
                logger.info(
                    "SARoEngine singleton ready — %d incidents indexed",
                    app.state.engine_index_count,
                )
            finally:
                db.close()
        except Exception as exc:
            logger.warning("SARoEngine singleton init failed (degraded mode): %s", exc)
            app.state.engine = None
            app.state.engine_index_count = 0
            app.state.engine_index_built_at = None
        # 5. Seed demo data when requested (idempotent — checks for existing demo tenant)
        if os.environ.get("SEED_DEMO_DATA", "").lower() in ("1", "true", "yes"):
            try:
                from scripts.seed_demo import seed as _seed_demo
                _seed_demo()
                logger.info("Demo data seeding complete")
            except Exception:
                logger.exception("Demo data seeding failed (non-fatal — continuing startup)")

    # Start EVF daily expiry scan background task (FR-EVF-13)
    import asyncio
    from services.evf_expiry_service import run_daily_expiry_scan
    _evf_expiry_task = asyncio.create_task(run_daily_expiry_scan())
    logger.info("EVF daily QCO expiry scan background task started")

    yield

    # Cancel background task on shutdown
    _evf_expiry_task.cancel()
    try:
        await _evf_expiry_task
    except asyncio.CancelledError:
        pass

    engine.dispose()
    logger.info("SARO shut down cleanly")


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title="SARO — Smart AI Risk Orchestrator",
    description=(
        "Production-grade AI risk auditing platform. "
        "4-gate pipeline: Data Quality → Fairness → Risk Classification → Compliance Mapping. "
        "Bayesian risk forecasting · MIT coverage · Incident matching · Fixed-delta."
    ),
    version="8.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Default to "*" so the Railway frontend can reach the API without needing
# ALLOWED_ORIGINS pre-configured.  Set ALLOWED_ORIGINS to a comma-separated
# list of specific origins to lock down in production.
# Note: allow_credentials=True is incompatible with allow_origins=["*"], so
# we use allow_origin_regex instead when the wildcard is active.

# LIVE-003: Set ALLOWED_ORIGINS in Railway/Fly.io secrets to lock CORS to the
# frontend origin (e.g. https://sarofrontend.fly.dev).  Without it, the wildcard
# branch activates: allow_credentials=False, which blocks cross-origin requests
# that carry an Authorization header AND rely on credentials:include behaviour.
# Required secret: ALLOWED_ORIGINS=https://sarofrontend.fly.dev
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _raw_origins.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _raw_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Open CORS — accept any origin; API security is enforced via JWT.
    # WARNING: allow_credentials must be False when allow_origins=["*"].
    # Frontend must use Authorization: Bearer header (not cookies) in this mode.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(RateLimiterMiddleware)


# ── Request timing middleware ─────────────────────────────────────────────────


@app.middleware("http")
async def add_timing_header(request: Request, call_next) -> Response:  # noqa: ANN001
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


# ── Global exception handler ──────────────────────────────────────────────────

import re as _re

# Parses "column audit_traces.event_hash does not exist"
_UNDEFINED_COL_RE = _re.compile(
    r'column\s+"?(\w+)"?\."?(\w+)"?\s+does not exist', _re.IGNORECASE
)
# Parses 'relation "foo" does not exist'
_UNDEFINED_TABLE_RE = _re.compile(
    r'relation\s+"?(\w+)"?\s+does not exist', _re.IGNORECASE
)

_slog = structlog.get_logger("saro.exceptions")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    exc_str = str(exc)
    log_fields: dict = {
        "method": request.method,
        "path": request.url.path,
        "error_class": type(exc).__name__,
    }

    # DB connectivity failures must return 503, not 500, so clients and load
    # balancers can distinguish a config/infra error from an application bug.
    import re as _re
    if _re.search(
        r"Tenant or user not found|password authentication failed|"
        r"could not connect to server|connection refused|connect timeout",
        exc_str, _re.IGNORECASE,
    ):
        _slog.error("db_connection_error_on_request", exc_info=True, **log_fields)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database unavailable — check DATABASE_URL in Railway Variables.",
                "type": "db_connection_error",
            },
        )

    col_match = _UNDEFINED_COL_RE.search(exc_str)
    tbl_match = _UNDEFINED_TABLE_RE.search(exc_str)

    if col_match:
        table_name, col_name = col_match.group(1), col_match.group(2)
        log_fields.update({
            "error_type": "missing_column",
            "table": table_name,
            "column": col_name,
            "migration_hint": (
                f"Column '{col_name}' missing from '{table_name}'. "
                f"Check migrations/ for an ALTER TABLE ADD COLUMN statement. "
                f"Apply the migration and restart, or verify apply_pending_migrations() ran."
            ),
        })
    elif tbl_match:
        log_fields.update({
            "error_type": "missing_table",
            "table": tbl_match.group(1),
            "migration_hint": (
                f"Table '{tbl_match.group(1)}' does not exist. "
                f"Check migrations/ for a CREATE TABLE statement and restart."
            ),
        })
    else:
        log_fields["error_type"] = "unhandled_exception"

    _slog.error("unhandled_request_exception", exc_info=True, **log_fields)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(scan_router)
app.include_router(reports_router)
app.include_router(demo_router)
app.include_router(traces_router)
app.include_router(trace_export_router)
app.include_router(clients_router)
app.include_router(audit_events_router)
app.include_router(dashboard_router)
app.include_router(output_audit_router)
app.include_router(github_router)
app.include_router(aims_router)
app.include_router(governance_trust_router)
app.include_router(audit_chain_router)
app.include_router(governance_router)
app.include_router(risk_dashboard_router)
app.include_router(trace_view_router)
app.include_router(rule_packs_router)
app.include_router(rule_packs_alias_router)
app.include_router(sso_router)
app.include_router(remediation_router)
app.include_router(compliance_hub_router)
app.include_router(risk_config_router)
app.include_router(compliance_matrix_router)
app.include_router(notifications_router)
app.include_router(engine_status_router)
app.include_router(hf_processor_router)
app.include_router(ingest_router)
app.include_router(fe_dashboard_router)
app.include_router(evf_router)
app.include_router(evf_sprint2_router)
app.include_router(evf_sprint3_router)
app.include_router(evaluations_router)
app.include_router(systems_router)
app.include_router(controls_router)
app.include_router(onboarding_router)
app.include_router(risks_router)
app.include_router(insights_router)


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health", tags=["ops"])
def health() -> JSONResponse:
    """
    Railway / load-balancer health probe.

    Returns HTTP 200 when healthy, HTTP 503 when:
      - The database is unreachable, OR
      - a migration shipped in this image is not applied (schema mismatch —
        Railway will restart the container).  Orphan/extra rows in
        schema_migrations (from migrations removed/renamed in a later image)
        are harmless and do NOT trip the gate.

    Fields:
      status                "ok" | "degraded" | "schema_mismatch"
      database              "ok" | "unreachable"
      db_error              null | "auth_failure" | "network_unreachable" | "ssl_error" | "unknown"
      schema_version        highest applied migration version in schema_migrations
      schema_ok             true when every migration on disk is applied
      highest_migration     highest *.sql filename stem found under migrations/
      missing_migrations    on-disk migration stems not yet applied (empty when schema_ok)
      version               app version string
    """
    from database import get_db
    from models import User
    from sqlalchemy import text as _t

    _db_result = health_check()
    db_ok: bool = _db_result["ok"]
    db_error: str | None = _db_result.get("error")
    bootstrap_needed: bool | None = None
    schema_version: str | None = None
    schema_ok: bool | None = None

    # Migrations this image ships: the full set of stems, plus the highest one.
    _mdir = pathlib.Path(__file__).parent / "migrations"
    _disk_stems = [p.stem for p in _mdir.glob("*.sql")]
    _disk = sorted(_disk_stems)
    highest_on_disk: str | None = _disk[-1] if _disk else None
    missing_migrations: list[str] | None = None

    if db_ok:
        try:
            db = next(get_db())
            try:
                bootstrap_needed = db.query(User).count() == 0
                try:
                    _applied = {
                        r[0]
                        for r in db.execute(
                            _t("SELECT version FROM schema_migrations")
                        ).fetchall()
                    }
                    if not _applied:
                        # schema_migrations empty — migrations may still be running
                        # on first boot.  Unknown, not a mismatch.
                        schema_version = None
                        schema_ok = None
                    else:
                        # Report the highest applied version for visibility only.
                        schema_version = max(_applied)
                        # Schema is healthy when every migration shipped in THIS
                        # image has been applied.  Do NOT require max(db)==max(disk):
                        # an orphan row left by a migration that was renamed/removed
                        # in a later image sorts above the highest file on disk and
                        # would otherwise brick the deploy with a silent 503 even
                        # though the schema is fully migrated.  Extra/orphan rows are
                        # harmless; only a genuinely *missing* migration is a mismatch.
                        _missing = [s for s in _disk_stems if s not in _applied]
                        missing_migrations = sorted(_missing)
                        schema_ok = not _missing
                except Exception:
                    # schema_migrations table not yet created (first boot before migrations run)
                    schema_version = None
                    schema_ok = None
            finally:
                db.close()
        except Exception:
            bootstrap_needed = None

    if not db_ok:
        # auth_failure is a config error — restarting cannot fix it.
        # Return HTTP 200 so Railway does NOT roll back the deployment or
        # stop routing traffic; the db_error field tells operators what to fix.
        # All other DB failures return 503 so Railway/load-balancers can
        # legitimately restart or route away from a sick instance.
        http_status = 200 if db_error == "auth_failure" else 503
        status = "degraded"
    elif schema_ok is False:
        # Only hard-503 when a migration this image ships is genuinely *not* applied
        # (see missing_migrations).  Orphan/extra rows in schema_migrations do NOT
        # trip this — they are harmless leftovers from removed/renamed migrations.
        # schema_ok=None means migrations haven't recorded yet — return degraded/200 so
        # Railway doesn't restart-loop during the first-boot migration window.
        status, http_status = "schema_mismatch", 503
    elif schema_ok is None and db_ok:
        status, http_status = "degraded", 200
    else:
        status, http_status = "ok", 200

    return JSONResponse(
        status_code=http_status,
        content={
            "status": status,
            "database": "ok" if db_ok else "unreachable",
            "db_error": db_error,
            "schema_version": schema_version,
            "schema_ok": schema_ok,
            "highest_migration": highest_on_disk,
            "missing_migrations": missing_migrations,
            "bootstrap_needed": bootstrap_needed,
            "version": app.version,
        },
    )


@app.get("/", tags=["ops"])
def root() -> dict:
    return {"app": "SARO", "version": app.version, "docs": "/docs"}
