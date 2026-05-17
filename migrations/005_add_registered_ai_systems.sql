-- REM-002: Registered AI systems table for coverage gap analysis
CREATE TABLE IF NOT EXISTS registered_ai_systems (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    vendor      VARCHAR(255),
    owner       VARCHAR(255),
    description TEXT,
    last_audit_date DATE,
    overdue_threshold_days INTEGER NOT NULL DEFAULT 60,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS so each tenant only sees their own systems
ALTER TABLE registered_ai_systems ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_ai_systems ON registered_ai_systems
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- Index for fast tenant + audit date queries
CREATE INDEX IF NOT EXISTS idx_ai_systems_tenant_id ON registered_ai_systems(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_systems_last_audit ON registered_ai_systems(last_audit_date);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_ai_systems_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ai_systems_updated_at ON registered_ai_systems;
CREATE TRIGGER trg_ai_systems_updated_at
    BEFORE UPDATE ON registered_ai_systems
    FOR EACH ROW EXECUTE FUNCTION update_ai_systems_updated_at();
