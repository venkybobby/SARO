-- Migration 028: Rule-Pack Versioning — Immutable Snapshots (STORY-RPV-001)
--
-- Creates rule_pack_snapshots: a versioned, hash-chained, append-only record of
-- the rule-pack state in force at publish time. Historical attestations pin to a
-- snapshot (STORY-RPV-002) so the exact criteria for any past evaluation are
-- reproducible even though SARO retains zero payload content.
--
-- Immutability strategy (mirrors the EVF split, migration 012):
--   * application layer  — services/rule_pack_snapshot_service.py guards writes
--     (unit-testable on the SQLite test harness, which cannot run plpgsql triggers)
--   * database trigger   — defense-in-depth on real Postgres: no UPDATE/DELETE
--     of any snapshot row is permitted once inserted (publish-on-create model).
--
-- Hash chain: record_hash = SHA-256(canonical_payload + prev_hash), identical
-- discipline to services/hash_chain_service.compute_event_hash. content_hash is
-- computed over the canonical serialization of every included rule row so a later
-- mutation of the working tables is detectable by diff, and tampering with a
-- snapshot row itself breaks the chain from that version forward.
--
-- Safe to re-run: all DDL uses IF NOT EXISTS / OR REPLACE.
-- Refs: STORY-RPV-001 | Gap #1 (radar scan #1, 2026-07-04)

CREATE TABLE IF NOT EXISTS rule_pack_snapshots (
    id                 UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    -- Semantic version, strictly increasing across published snapshots.
    version            VARCHAR(50)  NOT NULL UNIQUE,
    -- SHA-256 over the canonical serialization of every included rule row.
    content_hash       VARCHAR(64)  NOT NULL,
    -- Hash chain over immutable snapshot fields (prev_hash of the prior version).
    prev_hash          VARCHAR(64),
    record_hash        VARCHAR(64)  NOT NULL,
    -- Per-framework included row-id manifest + per-row hash (JSON), NOT full text.
    -- Shape: {"eu_ai_act_rules": {"12": "<rowhash>", ...}, "governance_rules": {...}}
    snapshot_manifest  JSONB        NOT NULL,
    -- Per-framework included row counts, e.g. {"eu_ai_act_rules": 17, ...}.
    framework_counts   JSONB        NOT NULL,
    -- TRUE when LEGACY_UNREVIEWED / status-less rows were included under the
    -- SARO_SNAPSHOT_INCLUDE_LEGACY flag; caveat carries the disclosure text.
    includes_legacy    BOOLEAN      NOT NULL DEFAULT FALSE,
    caveat             TEXT,
    publisher_user_id  UUID         REFERENCES users(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Immutability trigger — publish-on-create, append-only (no UPDATE or DELETE).
CREATE OR REPLACE FUNCTION rule_pack_snapshots_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'rule_pack_snapshots rows are immutable once published — version % cannot be %',
        OLD.version, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rule_pack_snapshots_immutable ON rule_pack_snapshots;
CREATE TRIGGER trg_rule_pack_snapshots_immutable
    BEFORE UPDATE OR DELETE ON rule_pack_snapshots
    FOR EACH ROW EXECUTE FUNCTION rule_pack_snapshots_prevent_modification();

CREATE INDEX IF NOT EXISTS ix_rule_pack_snapshots_created_at
    ON rule_pack_snapshots (created_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS ix_rule_pack_snapshots_record_hash
    ON rule_pack_snapshots (record_hash);

COMMENT ON TABLE rule_pack_snapshots IS
    'Immutable, hash-chained rule-pack version snapshots (STORY-RPV-001). '
    'Publish-on-create; UPDATE/DELETE rejected by trigger. record_hash chains to '
    'the prior version; content_hash covers the canonical serialization of every '
    'included rule row. Evidence records pin version + content_hash (STORY-RPV-002).';
