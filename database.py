"""
Database connection and session management.

Uses NullPool so each connection is returned to Neon's pooler immediately —
critical for serverless/edge deployments where persistent connections are not
available.

Engine is created lazily on first use so that importing this module never
raises a KeyError/RuntimeError when DATABASE_URL is not yet in the environment
(e.g. during Koyeb startup before secrets are injected or during unit tests).
"""
from __future__ import annotations

import functools
import logging
import os

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


# ── Lazy engine factory ───────────────────────────────────────────────────────

def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it as a Koyeb secret or set it in your .env file."
        )
    return url


@functools.lru_cache(maxsize=1)
def _get_engine():
    """Create (once) and return the SQLAlchemy engine."""
    eng = create_engine(
        _database_url(),
        poolclass=NullPool,
        echo=False,
        connect_args={"connect_timeout": 10},
    )

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_connection, connection_record):  # noqa: ANN001
        logger.debug("New DB connection established")

    return eng


@functools.lru_cache(maxsize=1)
def _get_session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())


# ── Public aliases expected by main.py and models.py ─────────────────────────
# `engine` and `Base` are referenced in main.py as:
#   from database import Base, engine, health_check
# We expose a lazy proxy so the names exist at import time but the real engine
# is only constructed when first accessed.

class _EngineProxy:
    """Thin proxy: attribute access and calls are forwarded to the real engine."""

    def __getattr__(self, name: str):
        return getattr(_get_engine(), name)

    def connect(self, *args, **kwargs):
        return _get_engine().connect(*args, **kwargs)

    def dispose(self, *args, **kwargs):
        return _get_engine().dispose(*args, **kwargs)


engine = _EngineProxy()  # type: ignore[assignment]


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_db():
    """
    FastAPI dependency that yields a scoped SQLAlchemy session.

    The session is closed (and connection returned to the pool) after the
    request completes, whether it succeeded or raised an exception.
    """
    db: Session = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()


# ── Schema helpers ────────────────────────────────────────────────────────────

def create_all_tables() -> None:
    """
    Create all ORM-mapped tables that don't yet exist.

    Passes the real engine directly (not the proxy) to avoid the deprecated
    ``bind=`` keyword argument removed in SQLAlchemy 2.x.
    """
    Base.metadata.create_all(_get_engine())


# ── Schema self-heal ──────────────────────────────────────────────────────────
#
# Problem: SQLAlchemy's create_all() runs CREATE TABLE IF NOT EXISTS.
# It creates tables that don't exist but NEVER alters tables that do.
# Any column added to an ORM model after the table's first creation is
# therefore permanently absent from the live DB, causing ProgrammingError
# on every query that references it.
#
# Previous approach: maintain a static _COLUMN_MIGRATIONS list → fragile,
# requires a code change every time a column is added, easy to miss one.
#
# Current approach: compare the DB's actual column set against the full
# expected column set for each app table. On any mismatch, DROP the table
# and let create_all() recreate it with the current schema. Safe here
# because the audits / scan_reports tables are transient — no successful
# audit has ever been stored (every attempt crashed on the missing columns).
# Reference tables (mit_risks, eu_ai_act_rules, …) are never touched.

# Full expected column sets — must match the Audit / ScanReport ORM models.
# Drop-order matters for FK constraints: dependent table first.
_APP_TABLE_EXPECTED_COLS: dict[str, set[str]] = {
    "scan_reports": {
        "id", "audit_id",
        "mit_coverage_score", "fixed_delta", "overall_risk_score",
        "confidence_score", "report_json", "created_at",
    },
    "audit_traces": {
        "id", "audit_id", "gate_id", "gate_name",
        "check_type", "check_name", "result", "reason",
        "detail_json", "remediation_hint",
        "is_remediated", "remediated_at", "remediated_by_id",
        "created_at",
    },
    "audits": {
        "id", "tenant_id", "user_id",
        "batch_id", "dataset_name", "sample_count",
        "status", "created_at", "completed_at",
    },
    "demo_requests": {
        "id", "first_name", "last_name", "email",
        "contact_number", "company_name", "message",
        "status", "created_at", "updated_at",
    },
    # New tables added in vNext — create_all handles first creation;
    # schema healing triggers drop/recreate only if columns drift.
    "client_configs": {
        "id", "tenant_id", "industry", "size",
        "primary_contact_name", "primary_contact_email",
        "sso_enabled", "idp_provider", "idp_metadata",
        "scim_enabled", "scim_endpoint", "scim_bearer_token_hash",
        "mfa_required", "allow_magic_link_fallback",
        "created_at", "updated_at",
    },
    "audit_events": {
        "id", "tenant_id", "user_id",
        "event_type", "event_data", "created_at",
    },
    "enhanced_traces": {
        "id", "audit_id", "confidence", "model_version",
        "executive_summary", "chain_of_thought",
        "client_input_summary", "client_output_summary",
        "raw_prompt", "raw_response",
        # v2.1 additions — verbatim text + signed export
        "prompt_text", "raw_output_text", "export_hash",
        "created_at",
    },
    "audit_metadata": {
        "id", "audit_id",
        "source_model", "ingestion_method",
        "prompt_s3_key", "output_s3_key",
        "created_at",
    },
    "github_integrations": {
        "id", "tenant_id", "allowed_repos",
        "access_token_hash", "is_active",
        "created_at", "last_scan_at",
    },
    "github_scan_results": {
        "id", "audit_id", "repo_name", "file_path",
        "line_number", "snippet", "correlation_note",
        "finding_domain", "scan_hash", "created_at",
    },
}

