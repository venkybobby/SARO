-- Migration 037: Per-tenant cross-account client log source config (STORY-408)
--
-- Binds a tenant to exactly one client-account Bedrock log source (bucket +
-- prefix + assumed-role parameters). SARO never stores client AWS credentials —
-- only the parameters needed to assume a client-provisioned, read-only IAM role
-- via STS AssumeRole. external_id is a confused-deputy defense SARO itself
-- generates; it is not an AWS credential but is still tenant-isolated like any
-- other sensitive per-tenant config.

CREATE TABLE IF NOT EXISTS tenant_log_source_configs (
    id           UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id    UUID         NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    role_arn     VARCHAR(255) NOT NULL,
    external_id  VARCHAR(255) NOT NULL,
    bucket       VARCHAR(255) NOT NULL,
    prefix       VARCHAR(500) NOT NULL DEFAULT '',
    region       VARCHAR(50)  NOT NULL,
    kms_key_arn  VARCHAR(255),
    enabled      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ
);

-- Tenant isolation (STORY-TEN-001 AC-1 convention).
DO $$
BEGIN
    ALTER TABLE tenant_log_source_configs ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation_tenant_log_source_configs ON tenant_log_source_configs;
    CREATE POLICY tenant_isolation_tenant_log_source_configs ON tenant_log_source_configs
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
END $$;
