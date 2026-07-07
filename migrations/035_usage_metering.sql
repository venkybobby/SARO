-- Migration 035: PHI-free usage metering (STORY-MTR-001)
--
-- Per-tenant, per-period consumption meters that are PHI-free BY CONSTRUCTION: every
-- meter record carries only a tenant id, a closed-vocabulary meter key, a period
-- bucket, a count, and dimension tags from a closed vocabulary — no free-text fields,
-- so payload/PII leakage is structurally impossible (INV-2 by construction).
--
--   usage_meters             — the counters (idempotent upsert on a unique key).
--   usage_meter_idempotency  — dedup log so retried increments never double-count.
--   usage_statements         — immutable per-period usage artifacts (evidence too).
--
-- Idempotent DDL. Refs: STORY-MTR-001 | evf_expiry_notifications idempotency pattern.

CREATE TABLE IF NOT EXISTS usage_meters (
    id              UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id       UUID        NOT NULL,
    meter_key       VARCHAR(50) NOT NULL,
    period_bucket   VARCHAR(20) NOT NULL,          -- UTC period, e.g. '2026-07'
    -- Closed-vocabulary dimension tags (gate_id, vertical, adapter_id, outcome). No free text.
    dimensions      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    dimensions_hash VARCHAR(64) NOT NULL,          -- for the unique key (canonical dims)
    count           BIGINT      NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ,
    CONSTRAINT ux_usage_meters_key UNIQUE (tenant_id, meter_key, period_bucket, dimensions_hash)
);
CREATE INDEX IF NOT EXISTS ix_usage_meters_tenant_period ON usage_meters (tenant_id, period_bucket);

-- Global dedup log. Idempotency keys MUST be globally unique (e.g. 'evidence:{uuid}')
-- so one tenant's key can never suppress another tenant's increment; no tenant_id here.
CREATE TABLE IF NOT EXISTS usage_meter_idempotency (
    idempotency_key VARCHAR(255) NOT NULL PRIMARY KEY,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Immutable per-period usage statements (evidence: disputes are audits).
CREATE TABLE IF NOT EXISTS usage_statements (
    id            UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id     UUID        NOT NULL,
    period_bucket VARCHAR(20) NOT NULL,
    totals        JSONB       NOT NULL,
    content_hash  VARCHAR(64) NOT NULL,
    issued_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_usage_statements UNIQUE (tenant_id, period_bucket)
);

CREATE OR REPLACE FUNCTION usage_statements_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'usage_statements are immutable once issued — id % cannot be %', OLD.id, TG_OP;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_usage_statements_immutable ON usage_statements;
CREATE TRIGGER trg_usage_statements_immutable
    BEFORE UPDATE OR DELETE ON usage_statements
    FOR EACH ROW EXECUTE FUNCTION usage_statements_prevent_modification();

-- Tenant isolation (STORY-TEN-001 AC-1: no tenant-scoped table with zero policies).
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['usage_meters', 'usage_statements'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON %I', t, t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_%I ON %I '
            'USING (tenant_id::text = current_setting(''app.current_tenant'', true)) '
            'WITH CHECK (tenant_id::text = current_setting(''app.current_tenant'', true))',
            t, t);
    END LOOP;
END $$;
