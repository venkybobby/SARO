-- Migration 032: Tenant-isolation RLS policies for the zero-policy tables (STORY-TEN-001)
--
-- AC-1: "No table may rely on 'RLS enabled, zero policies.'" Seven tenant-scoped
-- tables had RLS enabled but no policy (Supabase discovery 2026-07-06):
--   ai_systems, aims_documents, audit_events, client_configs, github_integrations,
--   hf_sample_queue, tenant_risk_configs
-- This migration adds a tenant-isolation policy to each, mirroring the existing
-- pattern (migration 025): USING + WITH CHECK on tenant_id vs app.current_tenant.
--
-- POSTURE NOTE (see docs/TENANT_ISOLATION.md): under the FastAPI-only architecture
-- (PT decision (a)), the ENFORCED isolation control is the API layer
-- (.filter(tenant_id == current_user.tenant_id)); RLS is defense-in-depth and is
-- inert at runtime because the service-role pooler connection bypasses RLS and
-- nothing sets app.current_tenant. These policies close the inventory gap and become
-- load-bearing only if a future deployment sanctions direct DB access (posture (b)).
--
-- Idempotent: DROP POLICY IF EXISTS then CREATE. Safe to re-run.

DO $$
DECLARE
    t text;
    tenant_tables text[] := ARRAY[
        'ai_systems', 'aims_documents', 'audit_events', 'client_configs',
        'github_integrations', 'hf_sample_queue', 'tenant_risk_configs'
    ];
BEGIN
    FOREACH t IN ARRAY tenant_tables LOOP
        -- Only act on tables that exist and actually carry a tenant_id column.
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = t AND column_name = 'tenant_id'
        ) THEN
            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
            EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON %I', t, t);
            EXECUTE format(
                'CREATE POLICY tenant_isolation_%I ON %I '
                'USING (tenant_id::text = current_setting(''app.current_tenant'', true)) '
                'WITH CHECK (tenant_id::text = current_setting(''app.current_tenant'', true))',
                t, t
            );
        END IF;
    END LOOP;
END $$;
