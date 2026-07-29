# FND-090 — demo/token missing from rate limiter's auth-strict prefixes
Stage: trivial

## Lifecycle
- [x] discover   (skipped — well-trodden: middleware/rate_limiter.py)
- [x] shape      (skipped — fix already specified by the security-auditor finding)
- [ ] preview    (skipped — backend-only, no UI surface)
- [x] plan       (see below)
- [x] build
- [ ] verify      (trivial task; regression tests are the verification)
- [ ] sell — n/a

## Plan
security-auditor review of FND-088 found `GET /api/v1/demo/token`
(routers/demo.py) missing from `middleware/rate_limiter.py`'s
`_AUTH_STRICT_PREFIXES`, so it fell through to the unthrottled default
branch instead of the strict 10/min/IP cap sibling token-minting endpoints
get (`/auth/token`, `/auth/login`, `/auth/bootstrap`, `/auth/magic-link`).
Pre-existing gap, not introduced by FND-088's fix; flagged non-blocking but
worth closing on its own.

Fix: added `/api/v1/demo/token` to `_AUTH_STRICT_PREFIXES`. Verified no
existing test relies on unlimited demo-token calls (STORY-412 census,
FND-088, FND-086 — all call it at most once per test/fixture). Pinned by
`tests/regression/test_fnd_090_demo_token_rate_limited.py` (red-first: all
3 assertions failed pre-fix).

## Deviations
Plan assumed a single-file fix + its regression test, but the full
`tests/regression` run surfaced real cross-test interference: this sandbox
has a live Redis reachable at the default `REDIS_URL`, so `check_rate_limit`
is NOT failing open in this environment. `test_fnd_088_demo_token_validates_tenant.py`
(4 real calls) and the STORY-412 census (6 real calls) both hit the real
`main.app` repeatedly against the same per-IP `auth-ip:` bucket, and once
`/demo/token` joined `_AUTH_STRICT_PREFIXES` their combined calls exceeded
the 10/min cap, 429-ing 3 previously-green tests. Conservative fix per FM-5
(don't guess, don't silently weaken): added an autouse/fixture-level
monkeypatch of `rate_limiter.check_rate_limit` in both files so they exercise
their own logic (token validation / tab census) without depending on a
shared external Redis's real-time state — the same technique
`tests/test_pt014_auth_rate_limit.py` already uses. No test assertions were
weakened; the rate limit itself is unchanged and still pinned by FND-090's
own test. Also ran `ruff format` on the two files I fully authored/extended
clean (`test_fnd_090_*.py`, and the new lines in `test_fnd_088_*.py` which
was fully-formatted before my edit); `middleware/rate_limiter.py` and
`test_story_412_*.py` already had pre-existing ruff-format drift on
unrelated lines before this change (confirmed via `git stash` diff) — left
untouched, out of this finding's scope.
