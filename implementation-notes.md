# FND-092 (was FND-090) — demo/token missing from rate limiter's auth-strict prefixes
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
`tests/regression/test_fnd_092_demo_token_rate_limited.py` (red-first: all
3 assertions failed pre-fix).

Full-suite verification at fix time: `tests/regression -q` 222 passed;
`pytest -m unit` 920 passed; `pytest -m integration` 375 passed, 3 skipped;
full `tests/` 2412 passed, 26 skipped; `ruff check .` clean; `mypy` +
`bandit` on the changed source file clean.

## Deviations
1. Test-isolation fix (same session, before renumbering): the full
   regression run exposed a live Redis reachable at this sandbox's default
   `REDIS_URL` (not fail-open). `test_fnd_088_demo_token_validates_tenant.py`
   (4 real calls) and the STORY-412 census (6 real calls) both hit the real
   `main.app` repeatedly against the same per-IP `auth-ip:` bucket; once
   `/demo/token` joined `_AUTH_STRICT_PREFIXES` their combined calls exceeded
   the 10/min cap and 429'd 3 previously-green tests. Fixed by monkeypatching
   `rate_limiter.check_rate_limit` in both files (same technique
   `tests/test_pt014_auth_rate_limit.py` already uses) — no assertions
   weakened, the rate limit itself is unchanged and still pinned by this
   finding's own test.

2. **ID renumbering (FND-090 → FND-092):** this fix was committed and PR'd
   as FND-090. Before merge, `main` independently landed an unrelated
   FND-090/FND-091 pair (`tenants.settings_json` production migration gap +
   its `database.py` self-heal follow-up), creating a real ledger collision
   per CLAUDE.md's ledger rule (repo is the only status ledger that counts).
   Merged `origin/main`, took main's FND-090/FND-091 rows as-is in
   `quality/findings.md` and `tests/regression/manifest.yaml`, and
   renumbered this fix's entry to FND-092 (next available ID). Renamed
   `test_fnd_090_demo_token_rate_limited.py` →
   `test_fnd_092_demo_token_rate_limited.py` and updated all in-repo
   `FND-090` references belonging to this fix (`middleware/rate_limiter.py`
   comment, the two test-isolation monkeypatch comments) to `FND-092`.
   `database.py` merged cleanly (main's `tenants` self-heal entries and this
   PR's file are disjoint).
