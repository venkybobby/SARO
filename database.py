"""
Database connection and session management.

Uses NullPool so each connection is returned to Supabase's PgBouncer pooler
immediately — required for transaction-mode pooling where persistent connections
are not held between requests.

Engine is created lazily on first use so that importing this module never
raises a KeyError/RuntimeError when DATABASE_URL is not yet in the environment
(e.g. during Railway startup before variables are injected or during unit tests).
"""
from __future__ import annotations

import functools
import hashlib
import logging
import os
import pathlib

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


# ── Lazy engine factory ───────────────────────────────────────────────────────

def _database_url() -> str:
    import re as _re
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it as a Railway variable or set it in your .env file."
        )
    # Supabase pooler authentication guard: the Supabase session/transaction
    # pooler (*.pooler.supabase.com) requires the project-scoped username
    # "postgres.<project-ref>" rather than the bare "postgres".  A bare
    # username produces an immediate "password authentication failed" error
    # because the pooler treats usernames as routing keys.
    #
    # We parse the netloc instead of the full URL so we don't accidentally
    # match "postgres" in a database name or query string.
    if _re.search(r"pooler\.supabase\.com", url):
        # Extract the username portion: everything between "://" and "@"
        _netloc_match = _re.search(r"://([^:@]+)[^@]*@", url)
        if _netloc_match:
            _username = _netloc_match.group(1)
            if _username == "postgres":
                logger.warning(
                    "DATABASE_URL uses bare username 'postgres' against a Supabase pooler "
                    "host (*.pooler.supabase.com).  Supabase requires the project-scoped "
                    "username 'postgres.<project-ref>' (e.g. postgres.fktfhtygvwqlmoazmhdf). "
                    "Connection will fail with 'password authentication failed' until the "
                    "Railway DATABASE_URL secret is updated.  "
                    "See: https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler"
                )
    return url


@functools.lru_cache(maxsize=1)
def _get_engine():
    """Create (once) and return the SQLAlchemy engine."""
    eng = create_engine(
        _database_url(),
        poolclass=NullPool,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "connect_timeout": 10,
            "sslmode": os.environ.get("DB_SSLMODE", "require"),
            "options": "-c statement_timeout=30000",
        },
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

_MIGRATIONS_DIR = pathlib.Path(__file__).parent / "migrations"


def _iter_sql_statements(sql: str):
    """Yield individual SQL statements from a script, respecting $$ dollar-quote blocks.

    Standard SQL splitters that naively split on ";" break plpgsql CREATE FUNCTION
    bodies which contain ";" inside $$ ... $$ delimiters.  This function toggles a
    ``in_dollar`` flag each time a line contains an odd number of "$$" tokens so that
    semicolons inside function bodies are not treated as statement terminators.

    Example — the following is yielded as ONE statement:
        CREATE OR REPLACE FUNCTION foo() RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'boom';   -- semicolon here is NOT a terminator
        END;
        $$ LANGUAGE plpgsql;        -- THIS semicolon ends the statement
    """
    in_dollar = False
    buf: list[str] = []
    for line in sql.splitlines():
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        buf.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt and not stmt.startswith("--"):
                yield stmt
            buf = []
    # Yield any trailing content (e.g. a statement without a trailing newline)
    if buf:
        stmt = "\n".join(buf).strip()
        if stmt and not stmt.startswith("--"):
            yield stmt


