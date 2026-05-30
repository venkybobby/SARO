-- Migration 000: create schema_migrations tracking table.
--
-- This file is processed FIRST (alphabetical sort) by apply_pending_migrations()
-- and by the CI migrate job.  It bootstraps the tracking table itself uses —
-- i.e. the table is created here and then this file is immediately recorded
-- in it, so subsequent runs skip it.
--
-- Safe to re-run: every statement uses IF NOT EXISTS / CREATE OR REPLACE.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(255) PRIMARY KEY,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    checksum    VARCHAR(64)  NOT NULL,
    applied_by  VARCHAR(255) NOT NULL DEFAULT 'system'
);

-- Prevent UPDATE or DELETE on migration records (same immutability principle
-- as audit_traces — once applied, a migration record must not be altered).
CREATE OR REPLACE FUNCTION prevent_migration_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'schema_migrations records are immutable — version % cannot be %',
        OLD.version, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lock_schema_migrations ON schema_migrations;
CREATE TRIGGER trg_lock_schema_migrations
    BEFORE UPDATE OR DELETE ON schema_migrations
    FOR EACH ROW EXECUTE FUNCTION prevent_migration_modification();

COMMENT ON TABLE schema_migrations IS
    'Tracks applied database migrations for SARO. '
    'Populated by apply_pending_migrations() (startup) and the CI migrate job. '
    'Records are immutable by trigger.';
