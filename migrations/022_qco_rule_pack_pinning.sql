-- Migration 022: PT-001 — pin QCO records to the rule-pack hash they were
-- reviewed against, and store the SME findings summary.
--
-- Both columns are informational (NOT part of the record_hash payload), so the
-- existing QCO hash chain remains valid. A QCO whose rule_pack_hash differs from
-- the current engine rule-pack hash no longer validates the active rule packs
-- (see services/evf_qco_service.qco_rule_pack_is_current).
--
-- ADD COLUMN … IF NOT EXISTS so the migration is idempotent.

ALTER TABLE evf_qco_registry
  ADD COLUMN IF NOT EXISTS rule_pack_hash VARCHAR(64);

ALTER TABLE evf_qco_registry
  ADD COLUMN IF NOT EXISTS findings_summary TEXT;