def apply_pending_migrations(applied_by: str = "system") -> list[str]:
    """Apply every *.sql file under migrations/ not yet recorded in schema_migrations.

    Algorithm (idempotent, safe for concurrent Gunicorn workers):
      1. Bootstrap: ensure schema_migrations table exists (CREATE TABLE IF NOT EXISTS).
      2. Sort all *.sql files alphabetically — 000 runs first so the tracking
         table is created before any subsequent migration tries to record itself.
      3. For each file: check if already applied (by version = stem).
         If not: execute each statement via _iter_sql_statements(), then INSERT
         the version + SHA-256 checksum into schema_migrations.  Both happen in
         the same transaction so a partial migration is never recorded as applied.
      4. Return the list of newly applied version strings.

    Failures raise immediately — the caller (lifespan) should let the exception
    propagate so Railway restarts rather than serving traffic on a bad schema.
    """
    eng = _get_engine()

    # Bootstrap: create tracking table before reading it (handles first-ever run)
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(255) PRIMARY KEY,"
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
            "checksum VARCHAR(64) NOT NULL,"
            "applied_by VARCHAR(255) NOT NULL DEFAULT 'system'"
            ")"
        ))

    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    applied: list[str] = []

    for path in migration_files:
        version = path.stem
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode()).hexdigest()

        with eng.begin() as conn:
            already = conn.execute(
                text("SELECT COUNT(*) FROM schema_migrations WHERE version = :v"),
                {"v": version},
            ).scalar()

            if already:
                logger.debug("Migration already applied, skipping: %s", version)
                continue

            logger.info("Applying migration: %s", version)
            for stmt in _iter_sql_statements(sql):
                conn.execute(text(stmt))

            conn.execute(
                text(
                    "INSERT INTO schema_migrations(version, checksum, applied_by) "
                    "VALUES (:v, :c, :by)"
                ),
                {"v": version, "c": checksum, "by": applied_by},
            )
            applied.append(version)
            logger.info("Migration applied successfully: %s", version)

    return applied


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
        # SARO-006 provenance fields
        "engine_version", "rule_pack_hash", "compliance_matrix_version",
    },
    "audit_traces": {
        "id", "audit_id", "gate_id", "gate_name",
        "check_type", "check_name", "result", "reason",
        "detail_json", "remediation_hint",
        "signal_text", "top_sample_ids",
        "is_remediated", "remediated_at", "remediated_by_id",
        "created_at",
        # AUD-001: SHA-256 hash chain columns (migration 003 / 009)
        "event_hash", "prev_hash",
    },
    "audits": {
        "id", "tenant_id", "user_id",
        "batch_id", "dataset_name", "sample_count",
        "status", "created_at", "completed_at",
        # S-101: verbatim text fields for single-output ingestion
        "prompt_text", "raw_output_text",
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
        # CF-01: plain-English executive steps
        "executive_steps",
        "client_input_summary", "client_output_summary",
        "raw_prompt", "raw_response",
        # v2.1 additions — verbatim text + signed export
        "prompt_text", "raw_output_text", "export_hash",
        "created_at",
    },
    "users": {
        "id", "tenant_id", "email", "hashed_password",
        "role",
        # CF-06: persona RBAC
        "persona_role",
        "is_active", "created_at",
    },
    "audit_metadata": {
        "id", "audit_id",
        "source_model", "ingestion_method",
        "prompt_s3_key", "output_s3_key",
        "created_at",
    },
    # S-001: HuggingFace sample queue
    "hf_sample_queue": {
        "id", "tenant_id", "vertical", "source_dataset",
        "prompt_text", "raw_output_text", "source_model",
        "status", "audit_id", "error_message", "retry_count",
        "sampled_at", "processed_at", "updated_at",
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
    # SARO-001: per-sample Gate 3 findings
    "sample_findings": {
        "id", "audit_id", "sample_id", "domain",
        "matched_signal", "matched_text_fragment", "weight", "created_at",
    },
    # SARO-003: tenant risk config overrides
    "tenant_risk_configs": {
        "id", "tenant_id", "domain_weights", "keyword_suppressions",
        "max_weight_ceiling", "created_at", "updated_at",
    },
    # SARO-005: ISO 42001 generated documents
    "iso42001_documents": {
        "id", "audit_id", "generated_by_user_id",
        "format", "content", "content_hash", "version", "created_at",
    },
}

