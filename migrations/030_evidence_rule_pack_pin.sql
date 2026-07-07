-- Migration 030: Attestation evidence pins rule-pack version (STORY-RPV-002)
--
-- Adds the criteria pin to the evidence store and the full-content store to the
-- snapshot so any historical attestation can reproduce the EXACT rule text it was
-- evaluated against — the only link between an attestation and its criteria under
-- SARO's zero-payload-retention posture.
--
-- 1. grc_evidence_records: rule_pack_version_id + rule_pack_content_hash. These are
--    folded into the record's own content_hash / chain (see grc/evidence.py
--    _PAYLOAD_FIELDS) so the pin is tamper-evident (AC-1). Pre-existing rows keep
--    NULL, rendered "PRE-VERSIONING" — never backfilled with a guess (AC-4).
-- 2. rule_pack_snapshots: snapshot_content holds the frozen full rule rows
--    ({table:{id:{fields}}}) so reproduction returns exact text after the working
--    copy mutates (AC-3). RPV-001's content_hash/manifest are unchanged.
--
-- Idempotent (ADD COLUMN IF NOT EXISTS). Refs: STORY-RPV-002 | Gap #1.

ALTER TABLE grc_evidence_records
    ADD COLUMN IF NOT EXISTS rule_pack_version_id   VARCHAR(50),
    ADD COLUMN IF NOT EXISTS rule_pack_content_hash VARCHAR(64);

ALTER TABLE rule_pack_snapshots
    ADD COLUMN IF NOT EXISTS snapshot_content JSONB;

COMMENT ON COLUMN grc_evidence_records.rule_pack_version_id IS
    'Rule-pack snapshot version in force when this evidence was captured (STORY-RPV-002). '
    'NULL = PRE-VERSIONING (record predates versioning); never backfilled.';
COMMENT ON COLUMN rule_pack_snapshots.snapshot_content IS
    'Frozen full rule rows {table:{id:{fields}}} for exact criteria reproduction (STORY-RPV-002).';
