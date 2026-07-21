-- 039_tenant_rule_pack_pin.sql — STORY-376: per-tenant rule-pack version pinning.
--
-- Lets a subscribing tenant pin a specific published rule-pack version.
-- Deprecation and rollback are re-pinning, never deletion: a published snapshot
-- is immutable (INV-7, migration 028 trigger) and is never removed, so a tenant
-- moving away from a version leaves it — and every attestation produced under
-- it — intact and reproducible.
--
-- One active pin per tenant (UNIQUE tenant_id). A tenant with no pin row uses
-- the platform's latest published version by default.

CREATE TABLE IF NOT EXISTS tenant_rule_pack_pins (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    version           VARCHAR(50) NOT NULL,
    pinned_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ
);

COMMENT ON TABLE tenant_rule_pack_pins IS
    'STORY-376: tenant -> published rule-pack version. Deprecation = re-pin, never delete.';

-- Tenant isolation (STORY-TEN-001 AC-1 convention) — a tenant may only see its
-- own pin. The pinned VERSION is global/immutable, but which tenant pins what
-- is tenant-private.
DO $$
BEGIN
    ALTER TABLE tenant_rule_pack_pins ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation_tenant_rule_pack_pins ON tenant_rule_pack_pins;
    CREATE POLICY tenant_isolation_tenant_rule_pack_pins ON tenant_rule_pack_pins
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
END $$;
