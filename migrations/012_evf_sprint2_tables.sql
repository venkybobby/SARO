-- Migration 012: EVF Sprint 2 — QCO Registry + Publication Audit Trail
--
-- Creates two tables for the External SME Validation Framework (SARO-RISK-001):
--   evf_qco_registry       — versioned, immutable-once-published QCO records (FR-EVF-10)
--   evf_publication_events — append-only hash-chained claim publication log (FR-EVF-20/21)
--
-- Immutability strategy:
--   evf_qco_registry      — enforced at application layer (evf_qco_service.py);
--                           no DB trigger (records may be updated while draft)
--   evf_publication_events — enforced by DB trigger (append-only, no UPDATE/DELETE)
--
-- Safe to re-run: all DDL uses IF NOT EXISTS.
-- Refs: FR-EVF-10, FR-EVF-20, FR-EVF-21 | SARO-RISK-001

-- ─────────────────────────────────────────────────────────────────────────────
-- Table 1: evf_qco_registry
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evf_qco_registry (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    -- Reference number format: SARO-QCO-{FRAMEWORK}-{YYYY}-{SEQ:03d}
    qco_reference_number    VARCHAR(100) NOT NULL UNIQUE,
    framework_covered       VARCHAR(50)  NOT NULL,
    saro_version_assessed   VARCHAR(50)  NOT NULL,
    sme_firm                VARCHAR(255) NOT NULL,
    sme_credential          VARCHAR(255),
    -- Set at publish time; expiry_date must be <= issue_date + 365 days (FR-EVF-13)
    issue_date              DATE,
    expiry_date             DATE,
    scope_boundary_summary  TEXT,
    -- Access-controlled document location + SHA-256 integrity fingerprint
    document_url            TEXT,
    document_sha256         VARCHAR(64),
    engagement_id           UUID         REFERENCES evf_sme_engagements(id) ON DELETE SET NULL,
    -- Publication state: once published=TRUE the record is immutable
    published               BOOLEAN      NOT NULL DEFAULT FALSE,
    published_at            TIMESTAMPTZ,
    published_by_user_id    UUID         REFERENCES users(id) ON DELETE SET NULL,
    -- Hash chain fields (populated at publish time)
    prev_hash               VARCHAR(64),
    record_hash             VARCHAR(64),
    -- Renewal link: renews_qco_id → the QCO this one renews
    --               superseded_by_qco_id → the renewal QCO that replaced this one
    renews_qco_id           UUID         REFERENCES evf_qco_registry(id) ON DELETE SET NULL,
    superseded_by_qco_id    UUID         REFERENCES evf_qco_registry(id) ON DELETE SET NULL,
    created_by_user_id      UUID         REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,

    CONSTRAINT evf_qco_framework_check
        CHECK (framework_covered IN ('EU_AI_ACT', 'NIST_AI_RMF', 'AIGP', 'ISO_42001')),
    CONSTRAINT evf_qco_expiry_after_issue
        CHECK (expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date),
    CONSTRAINT evf_qco_expiry_max_validity
        CHECK (expiry_date IS NULL OR issue_date IS NULL
               OR expiry_date <= issue_date + INTERVAL '365 days')
);

-- Auto-update updated_at for draft records
CREATE OR REPLACE FUNCTION evf_qco_registry_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evf_qco_registry_updated_at ON evf_qco_registry;
CREATE TRIGGER trg_evf_qco_registry_updated_at
    BEFORE UPDATE ON evf_qco_registry
    FOR EACH ROW EXECUTE FUNCTION evf_qco_registry_set_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS ix_evf_qco_framework_expiry
    ON evf_qco_registry (framework_covered, expiry_date);

CREATE INDEX IF NOT EXISTS ix_evf_qco_published
    ON evf_qco_registry (published);

CREATE INDEX IF NOT EXISTS ix_evf_qco_engagement_id
    ON evf_qco_registry (engagement_id);

CREATE INDEX IF NOT EXISTS ix_evf_qco_record_hash
    ON evf_qco_registry (record_hash);

COMMENT ON TABLE evf_qco_registry IS
    'Versioned QCO registry. Records are immutable once published=TRUE (application-enforced). '
    'Hash chain (prev_hash + record_hash) covers all immutable fields. '
    'FR-EVF-10 | SARO-RISK-001';

-- ─────────────────────────────────────────────────────────────────────────────
-- Table 2: evf_publication_events
-- ─────────────────────────────────────────────────────────────────────────────
-- Append-only log. Rows must never be updated or deleted (trigger-enforced).
-- Five required fields (AC-21a): timestamp, artefact_identifier,
--   qco_reference_number, publisher_user_id, distribution_channel.
-- Hash chain: event_hash = SHA-256(payload + prev_hash).

CREATE TABLE IF NOT EXISTS evf_publication_events (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    -- Required field 1: UTC timestamp (server-set at write time)
    timestamp               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Required field 2: identifies the artefact that triggered the publication
    artefact_identifier     VARCHAR(500) NOT NULL,
    -- Required field 3: soft FK to evf_qco_registry (string for resilience)
    qco_reference_number    VARCHAR(100) NOT NULL,
    -- Required field 4: publishing user identity
    publisher_user_id       UUID         REFERENCES users(id) ON DELETE SET NULL,
    -- Required field 5: distribution channel
    -- Allowed: API | REPORT_PDF | DASHBOARD | SALES_DECK | WEBSITE | PARTNER_PORTAL
    distribution_channel    VARCHAR(50)  NOT NULL,
    -- Hash chain
    prev_hash               VARCHAR(64),
    event_hash              VARCHAR(64),
    -- Idempotency key — deduplicate retries (unique, nullable)
    idempotency_key         VARCHAR(255) UNIQUE,

    CONSTRAINT evf_pub_channel_check
        CHECK (distribution_channel IN (
            'API', 'REPORT_PDF', 'DASHBOARD', 'SALES_DECK', 'WEBSITE', 'PARTNER_PORTAL'
        ))
);

-- Immutability trigger — append-only (no UPDATE or DELETE permitted)
CREATE OR REPLACE FUNCTION evf_publication_events_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'evf_publication_events rows are append-only — id % cannot be %',
        OLD.id, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evf_pub_events_immutable ON evf_publication_events;
CREATE TRIGGER trg_evf_pub_events_immutable
    BEFORE UPDATE OR DELETE ON evf_publication_events
    FOR EACH ROW EXECUTE FUNCTION evf_publication_events_prevent_modification();

-- Indexes
CREATE INDEX IF NOT EXISTS ix_evf_pub_events_timestamp
    ON evf_publication_events (timestamp ASC, id ASC);

CREATE INDEX IF NOT EXISTS ix_evf_pub_events_qco_ref
    ON evf_publication_events (qco_reference_number);

CREATE INDEX IF NOT EXISTS ix_evf_pub_events_event_hash
    ON evf_publication_events (event_hash);

CREATE INDEX IF NOT EXISTS ix_evf_pub_events_channel
    ON evf_publication_events (distribution_channel);

COMMENT ON TABLE evf_publication_events IS
    'Append-only hash-chained log of every external compliance claim publication. '
    'Immutability enforced by trigger. '
    'Five required fields (AC-21a): timestamp, artefact_identifier, '
    'qco_reference_number, publisher_user_id, distribution_channel. '
    'FR-EVF-20, FR-EVF-21 | SARO-RISK-001';
