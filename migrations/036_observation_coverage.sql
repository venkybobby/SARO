-- Migration 036: Observation-gap (coverage) attestations — adapter-independent core (STORY-COV-001)
--
-- Mirror-async means SARO is sometimes blind (adapter outage, lag spike, deploy
-- window). This makes that blindness first-class EVIDENCE instead of a silent gap an
-- examiner reads as dishonesty. De-identified by construction (INV-2): checkpoints and
-- gaps carry only watermark POSITIONS and TIMESTAMPS — never observed content.
--
--   observation_checkpoints  — heartbeat/watermark markers (last-observed position+time).
--   observation_gaps         — first-class gap records with a cause class + watermark delta.
--   observation_lag_samples  — p50/p95/max observation lag per window (measured evidence).
--
-- Scope note: the live Bedrock-adapter heartbeat EMISSION (STORY-406) is deferred; this
-- ships the checkpoint interface + gap/lag/report logic. Idempotent DDL.

CREATE TABLE IF NOT EXISTS observation_checkpoints (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id           UUID        NOT NULL,
    system_id           VARCHAR(255) NOT NULL,
    adapter_id          VARCHAR(255) NOT NULL,
    watermark_position  VARCHAR(255) NOT NULL,     -- source-side position (never content)
    watermark_timestamp TIMESTAMPTZ NOT NULL,      -- source-side time of last observation
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Idempotent checkpoint semantics: a re-read of the same window does not double-record.
    CONSTRAINT ux_observation_checkpoints UNIQUE (tenant_id, system_id, adapter_id, watermark_position)
);
CREATE INDEX IF NOT EXISTS ix_observation_checkpoints_key
    ON observation_checkpoints (tenant_id, system_id, adapter_id, watermark_timestamp DESC);

CREATE TABLE IF NOT EXISTS observation_gaps (
    id               UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id        UUID        NOT NULL,
    system_id        VARCHAR(255) NOT NULL,
    adapter_id       VARCHAR(255) NOT NULL,
    gap_start        TIMESTAMPTZ NOT NULL,
    gap_end          TIMESTAMPTZ,                 -- NULL == ongoing
    -- ADAPTER_FAILURE|SOURCE_UNAVAILABLE|CREDENTIAL_EXPIRY|DEPLOY_WINDOW|LAG_EXCEEDED
    -- |PLANNED_MAINTENANCE|SARO_OUTAGE|UNKNOWN
    cause_class      VARCHAR(40) NOT NULL DEFAULT 'UNKNOWN',
    detection_method VARCHAR(60),
    watermark_start  VARCHAR(255),                -- range of missed source activity (positions only)
    watermark_end    VARCHAR(255),
    duration_seconds BIGINT,
    approver         VARCHAR(255),                -- for PLANNED_MAINTENANCE
    retroactive      BOOLEAN     NOT NULL DEFAULT FALSE,
    -- Evidence hash chain (AC-3): finalized gaps chain per tenant like any attestation.
    prev_hash        VARCHAR(64),
    content_hash     VARCHAR(64),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ,
    CONSTRAINT observation_gaps_cause_check CHECK (cause_class IN (
        'ADAPTER_FAILURE','SOURCE_UNAVAILABLE','CREDENTIAL_EXPIRY','DEPLOY_WINDOW',
        'LAG_EXCEEDED','PLANNED_MAINTENANCE','SARO_OUTAGE','UNKNOWN'))
);
CREATE INDEX IF NOT EXISTS ix_observation_gaps_open
    ON observation_gaps (tenant_id, system_id, adapter_id) WHERE gap_end IS NULL;

CREATE TABLE IF NOT EXISTS observation_lag_samples (
    id            UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id     UUID        NOT NULL,
    system_id     VARCHAR(255) NOT NULL,
    adapter_id    VARCHAR(255) NOT NULL,
    window_bucket VARCHAR(20) NOT NULL,           -- e.g. '2026-07-07T14' (hour)
    p50_ms        DOUBLE PRECISION,
    p95_ms        DOUBLE PRECISION,
    max_ms        DOUBLE PRECISION,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_observation_lag UNIQUE (tenant_id, system_id, adapter_id, window_bucket)
);

-- Tenant isolation (STORY-TEN-001 AC-1).
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['observation_checkpoints','observation_gaps','observation_lag_samples'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON %I', t, t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_%I ON %I '
            'USING (tenant_id::text = current_setting(''app.current_tenant'', true)) '
            'WITH CHECK (tenant_id::text = current_setting(''app.current_tenant'', true))',
            t, t);
    END LOOP;
END $$;
