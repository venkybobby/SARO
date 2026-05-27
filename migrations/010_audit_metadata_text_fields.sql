-- migrations/010_audit_metadata_text_fields.sql
-- S-101: Add prompt_text / raw_output_text to audit_metadata for ingest endpoint
-- These columns hold verbatim text for single-output ingests (≤50KB stored inline;
-- larger values use the existing prompt_s3_key / output_s3_key S3 path).
-- ROLLBACK: ALTER TABLE audit_metadata DROP COLUMN IF EXISTS prompt_text, DROP COLUMN IF EXISTS raw_output_text;

BEGIN;

ALTER TABLE audit_metadata
    ADD COLUMN IF NOT EXISTS prompt_text     TEXT,
    ADD COLUMN IF NOT EXISTS raw_output_text TEXT;

COMMIT;
