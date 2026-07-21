-- 038_user_token_version.sql — FND-066: session revocation on credential change.
--
-- Before this, JWTs were validated on signature + expiry alone. Rotating a
-- leaked password left every token minted with it fully valid until it expired,
-- so the containment step in docs/security/secrets-runbook.md §3 ("rotate, then
-- verify the old credential is dead") was incomplete AND misleading — it told
-- the operator access was cut while sessions continued.
--
-- Found by the STORY-371 tabletop walking the FND-003 scenario end to end.
--
-- token_version is the session generation. Every issued token carries it;
-- auth.revoke_user_sessions() increments it, invalidating all of that user's
-- outstanding tokens at once. A per-token denylist would need storage growing
-- with every revocation plus a lookup on every request; this is one integer
-- compared against a claim that is already being decoded.
--
-- Existing rows default to 1. Tokens issued BEFORE this migration carry no
-- token_version claim at all and are rejected by auth.get_current_user (fail
-- closed) — everyone signs in once after deploy, which is the correct price for
-- not leaving the hole open for the lifetime of every issued token.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1;

COMMENT ON COLUMN users.token_version IS
    'FND-066 session generation; bumped on password change to revoke outstanding JWTs.';
