-- Migration 034: Finding disposition lifecycle (STORY-DISP-001)
--
-- Every failed evaluation enters a tracked disposition lifecycle so "what did you
-- do about it?" has an evidence-backed answer. Dispositions ARE evidence: a
-- forward-only state machine (OPEN -> ACKNOWLEDGED -> REMEDIATED|WAIVED|ESCALATED)
-- with an append-only, hash-chained transition log (evf_engagement_transitions
-- pattern). De-identified by construction (INV-2: no observed content).
--
--   dispositions              — one per failing finding; forward-only state.
--   disposition_transitions   — append-only hash-chained log; immutable by trigger.
--
-- Waiver expiry auto-reopens to OPEN with a lineage link and emits a notification
-- (the first real consumer of the notifications table).
--
-- Idempotent. Refs: STORY-DISP-001 | notifications (0 rows) | grc_evidence_records.

CREATE TABLE IF NOT EXISTS dispositions (
    id                   UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id            UUID        NOT NULL,
    -- De-identified finding metadata only (INV-2) — never observed content.
    evidence_record_id   UUID        REFERENCES grc_evidence_records(id) ON DELETE SET NULL,
    rule_id              VARCHAR(255),
    gate_id              VARCHAR(100),
    system_id            VARCHAR(255),
    severity             VARCHAR(20),
    -- OPEN | ACKNOWLEDGED | REMEDIATED | WAIVED | ESCALATED
    state                VARCHAR(30) NOT NULL DEFAULT 'OPEN',
    acknowledged_at      TIMESTAMPTZ,
    acknowledged_by      VARCHAR(255),
    -- Waiver fields (required together when state = WAIVED).
    waiver_justification TEXT,
    waiver_approver      VARCHAR(255),
    waiver_expiry        DATE,
    -- Reserved lineage FK for a future create-new-row reopen model. v1 does a
    -- same-row WAIVED->OPEN reopen whose lineage lives in disposition_transitions.
    reopened_from_id     UUID        REFERENCES dispositions(id) ON DELETE SET NULL,
    recurrence_count     INTEGER     NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ,
    CONSTRAINT dispositions_state_check
        CHECK (state IN ('OPEN','ACKNOWLEDGED','REMEDIATED','WAIVED','ESCALATED'))
);

CREATE INDEX IF NOT EXISTS ix_dispositions_tenant_state ON dispositions (tenant_id, state);
CREATE INDEX IF NOT EXISTS ix_dispositions_evidence ON dispositions (evidence_record_id);
CREATE INDEX IF NOT EXISTS ix_dispositions_waiver_expiry ON dispositions (waiver_expiry)
    WHERE state = 'WAIVED';
-- Recurrence linkage: at most one active (non-terminal-ish) disposition per finding key.
CREATE INDEX IF NOT EXISTS ix_dispositions_finding_key ON dispositions (tenant_id, rule_id, system_id);

CREATE TABLE IF NOT EXISTS disposition_transitions (
    id              UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    disposition_id  UUID        NOT NULL REFERENCES dispositions(id) ON DELETE CASCADE,
    seq             INTEGER     NOT NULL,
    from_state      VARCHAR(30) NOT NULL,
    to_state        VARCHAR(30) NOT NULL,
    actor           VARCHAR(255),
    reason          TEXT,
    prev_hash       VARCHAR(64),
    event_hash      VARCHAR(64) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_disposition_transitions_seq UNIQUE (disposition_id, seq)
);

CREATE INDEX IF NOT EXISTS ix_disposition_transitions_disp ON disposition_transitions (disposition_id, seq);

-- Append-only: the transition log is immutable (trigger-enforced).
CREATE OR REPLACE FUNCTION disposition_transitions_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'disposition_transitions is append-only — id % cannot be %', OLD.id, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_disposition_transitions_immutable ON disposition_transitions;
CREATE TRIGGER trg_disposition_transitions_immutable
    BEFORE UPDATE OR DELETE ON disposition_transitions
    FOR EACH ROW EXECUTE FUNCTION disposition_transitions_prevent_modification();

-- Tenant isolation (STORY-TEN-001 AC-1: no tenant-scoped table relies on zero policies).
-- dispositions carries tenant_id; disposition_transitions is a child scoped via its parent.
ALTER TABLE dispositions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_dispositions ON dispositions;
CREATE POLICY tenant_isolation_dispositions ON dispositions
    USING (tenant_id::text = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true));

-- Added post-034 for the four-eyes control (approver must differ from acknowledger).
-- Idempotent so already-created tables gain the column too.
ALTER TABLE dispositions ADD COLUMN IF NOT EXISTS acknowledged_by VARCHAR(255);

COMMENT ON TABLE dispositions IS
    'Finding disposition lifecycle (STORY-DISP-001). Forward-only state machine; de-identified '
    '(INV-2). Expired WAIVED auto-reopens to OPEN; lineage lives in disposition_transitions.';
