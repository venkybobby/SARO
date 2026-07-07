-- Migration 033: SARO self-audit spine (STORY-META-001)
--
-- Turns the (empty) audit_events table into an immutable, hash-chained trail of
-- privileged/sensitive actions WITHIN SARO, so the platform can survive the same
-- scrutiny it applies to customers. Metadata only — never payload content
-- (INV-2/INV-3 apply to the audit trail itself).
--
--   1. Extend audit_events with the META-001 columns (nullable so existing
--      unchained writers keep working; self-audit events fill the chained schema).
--   2. Immutability trigger: reject UPDATE/DELETE (append-only).
--   3. SYSTEM tenant for global / out-of-band events (rule-pack changes are global).
--   4. Out-of-band capture (AC-3): statement-level triggers on the rule tables insert
--      a RULE_PACK_CHANGE event with actor = 'db:'||current_user when rules are written
--      outside the API (the 2026-07-04 path). Flagged out_of_band (not app-chained).
--      Residual risk: a superuser can disable the trigger — mitigation is role
--      separation, documented honestly in the security whitepaper (not pretended away).
--   5. Backfill (AC edge): two RETROACTIVE RULE_PACK_CHANGE events referencing the
--      tracked radar migrations — the trail's first entries demonstrate honest backfill.
--
-- Idempotent. Refs: STORY-META-001 | audit_events (0 rows, Supabase discovery 2026-07-06).

-- 1. columns ------------------------------------------------------------------
ALTER TABLE audit_events
    ADD COLUMN IF NOT EXISTS action_class VARCHAR(50),
    ADD COLUMN IF NOT EXISTS actor        VARCHAR(255),
    ADD COLUMN IF NOT EXISTS target_type  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS target_id    VARCHAR(255),
    ADD COLUMN IF NOT EXISTS outcome      VARCHAR(50),
    ADD COLUMN IF NOT EXISTS retroactive  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS seq          BIGINT,
    ADD COLUMN IF NOT EXISTS prev_hash    VARCHAR(64),
    ADD COLUMN IF NOT EXISTS event_hash   VARCHAR(64);

-- id had only an app-layer (ORM) default; the DB-level default is REQUIRED so the
-- raw-SQL backfill and the out-of-band trigger inserts below can omit id (AC-3).
ALTER TABLE audit_events ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Per-tenant monotonic ordering for the app-layer chain (partial: chained rows only).
CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_events_tenant_seq
    ON audit_events (tenant_id, seq) WHERE seq IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_audit_events_action_class ON audit_events (action_class);
CREATE INDEX IF NOT EXISTS ix_audit_events_actor ON audit_events (actor);
CREATE INDEX IF NOT EXISTS ix_audit_events_target ON audit_events (target_type, target_id);

-- 2. immutability -------------------------------------------------------------
CREATE OR REPLACE FUNCTION audit_events_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only — id % cannot be %', OLD.id, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events;
CREATE TRIGGER trg_audit_events_immutable
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_prevent_modification();

-- 3. SYSTEM tenant for global / out-of-band events ----------------------------
INSERT INTO tenants (id, name, slug)
VALUES ('a0000000-0000-0000-0000-000000000001', 'SARO System', 'saro-system')
ON CONFLICT (id) DO NOTHING;

-- 4. out-of-band capture (AC-3) ----------------------------------------------
-- Statement-level (one event per statement with a row count — AC edge "not per row").
CREATE OR REPLACE FUNCTION audit_events_capture_rule_write()
RETURNS TRIGGER AS $$
DECLARE
    n integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        SELECT count(*) INTO n FROM oldrows;
    ELSE
        SELECT count(*) INTO n FROM newrows;
    END IF;
    INSERT INTO audit_events (tenant_id, event_type, event_data, action_class, actor,
                              target_type, target_id, outcome, retroactive)
    VALUES (
        'a0000000-0000-0000-0000-000000000001',
        'rule_pack_change',
        jsonb_build_object('source', 'db_trigger', 'out_of_band', true,
                           'operation', TG_OP, 'row_count', n),
        'RULE_PACK_CHANGE',
        'db:' || current_user,
        TG_TABLE_NAME,
        TG_TABLE_NAME || ':' || TG_OP,
        'SUCCESS',
        false
    );
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['eu_ai_act_rules', 'governance_rules'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_oob_audit_ins ON %I', t, t);
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_oob_audit_upd ON %I', t, t);
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_oob_audit_del ON %I', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_oob_audit_ins AFTER INSERT ON %I '
            'REFERENCING NEW TABLE AS newrows FOR EACH STATEMENT '
            'EXECUTE FUNCTION audit_events_capture_rule_write()', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_oob_audit_upd AFTER UPDATE ON %I '
            'REFERENCING NEW TABLE AS newrows FOR EACH STATEMENT '
            'EXECUTE FUNCTION audit_events_capture_rule_write()', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_oob_audit_del AFTER DELETE ON %I '
            'REFERENCING OLD TABLE AS oldrows FOR EACH STATEMENT '
            'EXECUTE FUNCTION audit_events_capture_rule_write()', t, t);
    END LOOP;
END $$;

-- 5. backfill (AC edge) — retroactive, honestly flagged, not app-chained ------
INSERT INTO audit_events (tenant_id, event_type, event_data, action_class, actor,
                          target_type, target_id, outcome, retroactive)
SELECT 'a0000000-0000-0000-0000-000000000001', 'rule_pack_change',
       jsonb_build_object('source', 'backfill', 'migration', v.mig, 'note',
                          'Retroactive record of an out-of-band rule-pack migration applied before the self-audit spine existed.'),
       'RULE_PACK_CHANGE', 'system:backfill', 'migration', v.mig, 'SUCCESS', true
FROM (VALUES
    ('radar_scan1_validation_status_columns'),
    ('radar_scan1_rule_pack_delta_data')
) AS v(mig)
WHERE NOT EXISTS (
    SELECT 1 FROM audit_events e
    WHERE e.retroactive = true AND e.target_id = v.mig
);

COMMENT ON COLUMN audit_events.action_class IS
    'META-001 action class: RULE_PACK_CHANGE|EVIDENCE_ACCESS|DISPOSITION_ACTION|ADMIN_ACTION|AUTH_EVENT|EXPORT';
