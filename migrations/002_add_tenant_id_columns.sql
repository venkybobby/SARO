-- Add tenant_id to all tenant-scoped tables for RLS
ALTER TABLE audits ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
ALTER TABLE scan_reports ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
ALTER TABLE audit_traces ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id_rls UUID REFERENCES tenants(id);

-- Backfill from existing relationships
UPDATE audits a SET tenant_id = (SELECT u.tenant_id FROM users u WHERE u.id = a.user_id) WHERE tenant_id IS NULL;
UPDATE audit_traces at SET tenant_id = (SELECT a.tenant_id FROM audits a WHERE a.id = at.audit_id) WHERE tenant_id IS NULL;
