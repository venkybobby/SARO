-- Migration 029: Rule-pack validation_status columns (STORY-RPV-001 / reviewer B1)
--
-- Exports the Supabase-applied migration `radar_scan1_validation_status_columns`
-- (version 20260704194849, applied out-of-band via MCP on 2026-07-04) into the
-- repo migration set so CI-managed schema_migrations and the live DB do not
-- diverge — a fresh deploy or new environment must get these columns from the
-- repo, not only from the live Supabase project.
--
-- These columns back the RPV-001 publish gate (AC-3: only SME_VALIDATED rows are
-- includable) and the CHUB-011 validation-status filtering. Vocabulary:
--   LEGACY_UNREVIEWED | DRAFT_UNVALIDATED | SME_VALIDATED | RETIRED
--
-- Faithful to the live DDL: validation_status is NOT NULL DEFAULT
-- 'LEGACY_UNREVIEWED' so existing rows are provisionally-visible legacy, never a
-- surprise NULL. (The RPV-001 service still fail-closes a NULL to DRAFT as
-- defense in depth against raw inserts that bypass the default.)
--
-- Idempotent (ADD COLUMN IF NOT EXISTS) — safe to re-run and a no-op on the live
-- project that already has these columns.
-- Companion note: the sibling data migration `radar_scan1_rule_pack_delta_data`
-- (the 28 DRAFT / 7 RETIRED row edits) is exported separately under STORY-CHUB-011.

ALTER TABLE eu_ai_act_rules
    ADD COLUMN IF NOT EXISTS validation_status text NOT NULL DEFAULT 'LEGACY_UNREVIEWED',
    ADD COLUMN IF NOT EXISTS validated_by text,
    ADD COLUMN IF NOT EXISTS validated_date date,
    ADD COLUMN IF NOT EXISTS applicability_date date;

ALTER TABLE governance_rules
    ADD COLUMN IF NOT EXISTS validation_status text NOT NULL DEFAULT 'LEGACY_UNREVIEWED',
    ADD COLUMN IF NOT EXISTS validated_by text,
    ADD COLUMN IF NOT EXISTS validated_date date;
