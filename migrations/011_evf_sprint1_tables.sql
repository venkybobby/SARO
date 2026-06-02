-- Migration 011: EVF Sprint 1 — SME Engagement, Transitions, Validation Gate
--
-- Creates three tables for the External SME Validation Framework (SARO-RISK-001):
--   evf_sme_engagements       — one engagement per SME firm per framework per cycle
--   evf_engagement_transitions — append-only hash-chained state-transition audit log
--   evf_validation_gates       — 7-item checklist gate per engagement (1:1)
--
-- These are SARO-internal governance tables (not per-tenant customer data).
-- Access is enforced at the API layer (super_admin role) — no RLS required.
--
-- Safe to re-run: all DDL uses CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
-- / CREATE INDEX IF NOT EXISTS.
--
-- Refs: FR-EVF-05 (engagement tracking), FR-EVF-08 (validation gate)
-- Applied by: apply_pending_migrations() on startup (database.py)

-- ─────────────────────────────────────────────────────────────────────────────
-- Table 1: evf_sme_engagements
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evf_sme_engagements (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    sme_firm_name       VARCHAR(255) NOT NULL,
    sme_key_contact     VARCHAR(255),
    sme_credential      VARCHAR(255),
    -- EVFFramework enum: EU_AI_ACT | NIST_AI_RMF | AIGP | ISO_42001
    framework           VARCHAR(50)  NOT NULL,
    -- SMEEngagementState enum (forward-only state machine)
    -- SHORTLISTED → COI_CLEARED → SOW_ISSUED → REVIEW_IN_PROGRESS
    -- → DRAFT_QCO_RECEIVED → QCO_APPROVED → PUBLISHED → RENEWAL_TRIGGERED
    state               VARCHAR(50)  NOT NULL DEFAULT 'SHORTLISTED',
    state_entered_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by_user_id  UUID         REFERENCES users(id) ON DELETE SET NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,

    CONSTRAINT evf_engagements_framework_check
        CHECK (framework IN ('EU_AI_ACT', 'NIST_AI_RMF', 'AIGP', 'ISO_42001')),
    CONSTRAINT evf_engagements_state_check
        CHECK (state IN (
            'SHORTLISTED', 'COI_CLEARED', 'SOW_ISSUED', 'REVIEW_IN_PROGRESS',
            'DRAFT_QCO_RECEIVED', 'QCO_APPROVED', 'PUBLISHED', 'RENEWAL_TRIGGERED'
        ))
);

-- Index: list by state (dashboard queries)
CREATE INDEX IF NOT EXISTS ix_evf_engagements_state
    ON evf_sme_engagements (state);

-- Index: list by framework (filter queries)
CREATE INDEX IF NOT EXISTS ix_evf_engagements_framework
    ON evf_sme_engagements (framework);

-- Index: chronological list
CREATE INDEX IF NOT EXISTS ix_evf_engagements_created_at
    ON evf_sme_engagements (created_at DESC);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION evf_engagements_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evf_engagements_updated_at ON evf_sme_engagements;
CREATE TRIGGER trg_evf_engagements_updated_at
    BEFORE UPDATE ON evf_sme_engagements
    FOR EACH ROW EXECUTE FUNCTION evf_engagements_set_updated_at();

COMMENT ON TABLE evf_sme_engagements IS
    'One SME firm engagement per framework per validation cycle. '
    'State machine advances forward-only; RENEWAL_TRIGGERED reachable from any state. '
    'FR-EVF-05 | SARO-RISK-001';

-- ─────────────────────────────────────────────────────────────────────────────
-- Table 2: evf_engagement_transitions
-- ─────────────────────────────────────────────────────────────────────────────
-- Append-only hash-chained audit log.  Rows must never be updated or deleted.
-- event_hash = SHA-256(transition payload + prev_hash) — tamper-evident.
-- prev_hash NULL on the genesis row; each subsequent row chains to the prior
-- event_hash so any modification breaks all downstream hashes.

