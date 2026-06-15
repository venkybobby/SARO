-- Migration 023: S-1106 — audit trail for incident is_fixed changes.
--
-- The corpus exposed only a bare is_fixed boolean with no provenance: who marked
-- an incident resolved, and when. FB-019 ("is_fixed boolean has no audit trail").
-- Add fixed_by + fixed_at so any flip of is_fixed records both. The single write
-- path is services.incident_service.set_incident_fixed().
--
-- ADD COLUMN … IF NOT EXISTS so the migration is idempotent.

ALTER TABLE ai_incidents
  ADD COLUMN IF NOT EXISTS fixed_by VARCHAR(255);

ALTER TABLE ai_incidents
  ADD COLUMN IF NOT EXISTS fixed_at TIMESTAMPTZ;
