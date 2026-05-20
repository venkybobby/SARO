-- Migration 006: Notification system
-- Adds notifications table with per-tenant RLS policy.

CREATE TABLE IF NOT EXISTS notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    type        VARCHAR(50) NOT NULL CHECK (type IN ('threshold_breach','drift_alert','framework_update','system')),
    title       VARCHAR(255) NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    severity    VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical','high','medium','low')),
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

-- Indexes for efficient tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_notifications_tenant_unread
    ON notifications (tenant_id, read_at)
    WHERE read_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_notifications_tenant_created
    ON notifications (tenant_id, created_at DESC);

-- Row-Level Security
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY notifications_tenant_isolation ON notifications
    USING (tenant_id::text = current_setting('app.current_tenant', true));