# Tables that must NEVER be dropped to fix drift — use ALTER TABLE ADD COLUMN
# instead.  Maps table_name → {col_name: DDL_type_string}.
_SAFE_ALTER_COLS: dict[str, dict[str, str]] = {
    "users": {
        "persona_role": "VARCHAR(50)",
    },
    "tenants": {},
}


def ensure_app_schema() -> None:
    """
    Self-healing schema check for all app tables.

    Algorithm (runs on every startup, completes in < 100 ms when healthy):
      1. For each app table, compare the live DB column names against the
         expected set defined in _APP_TABLE_EXPECTED_COLS.
      2. If any columns are missing, log a WARNING showing which ones are
         absent, then DROP both tables (scan_reports first — it has a FK
         to audits) inside a single transaction.
      3. Call create_all_tables() to recreate the freshly dropped tables
         with the exact schema defined by the current ORM models.
      4. For tables in _SAFE_ALTER_COLS (e.g. users, tenants) that must
         NEVER be dropped, use ALTER TABLE ADD COLUMN IF NOT EXISTS instead.
      5. If every column is present, this function is a no-op.

    This replaces the old _COLUMN_MIGRATIONS static list that required a
    manual code update every time a column was added to an ORM model.
    """
    eng = _get_engine()
    inspector = inspect(eng)

    # Step 1 — detect drift
    drifted: dict[str, set[str]] = {}
    for table_name, expected_cols in _APP_TABLE_EXPECTED_COLS.items():
        if not inspector.has_table(table_name):
            continue  # absent → create_all will create it; no drift to fix
        actual_cols = {c["name"] for c in inspector.get_columns(table_name)}
        missing = expected_cols - actual_cols
        if missing:
            drifted[table_name] = missing

    if not drifted:
        logger.debug("ensure_app_schema: no schema drift detected")
        return

    # Step 2 — report and drop drifted tables
    for table_name, missing_cols in drifted.items():
        logger.warning(
            "Schema drift in table %r — missing columns: %s — dropping for recreation",
            table_name, sorted(missing_cols),
        )

    # Drop in dependency order (most-dependent first to satisfy FK constraints):
    #   enhanced_traces → audits
    #   audit_events    → tenants, users
    #   client_configs  → tenants
    #   scan_reports    → audits
    #   audit_traces    → audits, users
    #   audits          → tenants, users
    _DROP_ORDER = [
        "github_scan_results",   # → audits
        "enhanced_traces",       # → audits
        "audit_metadata",        # → audits
        "audit_events",          # → tenants, users
        "client_configs",        # → tenants
        "github_integrations",   # → tenants
        "scan_reports",          # → audits
        "audit_traces",          # → audits, users
        "audits",                # → tenants, users
        "demo_requests",
    ]
    with eng.begin() as conn:
        for table_name in _DROP_ORDER:
            if table_name in drifted and inspector.has_table(table_name):
                conn.execute(text(f'DROP TABLE "{table_name}"'))
                logger.info("Dropped drifted table: %s", table_name)

    # Step 3 — recreate via create_all (handles both tables atomically)
    create_all_tables()
    logger.info(
        "App tables recreated with current schema (drifted tables: %s)",
        sorted(drifted),
    )

    # Step 4 — safe ALTER TABLE ADD COLUMN for precious tables (users, tenants)
    #           that must never be dropped because they hold live data.
    for table_name, col_defs in _SAFE_ALTER_COLS.items():
        if not col_defs or not inspector.has_table(table_name):
            continue
        actual_cols = {c["name"] for c in inspector.get_columns(table_name)}
        with eng.begin() as conn:
            for col_name, col_type in col_defs.items():
                if col_name not in actual_cols:
                    logger.warning(
                        "Adding missing column %r to %r via ALTER TABLE",
                        col_name, table_name,
                    )
                    conn.execute(
                        text(
                            f'ALTER TABLE "{table_name}" '
                            f'ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}'
                        )
                    )


# ── Health check ──────────────────────────────────────────────────────────────

def health_check() -> bool:
    """Return True if the database is reachable, False otherwise."""
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
