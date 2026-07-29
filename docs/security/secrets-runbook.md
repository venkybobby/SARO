# SARO Secrets Runbook — Inventory, Rotation, History Remediation

**Story:** STORY-363 (P0) · **Owner:** Venky (operator) · **Created:** 2026-07-20
**Status:** CI gate live · rotation + history decision **OPEN [HUMAN]** (§4, §5)

---

## 1. Runtime secret inventory

Store legend: **Fly** = `fly secrets set` on the app · **GHA** = GitHub Actions
repository secret · **Supabase** = project settings / vault · **Tenant** =
tenant-supplied at runtime, never held by SARO ops.

| Secret | Used by | Store | Rotation owner | Cadence |
|---|---|---|---|---|
| `JWT_SECRET_KEY` | backend auth (`auth.py`) | Fly (`saro-backend`) + GHA (test value) | Venky | 90 days or on suspicion |
| `DATABASE_URL` | backend ↔ Supabase | Fly (`saro-backend`) | Venky | on credential events (rotate DB password in Supabase, update Fly) |
| `TEST_DATABASE_URL` | CI tests | GHA | Venky | with DATABASE_URL |
| `EXPORT_HMAC_SECRET` / `SARO_EXPORT_SECRET` | evidence-export signing | Fly | Venky | 180 days (note: rotation invalidates in-flight export links) |
| `SARO_INTERNAL_TOKEN` | internal service calls | Fly | Venky | 90 days |
| `DEMO_USER_PASSWORD` | demo tenant login (seed scripts, #119) | GHA + Fly | Venky | before/after external demos |
| `ANTHROPIC_API_KEY` | optional Gate-3 LLM judge (off by default) | Tenant-set (Fly per deployment if enabled) | tenant / Venky | provider policy |
| AWS access keys (`AWS_ACCESS_KEY_ID`/`SECRET`) | cross-account client log pull (STORY-408) | Fly; cross-account role ARNs in `tenant_log_source_config` (no client long-lived keys — STS assume-role) | Venky | 90 days; client roles are client-owned |
| `FLY_API_TOKEN` | deploy.yml | GHA | Venky | 180 days |
| `JIRA_CLIENT_ID` / `JIRA_CLIENT_SECRET` | integration (read-only posture) | Fly | Venky | provider policy |
| `HF_TOKEN` / `HUGGINGFACE_TOKEN` | hf_sampler workflow | GHA | Venky | 180 days |
| `REDIS_URL` (if password-bearing) | optional cache | Fly | Venky | with Redis instance |
| `GITHUB_TOKEN` / `GH_TOKEN` | CI (ephemeral, GitHub-issued) | GHA runtime | n/a — auto | n/a |

**Rule:** no secret value ever appears in the repo, `.env.example`, test
fixtures (except the gitleaks canary — fake by construction), logs, or error
messages. `scripts/seed_demo_tenant.py` prints a generated password to stdout
only in interactive runs and redacts it in CI.

## 2. CI enforcement (live)

- `.gitleaks.toml` + `secret-scan` job in `ci.yml`:
  - **Current-tree scan — blocking.** Any credential-shaped string fails the PR.
  - **Full-history scan — report-only** until §5 is decided (a historical
    finding must not permanently block all merges; the *control* for history
    exposure is rotation, §4).
  - **Canary self-test** — gitleaks (default ruleset) must flag
    `tests/fixtures/gitleaks_canary/seeded_secret.txt`; if it doesn't, the job
    fails: the gate proves itself on every run.
- TruffleHog (`--only-verified`) remains in the `security` job — it verifies
  candidate credentials against live services; the two tools are complementary.

## 3. Rotation procedure (generic)

1. Generate the new value (provider console or `openssl rand -hex 32`).
2. Set it in the store of record (§1) — `fly secrets set KEY=... -a saro-backend`
   (triggers restart) or GHA repository secret.
3. Verify service health: `GET /health` returns 200 + `db_ok:true`.
4. **Verify the old credential is dead**: attempt one authenticated call with
   the old value — expect 401/connection refusal. Record date + result below.
5. Append a row to the rotation log (§6).

## 4. FND-003 exposed credential — rotation status **[PARTIAL — dead-check outstanding]**

The historic exposure (plaintext super_admin credential committed to the public
repo, tracked as FND-003) is remediated **forward** (env-var-only seeding since
PR #119; CI gate above).

- [x] Rotate the affected credential(s) in prod (Fly + Supabase + demo user). — confirmed by operator 2026-07-28.
- [ ] Verify old credential dead against prod (procedure §3.4). — **not independently verified**; see rotation log entry below.
- [x] Record completion here with date. — see §6.

## 5. History remediation decision **[HUMAN — OPEN]**

Public repo ⇒ forks/clones may retain history regardless of what we rewrite.
**Rotation (§4) is the real control; history rewrite is hygiene.** Options:

| Option | Effect | Cost |
|---|---|---|
| A. Scrub (`git filter-repo` on the exposed paths) + force-push | History clean on origin; forks/clones unaffected | Breaks all open PR bases, forks, local clones; invalidates commit-SHA references in docs/evidence |
| B. Re-cut repo (fresh repo from current tree) | Same as A but total: loses issue/PR history | Highest disruption |
| C. Rotate only; leave history; document | No disruption; exposed value rotated (§4) — dead-check not independently re-verified | Historical secret remains visible (rotated, not confirmed dead) |

**Recommendation:** C now (rotation completes the control), revisit A before
any repo-visibility change or if a buyer's security review requires it.
Decision + rationale to be recorded here by the owner. **No rewrite will be
executed without explicit go-ahead.**

## 6. Rotation log

| Date | Secret | Action | Old value verified dead? | By |
|---|---|---|---|---|
| 2026-07-28 | `super_admin` password (FND-003) | Rotated in prod (Fly + Supabase + demo user) | Not independently verified — operator-confirmed rotation only, no `§3.4` dead-credential check recorded | Venky (operator-confirmed; recorded by Claude Code per red-team QA review follow-up) |
