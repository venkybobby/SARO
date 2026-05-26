BEGIN;

CREATE TYPE hf_sample_status AS ENUM
    ('pending', 'processing', 'processed', 'failed');

CREATE TABLE IF NOT EXISTS hf_sample_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    vertical         VARCHAR(50)  NOT NULL,
    source_dataset   VARCHAR(200) NOT NULL,
    prompt_text      TEXT NOT NULL,
    raw_output_text  TEXT NOT NULL,
    source_model     VARCHAR(100) NOT NULL DEFAULT 'unknown',
    status           hf_sample_status NOT NULL DEFAULT 'pending',
    audit_id         UUID REFERENCES audits(id) ON DELETE SET NULL,
    error_message    TEXT,
    retry_count      INTEGER NOT NULL DEFAULT 0,
    sampled_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at     TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hf_queue_tenant_status
    ON hf_sample_queue(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_hf_queue_vertical
    ON hf_sample_queue(vertical);
CREATE INDEX IF NOT EXISTS idx_hf_queue_updated_at
    ON hf_sample_queue(updated_at);

CREATE OR REPLACE FUNCTION cleanup_hf_sample_queue()
RETURNS void AS $$
BEGIN
    DELETE FROM hf_sample_queue
    WHERE status = 'processed'
      AND processed_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

COMMIT;
-- ROLLBACK: DROP TABLE IF EXISTS hf_sample_queue; DROP TYPE IF EXISTS hf_sample_status;
