-- SARO_AIInsights_Stories (STORY-002): persist reviewer decisions on AI insights.
-- Insights themselves are derived read-only at request time (routers/insights.py);
-- only the accept / snooze / dismiss decision is stored. Absence of a row = "active".
CREATE TABLE IF NOT EXISTS insight_actions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    audit_id    UUID NOT NULL UNIQUE REFERENCES audits(id) ON DELETE CASCADE,
    -- "accepted" | "snoozed" | "dismissed" (absence of a row = "active")
    status      VARCHAR(20) NOT NULL
                CHECK (status IN ('accepted', 'snoozed', 'dismissed')),
    acted_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Tenant isolation, same posture as the other tenant-scoped tables.
ALTER TABLE insight_actions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_insight_actions ON insight_actions;
CREATE POLICY tenant_isolation_insight_actions ON insight_actions
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE INDEX IF NOT EXISTS idx_insight_actions_tenant_id ON insight_actions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_insight_actions_audit_id ON insight_actions(audit_id);

-- Auto-update updated_at on change (last-write-wins semantics).
CREATE OR REPLACE FUNCTION update_insight_actions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_insight_actions_updated_at ON insight_actions;
CREATE TRIGGER trg_insight_actions_updated_at
    BEFORE UPDATE ON insight_actions
    FOR EACH ROW EXECUTE FUNCTION update_insight_actions_updated_at();
