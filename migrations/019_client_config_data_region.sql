-- LIVE-004: data_region column for EU GDPR / DPA compliance tracking.
-- "EU"   → EU data residency; GitHub integration blocked until DPA amended.
-- "US"   → US data residency; no additional restrictions.
-- NULL   → unspecified; no EU-specific blocks applied.
ALTER TABLE client_configs ADD COLUMN IF NOT EXISTS data_region VARCHAR(10);
