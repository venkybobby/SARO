-- LIVE-002: Allow NULL hashed_password so SSO JIT-provisioned users can be
-- created without a password hash.  verify_password() already handles None
-- (returns False) so existing password-login logic is unaffected.
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;