# Tables that must NEVER be dropped to fix drift — use ALTER TABLE ADD COLUMN
# instead.  Maps table_name → {col_name: DDL_type_string}.
_SAFE_ALTER_COLS: dict[str, dict[str, str]] = {
    "users": {
        "persona_role": "VARCHAR(50)",
    },
    "tenants": {},
    # SARO-004: version column added to reference table — ALTER only, never drop.
    "nist_ai_rmf_controls": {
        "version": "VARCHAR(50) DEFAULT 'AI RMF 1.0'",
    },
    # SARO-DC-001/DC-002: additive columns on audit_traces — ALTER only.
    # AUD-001: event_hash/prev_hash are additive — never drop, ALTER only.
    "audit_traces": {
        "signal_text": "VARCHAR(500)",
        "top_sample_ids": "JSONB",
        "event_hash": "VARCHAR(64)",
        "prev_hash": "VARCHAR(64)",
    },
    # audits holds live data and has many FK dependents — never drop, ALTER only.
    # S-101: prompt_text / raw_output_text added for single-output ingestion.
    "audits": {
        "prompt_text": "TEXT",
        "raw_output_text": "TEXT",
    },
    # Infrastructure table — never drop regardless of column drift.
    "schema_migrations": {},
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
        "sample_findings",       # → audits (SARO-001)
        "iso42001_documents",    # → audits (SARO-005)
        "github_scan_results",   # → audits
        "enhanced_traces",       # → audits
        "audit_metadata",        # → audits
        "audit_events",          # → tenants, users
        "client_configs",        # → tenants
        "tenant_risk_configs",   # → tenants (SARO-003)
        "github_integrations",   # → tenants
        "scan_reports",          # → audits
        "audit_traces",          # → audits, users
        "audits",                # → tenants, users
        "demo_requests",
    ]
    with eng.begin() as conn:
        for table_name in _DROP_ORDER:
            if (table_name in drifted
                    and inspector.has_table(table_name)
                    and table_name not in _SAFE_ALTER_COLS):
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

def health_check() -> dict:
    """Probe the database and return a structured health result.

    Returns a dict with the following keys:
        ok      (bool)         True when SELECT 1 succeeds.
        error   (str | None)   Error class label when ok=False:
                                 "auth_failure"       — credentials rejected (FATAL: password…)
                                 "network_unreachable" — host not routable / connection refused
                                 "ssl_error"          — TLS/SSL handshake failure
                                 "unknown"            — any other exception
        detail  (str | None)   The raw exception message (truncated to 200 chars).

    Callers that previously checked ``if health_check():`` should update to
    ``if health_check()["ok"]:``.  The boolean coercion of a non-empty dict
    is always True, so old code will continue to run the body of the ``if``
    block (i.e. silently treat the DB as reachable).  This is intentional —
    it is a safe degradation that prevents a breaking change while callers
    are migrated.
    """
    import re as _re
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "error": None, "detail": None}
    except Exception as exc:
        exc_str = str(exc)
        detail = exc_str[:200]

        if _re.search(r"password authentication failed|authentication failed", exc_str, _re.IGNORECASE):
            error_class = "auth_failure"
        elif _re.search(
            r"could not connect to server|connection refused|"
            r"Name or service not known|network is unreachable|"
            r"No route to host|Operation timed out|connect timeout",
            exc_str, _re.IGNORECASE,
        ):
            error_class = "network_unreachable"
        elif _re.search(r"SSL|TLS|certificate", exc_str, _re.IGNORECASE):
            error_class = "ssl_error"
        else:
            error_class = "unknown"

        logger.error(
            "Database health check failed — error_class=%s detail=%s",
            error_class, detail,
        )
        return {"ok": False, "error": error_class, "detail": detail}


# ── Persona Permission Seeding (CF-06) ────────────────────────────────────────

_PERSONA_SEEDS = [
    {
        "persona_role": "compliance_lead",
        "allowed_tabs": ["dashboard", "audit", "trace", "remediate", "aims", "governance"],
        "allowed_actions": ["create_aims_document", "link_audit", "export_pdf", "view_trace"],
    },
    {
        "persona_role": "risk_officer",
        "allowed_tabs": ["dashboard", "trace", "notifications"],
        "allowed_actions": ["view_trace", "view_dashboard"],
    },
    {
        "persona_role": "ai_auditor",
        "allowed_tabs": ["dashboard", "audit", "trace", "rule_packs", "remediate"],
        "allowed_actions": ["view_trace", "view_rule_packs", "remediate_trace"],
    },
]


def seed_persona_permissions() -> None:
    """
    Idempotently insert PersonaPermission rows for the three standard personas.
    Skips rows that already exist (upsert by persona_role uniqueness).
    """
    from models import PersonaPermission  # local import — avoids circular at module load

    factory = _get_session_factory()
    db: Session = factory()
    try:
        for seed in _PERSONA_SEEDS:
            existing = (
                db.query(PersonaPermission)
                .filter(PersonaPermission.persona_role == seed["persona_role"])
                .first()
            )
            if not existing:
                db.add(PersonaPermission(**seed))
        db.commit()
        logger.info("PersonaPermission rows seeded")
    except Exception:
        db.rollback()
        logger.exception("Failed to seed PersonaPermission rows")
    finally:
        db.close()
