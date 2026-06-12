-- FND-006: scan_reports.tenant_id was added (nullable) in 002_add_tenant_id_columns.sql
-- but never backfilled. Under tenant_isolation_scan_reports
-- (USING (tenant_id::text = current_setting('app.current_tenant', true))),
-- NULL = x evaluates to NULL (not true) in Postgres, so any scan_reports row
-- with tenant_id IS NULL is invisible to every tenant under RLS.
--
-- Backfill from the parent audits row, same pattern as the audit_traces
-- backfill in 002_add_tenant_id_columns.sql. Safe to re-run.
UPDATE scan_reports sr
SET tenant_id = (SELECT a.tenant_id FROM audits a WHERE a.id = sr.audit_id)
WHERE sr.tenant_id IS NULL;