CREATE TABLE IF NOT EXISTS evf_engagement_transitions (
    id              UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    engagement_id   UUID        NOT NULL REFERENCES evf_sme_engagements(id) ON DELETE CASCADE,
    from_state      VARCHAR(50) NOT NULL,
    to_state        VARCHAR(50) NOT NULL,
    actor_user_id   UUID        REFERENCES users(id) ON DELETE SET NULL,
    reason          TEXT,
    -- SHA-256 hash of this transition's payload (see evf_engagement_service.py)
    event_hash      VARCHAR(64),
    -- event_hash of the immediately preceding transition (NULL for genesis row)
    prev_hash       VARCHAR(64),
    -- Server-set; NOT updatable — append-only
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Prevent any UPDATE or DELETE on transition rows (append-only guarantee)
CREATE OR REPLACE FUNCTION evf_transitions_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'evf_engagement_transitions rows are append-only — id % cannot be %',
        OLD.id, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evf_transitions_immutable ON evf_engagement_transitions;
CREATE TRIGGER trg_evf_transitions_immutable
    BEFORE UPDATE OR DELETE ON evf_engagement_transitions
    FOR EACH ROW EXECUTE FUNCTION evf_transitions_prevent_modification();

-- Index: chain traversal per engagement (ordered by time)
CREATE INDEX IF NOT EXISTS ix_evf_transitions_engagement_created
    ON evf_engagement_transitions (engagement_id, created_at ASC);

-- Index: hash lookup for chain verification
CREATE INDEX IF NOT EXISTS ix_evf_transitions_event_hash
    ON evf_engagement_transitions (event_hash);

COMMENT ON TABLE evf_engagement_transitions IS
    'Append-only hash-chained log of every SME engagement state transition. '
    'Immutability enforced by trigger. '
    'event_hash = SHA-256(payload + prev_hash). '
    'FR-EVF-05 | SARO-RISK-001';

-- ─────────────────────────────────────────────────────────────────────────────
-- Table 3: evf_validation_gates
-- ─────────────────────────────────────────────────────────────────────────────
-- 7-item checklist gate (FR-EVF-08). One gate per engagement (UNIQUE constraint).
-- All 7 boolean items must be TRUE before the gate can be locked.
-- Once locked=TRUE, no further updates to item columns are permitted
-- (enforced at the application layer in evf_gate_service.py).

CREATE TABLE IF NOT EXISTS evf_validation_gates (
    id                          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    engagement_id               UUID        NOT NULL UNIQUE
                                            REFERENCES evf_sme_engagements(id) ON DELETE CASCADE,

    -- Gate item 1: COI declared and approved
    coi_declared_approved       BOOLEAN     NOT NULL DEFAULT FALSE,
    coi_evidence_ref            VARCHAR(500),

    -- Gate item 2: SOW executed
    sow_executed                BOOLEAN     NOT NULL DEFAULT FALSE,
    sow_evidence_ref            VARCHAR(500),

    -- Gate item 3: Evidence Package delivered to SME
    evidence_package_delivered  BOOLEAN     NOT NULL DEFAULT FALSE,
    evidence_package_ref        VARCHAR(500),

    -- Gate item 4: Product demo completed
    product_demo_completed      BOOLEAN     NOT NULL DEFAULT FALSE,
    product_demo_ref            VARCHAR(500),

    -- Gate item 5: Draft QCO received from SME
    draft_qco_received          BOOLEAN     NOT NULL DEFAULT FALSE,
    draft_qco_ref               VARCHAR(500),

    -- Gate item 6: SARO legal review of draft QCO completed
    saro_legal_review_completed BOOLEAN     NOT NULL DEFAULT FALSE,
    legal_signoff_ref           VARCHAR(500),

    -- Gate item 7: QCO approved and reference number assigned
    qco_approved_ref_assigned   BOOLEAN     NOT NULL DEFAULT FALSE,
    qco_ref                     VARCHAR(100),

    -- Lock state — set TRUE when all 7 items are TRUE; no further edits after this
    locked                      BOOLEAN     NOT NULL DEFAULT FALSE,
    locked_at                   TIMESTAMPTZ,
    locked_by_user_id           UUID        REFERENCES users(id) ON DELETE SET NULL,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION evf_gates_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evf_gates_updated_at ON evf_validation_gates;
CREATE TRIGGER trg_evf_gates_updated_at
    BEFORE UPDATE ON evf_validation_gates
    FOR EACH ROW EXECUTE FUNCTION evf_gates_set_updated_at();

-- Index: lookup by engagement (also covered by UNIQUE, but explicit for clarity)
CREATE INDEX IF NOT EXISTS ix_evf_gates_engagement_id
    ON evf_validation_gates (engagement_id);

-- Index: find all unlocked / locked gates (ops dashboard)
CREATE INDEX IF NOT EXISTS ix_evf_gates_locked
    ON evf_validation_gates (locked);

COMMENT ON TABLE evf_validation_gates IS
    '7-item validation gate per SME engagement. '
    'All items must be TRUE before locking. '
    'Once locked, no further item edits are permitted (enforced by application layer). '
    'FR-EVF-08 | SARO-RISK-001';
