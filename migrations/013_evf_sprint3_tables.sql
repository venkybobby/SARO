-- Migration 013: EVF Sprint 3 — QCO Expiry Notifications
--
-- Creates one table for the External SME Validation Framework (SARO-RISK-001):
--   evf_expiry_notifications — idempotent log of every QCO expiry notification
--
-- Notification types:
--   T_MINUS_60  — 60-day renewal trigger
--   T_MINUS_30  — 30-day reminder
--   T_MINUS_7   — 7-day reminder
--   EXPIRED     — QCO expired; validation reverted to Tier 2 (Under Review)
--   SALES_NOTIFY — 24-hour Sales alert (AC-13c)
--
-- Safe to re-run: all DDL uses CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
-- Picked up automatically by apply_pending_migrations() on startup.
-- Refs: FR-EVF-13 | SARO-RISK-001

CREATE TABLE IF NOT EXISTS evf_expiry_notifications (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    qco_id                  UUID        REFERENCES evf_qco_registry(id) ON DELETE SET NULL,
    qco_reference_number    VARCHAR(100) NOT NULL,
    -- EVFFramework value
    framework               VARCHAR(50)  NOT NULL,
    -- T_MINUS_60 | T_MINUS_30 | T_MINUS_7 | EXPIRED | SALES_NOTIFY
    notification_type       VARCHAR(20)  NOT NULL,
    -- Days remaining at notification time (negative = already expired)
    expires_in_days         INTEGER,
    -- UTC timestamp when notification was written / dispatched
    sent_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    -- Idempotency key: "{qco_id}:{notification_type}:{reference_date}"
    -- Unique constraint prevents duplicate notifications for same event
    idempotency_key         VARCHAR(255) NOT NULL UNIQUE,

    CONSTRAINT evf_expiry_notif_type_check
        CHECK (notification_type IN ('T_MINUS_60', 'T_MINUS_30', 'T_MINUS_7', 'EXPIRED', 'SALES_NOTIFY'))
);

-- Index: look up pending alerts by framework (Sales dashboard queries)
CREATE INDEX IF NOT EXISTS ix_evf_expiry_notif_framework
    ON evf_expiry_notifications (framework);

-- Index: look up by type (e.g. all SALES_NOTIFY for dispatch audit)
CREATE INDEX IF NOT EXISTS ix_evf_expiry_notif_type
    ON evf_expiry_notifications (notification_type);

-- Index: recent alerts first (default sort order)
CREATE INDEX IF NOT EXISTS ix_evf_expiry_notif_sent_at
    ON evf_expiry_notifications (sent_at DESC);

-- Index: filter by QCO id (expiry audit per QCO)
CREATE INDEX IF NOT EXISTS ix_evf_expiry_notif_qco_id
    ON evf_expiry_notifications (qco_id);

COMMENT ON TABLE evf_expiry_notifications IS
    'Idempotent log of QCO expiry notifications. '
    'One row per (qco_id, notification_type, reference_date) — deduped by idempotency_key. '
    'FR-EVF-13 | SARO-RISK-001';
