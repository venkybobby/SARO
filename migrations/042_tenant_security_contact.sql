-- 042_tenant_security_contact.sql — FND-067: per-tenant security contact.
--
-- docs/ops/support-model.md §4 commits to notifying an affected customer of a
-- confirmed reportable security incident within 72 hours. Locating the right
-- contact mid-incident wastes that clock; this column captures it at
-- onboarding. Nullable: tenants provisioned before this migration have no
-- recorded contact until an admin sets one (the incident runbook treats NULL
-- as "escalate to the tenant's admin users").

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS security_contact_email VARCHAR(320);
