-- 040_product_events.sql — STORY-381: first-party, PHI-free product analytics.
--
-- Events carry a closed-vocabulary name, a tenant id, a timestamp, and a
-- closed-vocabulary properties bag of bounded scalars. No free-text column
-- exists, so payload/PII cannot be stored (INV-2 by construction). Individual
-- user identity is deliberately absent — tenant id is the only identifier.
--
-- First-party: this table lives in SARO's own Supabase. No third-party analytics
-- SaaS (that would be a sub-processor and a security-review question, Epic 15).

CREATE TABLE IF NOT EXISTS product_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_name  VARCHAR(64) NOT NULL,
    properties  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_product_events_tenant_time
    ON product_events (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_product_events_name_time
    ON product_events (event_name, created_at);

COMMENT ON TABLE product_events IS
    'STORY-381: first-party PHI-free product analytics. Closed vocab, no free text.';

-- Tenant isolation (STORY-TEN-001 convention): a tenant sees only its own events.
DO $$
BEGIN
    ALTER TABLE product_events ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation_product_events ON product_events;
    CREATE POLICY tenant_isolation_product_events ON product_events
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
END $$;
