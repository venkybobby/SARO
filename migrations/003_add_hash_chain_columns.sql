-- Epic 1: Add tamper-evident hash chain columns to audit_traces
ALTER TABLE audit_traces ADD COLUMN IF NOT EXISTS prev_hash VARCHAR(64);
ALTER TABLE audit_traces ADD COLUMN IF NOT EXISTS event_hash VARCHAR(64);

-- Index for efficient chain traversal
CREATE INDEX IF NOT EXISTS idx_audit_traces_audit_id_created
  ON audit_traces (audit_id, created_at ASC);

-- DB trigger to prevent UPDATE/DELETE on audit_traces
CREATE OR REPLACE FUNCTION prevent_audit_trace_modification()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_traces records are immutable — tampering detected (operation: %)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_update_audit_traces ON audit_traces;
CREATE TRIGGER trg_prevent_update_audit_traces
  BEFORE UPDATE ON audit_traces
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_trace_modification();

DROP TRIGGER IF EXISTS trg_prevent_delete_audit_traces ON audit_traces;
CREATE TRIGGER trg_prevent_delete_audit_traces
  BEFORE DELETE ON audit_traces
  FOR EACH ROW EXECUTE FUNCTION prevent_audit_trace_modification();
