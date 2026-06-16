-- STORY-305: append-only, tamper-evident evidence store for the GRC platform.
-- Hash-chained provenance records; append-only enforced at the DB layer.

CREATE TABLE IF NOT EXISTS grc_evidence_records (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    output_id          VARCHAR(255) NOT NULL,
    system_id          VARCHAR(255),
    -- Per-tenant monotonic chain order (independent of timestamp resolution).
    seq                BIGINT NOT NULL DEFAULT 1,
    -- Provenance payload (hashed into content_hash).
    model_version      VARCHAR(255),
    prompt             TEXT,
    inputs             JSONB,
    retrieved_context  TEXT,
    decision           TEXT,
    confidence         DOUBLE PRECISION,
    consumer           VARCHAR(255),
    captured_at        TIMESTAMPTZ,
    -- Hash chain.
    content_hash       VARCHAR(64) NOT NULL,
    prev_chain_hash    VARCHAR(64) NOT NULL,
    chain_hash         VARCHAR(64) NOT NULL,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE grc_evidence_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_grc_evidence_records ON grc_evidence_records;
CREATE POLICY tenant_isolation_grc_evidence_records ON grc_evidence_records
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE INDEX IF NOT EXISTS idx_grc_evidence_tenant ON grc_evidence_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_grc_evidence_output ON grc_evidence_records(output_id);
CREATE INDEX IF NOT EXISTS idx_grc_evidence_created ON grc_evidence_records(tenant_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_grc_evidence_seq ON grc_evidence_records(tenant_id, seq);

-- Append-only: block UPDATE and DELETE at the DB layer. INSERT only.
CREATE OR REPLACE FUNCTION prevent_grc_evidence_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'grc_evidence_records is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_grc_evidence_no_mutation ON grc_evidence_records;
CREATE TRIGGER trg_grc_evidence_no_mutation
    BEFORE UPDATE OR DELETE ON grc_evidence_records
    FOR EACH ROW EXECUTE FUNCTION prevent_grc_evidence_mutation();
