"""Migration 009: backfill hash chain columns on audit_traces.

Migration 003 (003_add_hash_chain_columns.sql) already added event_hash
and prev_hash as nullable VARCHAR(64) columns.  This migration:

  1. Ensures the columns exist (idempotent — 003 may already have run).
  2. Backfills any NULL event_hash rows with the LEGACY_PRE_CHAIN sentinel
     so verify_chain() can distinguish genuinely unverifiable historical
     records from real hash failures.
  3. Adds a composite index (audit_id, created_at) for efficient chain
     traversal in the verify-chain endpoint.

Operational note: run this migration BEFORE deploying the AUD-001 application
code (or during a maintenance window), so that no concurrent inserts race
with the backfill UPDATE.  The ADD COLUMN operations are idempotent.

Downgrade: intentionally raises — resetting sentinel values is destructive
and loses the ability to distinguish legacy from new records.  Remove the
guard manually in a test environment if needed.
"""
from database import engine
from services.hash_chain_service import LEGACY_SENTINEL
from sqlalchemy import text


def upgrade():
    with engine.connect() as conn:
        # Idempotent column additions (no-op if 003 already ran)
        conn.execute(text(
            "ALTER TABLE audit_traces ADD COLUMN IF NOT EXISTS event_hash VARCHAR(64)"
        ))
        conn.execute(text(
            "ALTER TABLE audit_traces ADD COLUMN IF NOT EXISTS prev_hash VARCHAR(64)"
        ))
        # Backfill: rows written before AUD-001 wiring get the legacy sentinel.
        # Bound parameter avoids f-string SQL injection pattern.
        result = conn.execute(
            text("UPDATE audit_traces SET event_hash = :sentinel WHERE event_hash IS NULL"),
            {"sentinel": LEGACY_SENTINEL},
        )
        backfilled = result.rowcount
        # Composite index for efficient chain traversal (audit_id + created_at order)
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_audit_traces_audit_created "
            "ON audit_traces (audit_id, created_at ASC, id ASC)"
        ))
        # Lookup index for chain-membership queries
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_audit_traces_event_hash "
            "ON audit_traces (event_hash)"
        ))
        conn.commit()
    print(
        f"Migration 009 applied: {backfilled} NULL event_hash rows backfilled "
        f"with '{LEGACY_SENTINEL}' sentinel"
    )


def downgrade():
    raise RuntimeError(
        "Migration 009 downgrade is destructive: it resets event_hash sentinel values "
        "to NULL, making all pre-AUD-001 records indistinguishable from post-AUD-001 "
        "records with missing hashes.  Remove this guard manually in a test environment "
        "if you are certain no chain-enabled rows exist."
    )


if __name__ == "__main__":
    upgrade()
