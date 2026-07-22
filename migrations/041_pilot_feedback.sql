-- 041_pilot_feedback.sql — STORY-382: structured in-product pilot feedback.
--
-- A feedback form needs free text, so INV-2 here is MITIGATED, not eliminated:
-- a visible no-PHI notice (API contract), a length cap (body VARCHAR(4000)),
-- and this table is EXCLUDED from evidence exports so a pilot's confusing-UI
-- note never surfaces in an auditor's evidence pack.

CREATE TABLE IF NOT EXISTS pilot_feedback (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    screen        VARCHAR(64) NOT NULL,
    category      VARCHAR(20) NOT NULL,   -- bug | gap | confusing | feature
    severity      VARCHAR(20) NOT NULL,   -- low | medium | high
    body          VARCHAR(4000) NOT NULL, -- length-capped free text
    triage_status VARCHAR(20) NOT NULL DEFAULT 'new',
    story_id      VARCHAR(64),
    triage_note   VARCHAR(500),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pilot_feedback_tenant ON pilot_feedback (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_pilot_feedback_triage ON pilot_feedback (triage_status);

COMMENT ON TABLE pilot_feedback IS
    'STORY-382: in-product pilot feedback. Free text is mitigated (no-PHI notice + cap + export-excluded), not by-construction.';

-- Tenant isolation (STORY-TEN-001 convention): a tenant sees only its own feedback.
DO $$
BEGIN
    ALTER TABLE pilot_feedback ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation_pilot_feedback ON pilot_feedback;
    CREATE POLICY tenant_isolation_pilot_feedback ON pilot_feedback
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));
END $$;
