-- Migration 011: add vertical column to audit_metadata
-- GAP-009: enables dashboard vertical filter
BEGIN;

ALTER TABLE audit_metadata
    ADD COLUMN IF NOT EXISTS vertical VARCHAR(50);

COMMIT;
