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
import sys
import time

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

from database import create_all_tables, ensure_app_schema, engine, health_check
from routers.auth import router as auth_router
from routers.auth import tenants_router
from routers.clients import audit_events_router, router as clients_router
from routers.dashboard import router as dashboard_router
from routers.github_integration import router as github_router
from routers.output_audit import router as output_audit_router
from routers.demo import router as demo_router
from routers.reports import router as reports_router
from routers.scan import router as scan_router
from routers.traces import router as traces_router
from routers.audit_chain import router as audit_chain_router
from routers.governance import router as governance_router
from routers.risk_dashboard import router as risk_dashboard_router
from routers.trace_view import router as trace_view_router
from routers.rule_packs import router as rule_packs_router
from routers.sso import router as sso_router
from routers.remediation import router as remediation_router
from routers.compliance_hub import router as compliance_hub_router
from routers.risk_config import router as risk_config_router
from routers.compliance_matrix import router as compliance_matrix_router
from routers.notifications import router as notifications_router
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

    if not health_check():
        # Log a warning but do NOT crash — the process must bind its port so
        # Railway's health check can pass.  Individual requests will fail with
        # 503 only if the DB is still unreachable when they arrive, which is
        # a much better failure mode than never starting at all.
        logger.warning(
            "Database unreachable at startup. Check DATABASE_URL secret in Railway. "
            "API will return 503 on DB-dependent endpoints until the DB is reachable."
        )
    else:
        # 1. Self-heal audits/scan_reports if their columns are out of date
        #    (drops + recreates them when any column is missing).
        ensure_app_schema()
        # 2. Create any other tables that don't exist yet (reference tables, etc.)
        create_all_tables()
        logger.info("Database schema synchronised")

    yield

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
    # Open CORS — accept any origin; API security is enforced via JWT
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,   # required when allow_origins=["*"]
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
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
app.include_router(clients_router)
app.include_router(audit_events_router)
app.include_router(dashboard_router)
app.include_router(output_audit_router)
app.include_router(github_router)
app.include_router(audit_chain_router)
app.include_router(governance_router)
app.include_router(risk_dashboard_router)
app.include_router(trace_view_router)
app.include_router(rule_packs_router)
app.include_router(sso_router)
app.include_router(remediation_router)
app.include_router(compliance_hub_router)
app.include_router(risk_config_router)
app.include_router(compliance_matrix_router)
app.include_router(notifications_router)


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health", tags=["ops"])
def health() -> dict:
    """
    Railway / load-balancer health probe.

    Also returns bootstrap_needed=True when the users table is empty so the
    frontend can display a first-run setup prompt instead of a plain login form.
    """
    from database import get_db  # local import to avoid circular at module level
    from models import User

    db_ok = health_check()
    bootstrap_needed: bool | None = None
    if db_ok:
        try:
            db = next(get_db())
            try:
                bootstrap_needed = db.query(User).count() == 0
            finally:
                db.close()
        except Exception:
            bootstrap_needed = None  # DB readable but query failed

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "bootstrap_needed": bootstrap_needed,
        "version": app.version,
    }


@app.get("/", tags=["ops"])
def root() -> dict:
    return {"app": "SARO", "version": app.version, "docs": "/docs"}
