# TM-F1 — Signed OAuth state for Jira OAuth flow (FND-061) + broken token persistence (FND-062)
Stage: standard

## Lifecycle
- [x] discover   (skipped — area recon done inline: routers/remediation.py, services/jira.py, models.py, trace_export HMAC pattern, threat-model TM-F1 text)
- [x] shape      (interview skipped — TM-F1 finding text + task spec fully specify the change; decisions below derived from it)
- [x] preview    (skipped — backend-only)
- [x] plan
- [x] build      (red→green TDD: 9 tests written first, all failed against the
                  vulnerable code — the pre-fix callback 200'd a forged state and
                  logged "Failed to store Jira tokens" — then implementation
                  turned them green. Full backend suite: 1763 passed, 3 skipped.
                  ruff check / mypy / bandit clean on changed files.)
- [x] verify     (independent security-auditor: PASS-WITH-FINDINGS — all 10
                  checklist items confirmed; its two Low findings fixed in-PR
                  (non-ASCII state → bytes compare_digest so 400 not 500, pinned;
                  with_for_update row lock for atomic nonce consume) and its
                  pre-existing posture finding logged as FND-063 open.
                  Independent reviewer: APPROVE — its MINORs fixed in-PR
                  (rejection-category logging, generic 500 detail with env-var
                  names kept to logs, TTL lower bound, fail-closed 500 test).
                  change-debrief.html built. Final regression suite: 126 passed.)
- [ ] sell       (n/a)

## Decision Log

1. **State format** → `"{tenant_id}.{issued_ts}.{nonce}.{hmac_sha256_hex}"` —
   HMAC-SHA256 over `tenant.ts.nonce`, hex sig appended. Stateless signature
   verification (tamper + expiry) plus a DB-stored nonce for one-time use.
   *Consequence:* callback can verify integrity without a session store; replay
   protection survives multi-machine deploys because the nonce lives in Postgres.

2. **Signing key** → `OAUTH_STATE_SECRET` env var, falling back to
   `settings.jwt_secret_key`; **no hardcoded default** (the FND-044 class bug in
   `EXPORT_HMAC_SECRET` is explicitly not repeated). Missing both → 500 on
   /start (fail closed). jwt_secret_key fallback is safe because the Jira flow
   already hard-requires it for token encryption (`services/jira._get_fernet`).

3. **Nonce + token storage** → `Tenant.settings_json` (column exists, row always
   exists), NOT `ClientConfig.settings_json` — that column **does not exist**
   (models.py ClientConfig has no such attribute), so the pre-existing token
   write in the callback silently never persisted (AttributeError swallowed by
   the broad except) and `create_jira_issue`'s read path could never work.
   Logged as **FND-062**; both the callback write and the `create_jira_issue`
   read move to `Tenant.settings_json`. *Consequence:* no migration needed; the
   Jira integration becomes actually functional and testable.

4. **Verification order** → callback: missing state → 400; bad
   format/signature/expiry → 400; unknown/already-used nonce → 400 — **all
   before the code-for-token exchange** (no external call on an unverified
   request). Nonce is consumed at verification time (strict one-time use even if
   the subsequent exchange fails; user restarts the flow).

5. **TTL** → 10 minutes (`_STATE_TTL_SECONDS = 600`). OAuth redirect round-trips
   are seconds; 10 min tolerates a slow consent screen.

6. **Route signatures** → `state` stays `Optional[str] = None` in the callback so
   a missing value produces the spec'd 400 (not FastAPI's 422); `db` becomes a
   real required dependency (was `= None`). /start gains a `db` dependency to
   store the nonce. Response shapes unchanged (`{"oauth_url": ...}`,
   `{"status": "jira_connected", ...}`).

7. **Regression pinning** → `tests/regression/test_fnd_061_jira_oauth_signed_state.py`
   covers: valid state end-to-end (tokens land on Tenant.settings_json — this
   also pins FND-062), missing state, tampered state, forged-key state, expired
   state, replayed state; token-exchange mock asserts no external call on any
   rejected path. Manifest + quality/findings.md get FND-061 + FND-062 rows.

## Plan (tweak-likelihood order)

1. Data shape: `Tenant.settings_json["jira_oauth_state"] = {"nonce", "issued_at"}`;
   tokens `jira_access_token_enc`/`jira_refresh_token_enc` move to Tenant.settings_json.
2. New helpers in routers/remediation.py: `_state_secret`, `_sign_state_payload`,
   `_generate_oauth_state`, `_verify_oauth_state` (HTTPException(400) on all
   invalid shapes).
3. Behavior: /start signs + persists nonce; /callback verifies+consumes before
   exchange; create_jira_issue reads Tenant.settings_json.
4. Mechanical: regression tests (red→green), manifest + findings.md rows.

## Deviations
- Scope extension (conservative option): moved Jira token persistence from the
  nonexistent `ClientConfig.settings_json` to `Tenant.settings_json` (FND-062).
  Alternative (aggressive) was a migration adding the column to client_configs;
  rejected — larger blast radius, and Tenant.settings_json already exists.
- Finding IDs renumbered mid-task (058/059/060 → 061/062/063): origin/main moved
  4 commits ahead during the work and its tip (PR #124) already claimed
  FND-058/059/060. The branch will be merged with origin/main before push so the
  append-only ledger/manifest stay conflict-free.
- `docs/security/threat-model.md` (TM-F1's source, STORY-365 commit 85d22b1) is
  NOT on origin/main yet — it lives on `story/epics-14-19-pack` (the main
  checkout's current branch, 8 commits ahead of origin/main). It therefore can't
  be edited from this branch; when that pack merges, its TM-F1 disposition row
  should be updated to "Fixed — FND-061" (residual /start role gate = FND-063).
