-- SAR-013: AI System Inventory (EU AI Act Art. 49)
-- CRITICAL: eu_ai_act_risk_tier is a HUMAN governance decision (Art. 14).
-- The audit engine MUST NEVER set this field automatically.

CREATE TABLE IF NOT EXISTS ai_systems (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name                  VARCHAR(500) NOT NULL,
    description           TEXT,
    system_owner          VARCHAR(320),
    purpose               TEXT,
    deployment_context    VARCHAR(255),
    -- HUMAN DECISION ONLY: 'unacceptable' | 'high' | 'limited' | 'minimal'
    eu_ai_act_risk_tier   VARCHAR(20),
    last_audit_date       TIMESTAMPTZ,
    current_risk_score    INTEGER,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS system_audits (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_id   UUID NOT NULL REFERENCES ai_systems(id) ON DELETE CASCADE,
    audit_id    UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    linked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(system_id, audit_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_systems_tenant_id ON ai_systems(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_systems_risk_tier ON ai_systems(eu_ai_act_risk_tier);
CREATE INDEX IF NOT EXISTS idx_system_audits_system_id ON system_audits(system_id);
CREATE INDEX IF NOT EXISTS idx_system_audits_audit_id ON system_audits(audit_id);
