-- LIVE-005: Per-tenant JWT session length override.
-- NULL = use global ACCESS_TOKEN_EXPIRE_MINUTES env var (default 480 = 8h).
-- Set to e.g. 480 for enterprise SSO sessions, 60 for high-security tenants.
ALTER TABLE client_configs ADD COLUMN IF NOT EXISTS token_expire_minutes INTEGER;
