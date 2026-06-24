-- STORY-401 (Epic 14): per-policy trigger configuration.
-- The spine the governance-runtime router (STORY-402) dispatches on. Tenant-scoped,
-- many policies per tenant. Cross-field validation (block needs budget+timeout,
-- sample needs rate, mirror rejects all three) is enforced app-layer in
-- schemas.validate_trigger_config; the CHECK constraints below guard enum membership.
--
-- NOTE: on the app-startup path create_all() builds this table from the ORM first,
-- so CREATE TABLE IF NOT EXISTS no-ops there; the ALTER/CREATE POLICY/INDEX
-- statements still apply RLS + indexes to the existing table (mirrors migration 024).
-- The RLS policy is for schema parity only — like every SARO table it is inert at
-- runtime (nothing sets app.current_tenant); app-layer filtering is the enforcement.

CREATE TABLE IF NOT EXISTS policies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name                VARCHAR(500) NOT NULL,
    -- Safe default for any backfilled row is 'mirror' with null budget/timeout/rate (AC-6).
    trigger_mode        VARCHAR(10) NOT NULL DEFAULT 'mirror'
                            CHECK (trigger_mode IN ('block', 'mirror', 'sample')),
    latency_budget_ms   INTEGER,
    on_timeout          VARCHAR(10) CHECK (on_timeout IN ('open', 'closed')),
    sample_rate         DOUBLE PRECISION CHECK (sample_rate IS NULL OR (sample_rate >= 0 AND sample_rate <= 1)),
    -- Monotonic; bumps on any trigger-config change (AC-7). Starts at 1.
    policy_version      INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);

ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policies ON policies;
CREATE POLICY tenant_isolation_policies ON policies
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE INDEX IF NOT EXISTS idx_policies_tenant ON policies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_policies_trigger_mode ON policies(trigger_mode);
