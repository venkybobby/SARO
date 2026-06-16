-- STORY-301: AI system & agent registry for the GRC audit platform.
-- A dedicated registry (distinct from SAR-013 ai_systems) carrying the richer
-- governance metadata the GRC specs require, with an append-only audit trail.

CREATE TABLE IF NOT EXISTS grc_registry_entries (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entry_type                  VARCHAR(20) NOT NULL DEFAULT 'system'
                                    CHECK (entry_type IN ('system', 'agent')),
    -- Required governance metadata (completeness enforced in app: STORY-302).
    name                        VARCHAR(500) NOT NULL,
    version                     VARCHAR(100),
    owner                       VARCHAR(320),
    purpose                     TEXT,
    data_sources                JSONB,
    model_version               VARCHAR(255),
    lifecycle_stage             VARCHAR(50),
    deployment_status           VARCHAR(50),
    -- Tiering inputs (STORY-303 reads these).
    domain                      VARCHAR(100),
    interacts_with_humans       BOOLEAN,
    makes_autonomous_decisions  BOOLEAN,
    affects_individuals         BOOLEAN,
    -- Tiering outputs (classification suggestion; NOT the legal human-decision tier).
    internal_tier               VARCHAR(20),
    eu_ai_act_category          VARCHAR(20),
    nist_impact_level           VARCHAR(20),
    tiering_rationale           TEXT,
    tiered_at                   TIMESTAMPTZ,
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ,
    created_by_id               UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by_id               UUID REFERENCES users(id) ON DELETE SET NULL
);

ALTER TABLE grc_registry_entries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_grc_registry_entries ON grc_registry_entries;
CREATE POLICY tenant_isolation_grc_registry_entries ON grc_registry_entries
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE INDEX IF NOT EXISTS idx_grc_registry_entries_tenant ON grc_registry_entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_grc_registry_entries_owner ON grc_registry_entries(owner);
CREATE INDEX IF NOT EXISTS idx_grc_registry_entries_tier ON grc_registry_entries(internal_tier);
CREATE INDEX IF NOT EXISTS idx_grc_registry_entries_lifecycle ON grc_registry_entries(lifecycle_stage);


-- Immutable audit trail: who changed what, when. Append-only.
CREATE TABLE IF NOT EXISTS grc_registry_audit (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entry_id      UUID REFERENCES grc_registry_entries(id) ON DELETE SET NULL,
    action        VARCHAR(20) NOT NULL CHECK (action IN ('create', 'update')),
    actor_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_email   VARCHAR(320),
    changes_json  JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE grc_registry_audit ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_grc_registry_audit ON grc_registry_audit;
CREATE POLICY tenant_isolation_grc_registry_audit ON grc_registry_audit
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE INDEX IF NOT EXISTS idx_grc_registry_audit_entry ON grc_registry_audit(entry_id);
CREATE INDEX IF NOT EXISTS idx_grc_registry_audit_tenant ON grc_registry_audit(tenant_id);

-- Append-only enforcement at the DB layer: block UPDATE/DELETE on the trail.
CREATE OR REPLACE FUNCTION prevent_grc_registry_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'grc_registry_audit is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_grc_registry_audit_no_update ON grc_registry_audit;
CREATE TRIGGER trg_grc_registry_audit_no_update
    BEFORE UPDATE OR DELETE ON grc_registry_audit
    FOR EACH ROW EXECUTE FUNCTION prevent_grc_registry_audit_mutation();
