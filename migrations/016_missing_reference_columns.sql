-- Migration 016: add columns that the ORM models define but the DB is missing
--
-- ai_incidents.is_fixed  — tracks whether an incident was resolved/remediated
-- nist_ai_rmf_controls.function_name — NIST RMF function label (Govern/Map/…)
--
-- Both ADD COLUMN … IF NOT EXISTS so the migration is idempotent.

ALTER TABLE ai_incidents
  ADD COLUMN IF NOT EXISTS is_fixed BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE nist_ai_rmf_controls
  ADD COLUMN IF NOT EXISTS function_name VARCHAR(100);
