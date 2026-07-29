-- 043_tenants_settings_json.sql — backfill `tenants.settings_json`, present in
-- models.py/migration 000's source since the table's original design but
-- missing from the live schema (pre-existing drift, unrelated to any
-- migration numbering gap: production's tenants table was provisioned before
-- this column existed in 000's file and no incremental ALTER ever followed).
--
-- Surfaced by FND-088's fix: `db.get(Tenant, id)` selects every ORM-mapped
-- column, so the missing column turned a graceful demo-tenant-misconfig 503
-- into an unhandled 500 on every call to GET /api/v1/demo/token.

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS settings_json JSON;
