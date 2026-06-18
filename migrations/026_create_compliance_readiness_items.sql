-- CHUB-004: per-tenant Compliance Hub readiness checklist state.
-- The item catalog is code-defined (services/readiness_service.py); this table
-- stores only the toggled `completed` state of *manual* items, scoped per tenant.
-- Derived items are never written here (computed from their real source at read).
CREATE TABLE IF NOT EXISTS compliance_readiness_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    item_key    VARCHAR(64) NOT NULL,
    completed   BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_readiness_tenant_item UNIQUE (tenant_id, item_key)
);

-- Tenant isolation, same posture as the other tenant-scoped tables
-- (migrations/021_create_insight_actions.sql). App-layer filters in
-- services/readiness_service.py are the primary enforcement; RLS is
-- defense-in-depth, consistent with docs/ARCHITECTURE.md.
ALTER TABLE compliance_readiness_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_compliance_readiness_items ON compliance_readiness_items;
CREATE POLICY tenant_isolation_compliance_readiness_items ON compliance_readiness_items
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE INDEX IF NOT EXISTS idx_compliance_readiness_items_tenant_id
    ON compliance_readiness_items(tenant_id);

-- Auto-update updated_at on change (last-write-wins semantics).
CREATE OR REPLACE FUNCTION update_compliance_readiness_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compliance_readiness_items_updated_at ON compliance_readiness_items;
CREATE TRIGGER trg_compliance_readiness_items_updated_at
    BEFORE UPDATE ON compliance_readiness_items
    FOR EACH ROW EXECUTE FUNCTION update_compliance_readiness_items_updated_at();
