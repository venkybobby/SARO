-- 044_users_role_check.sql — FND-093: users.role had no DB-level guard.
--
-- models.User.role was a plain VARCHAR(50) with only a code comment
-- ("Roles: super_admin | operator") documenting the two valid values --
-- nothing at the schema level stopped a typo'd/arbitrary string from being
-- persisted. Defense-in-depth only: no current write path sets anything
-- other than the two literals.
--
-- Idempotent (DROP IF EXISTS + ADD) so an environment whose schema_migrations
-- already recorded 000 before this constraint existed in the model catches
-- up on the next apply_pending_migrations() run — see FND-090/091 for why
-- editing an already-applied migration's file content is not sufficient.

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS ck_users_role_valid;

ALTER TABLE users
    ADD CONSTRAINT ck_users_role_valid CHECK (role IN ('super_admin', 'operator'));
