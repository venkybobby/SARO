# JWT Hardening Plan — SARO v8.0.0
**Date:** 2026-05-28
**Branch target:** `main` (via PR to `venkybobby/SARO`)
**Reviewers:** Venky (Lead), Jordan Lee (Backend/Infra)

---

## 1. Current State Summary

The existing auth implementation has several strong foundations that should be preserved and not second-guessed.

| Component | Assessment |
|---|---|
| Password hashing | Argon2id (time_cost=3, memory_cost=65536) — OWASP best practice. Transparent bcrypt fallback for legacy hashes is correctly implemented. |
| Lazy env var loading | `_secret_key()`, `_algorithm()`, `_expire_minutes()` are all called at runtime, not import time. This prevents startup crashes when secrets are injected after process start (Railway). |
| Token payload | Contains `sub`, `email`, `role`, `tenant_id`, `exp` — appropriate for SARO's RBAC model. |
| `get_current_user` | Correctly re-fetches the User row from the DB on every request, which means `is_active=False` accounts are caught in real time. This is already partial protection against deactivated users. |
| `require_role` | Clean dependency factory pattern — used consistently across all routers. |
| Rate limiter | Redis sliding-window middleware exists (`middleware/rate_limiter.py`) — applied globally via `app.add_middleware(RateLimiterMiddleware)`. |
| `authenticate_user` | Returns `None` uniformly for both unknown email and bad password — does not leak which condition failed to the caller (correct). |
| Error messages | Login returns a single "Incorrect email or password" — no enumeration. |
| Structured logging | `structlog` with JSON renderer on Railway — good audit surface. |
| `TokenOut` schema | No internal JWT claims are leaked in the API response — only `access_token` and `token_type`. |

---

## 2. Gap Analysis Table

| # | Gap | Risk Level | Recommended Fix | Owner |
|---|---|---|---|---|
| G-01 | **Token expiry is 480 min (8 hours)** — long-lived tokens increase the blast radius of credential theft. SARO handles compliance audit data including potential PII signals. | High | Reduce `ACCESS_TOKEN_EXPIRE_MINUTES` default to `60`. Add a short-lived refresh token (see G-02) to compensate for UX. | devops-engineer (env var) + backend-developer (refresh flow) |
| G-02 | **No refresh token mechanism** — once the 8-hour token is stolen, there is no way to force re-authentication without deactivating the account. | High | Implement `POST /api/v1/auth/refresh` with an opaque refresh token (UUID stored in Supabase), short access token (60 min), long-lived refresh token (7 days). `REFRESH_TOKEN_EXPIRE_DAYS` already exists in `.env.example`. | backend-developer |
| G-03 | **No token revocation / logout endpoint** — `is_active` check in `get_current_user` catches deactivated accounts but does NOT invalidate issued tokens. A token issued to an account before `is_active` was set to `False` will work until expiry. | High | Add `POST /api/v1/auth/logout` that deletes the refresh token row. For access tokens, the short expiry from G-01 (60 min) is the primary mitigation. A Redis jti denylist is an optional second layer (see G-03a). | backend-developer |
| G-03a | **No jti (JWT ID) denylist** — critical for immediate revocation without waiting for expiry. | Medium | Add `jti` claim (UUID) to access tokens. On logout or account deactivation, write `jti` to Redis with TTL equal to the token's remaining lifetime. Check in `_decode_token`. Dependent on Redis being available (already present in the stack). | backend-developer |
| G-04 | **HS256 shared secret** — acceptable for a single-service deployment but becomes a problem if SARO adds microservices or third-party token consumers. The same secret that signs also verifies, so any service with the secret can forge tokens. | Medium | No immediate change required for the current single-Railway-service deployment. Document the RS256 upgrade path: Railway injects `JWT_PRIVATE_KEY` + `JWT_PUBLIC_KEY`; signing uses private key, verification uses public key. Plan for this before adding a second backend service. | devops-engineer (future sprint) |
| G-05 | **No JWT secret rotation mechanism** — `JWT_SECRET_KEY` is a single static value. Rotation requires downtime or a dual-key grace period. | Medium | Implement a grace period rotation: support `JWT_SECRET_KEY` (current) and `JWT_SECRET_KEY_PREV` (previous). `_decode_token` tries current key first, falls back to previous. Allows Railway secret rotation with zero token-invalidation downtime. | backend-developer + devops-engineer |
| G-06 | **Rate limiter is per-tenant, not per-endpoint** — `POST /api/v1/auth/token` (login) shares the 100 rpm bucket with all other tenant requests. A credential-stuffing attack uses far fewer requests than 100 rpm. | High | Add a dedicated per-IP rate limit on `POST /api/v1/auth/token` and `POST /api/v1/auth/bootstrap`: 10 attempts per minute per IP. This is separate from and additive to the existing tenant-level limiter. Remove `/api/v1/auth/magic-link` and `/api/v1/auth/saml` from `_ALLOWLIST_PREFIXES` — they should also be rate-limited. | backend-developer |
| G-07 | **CORS defaults to `*` when `ALLOWED_ORIGINS` is not set** — the comment in `main.py` acknowledges this ("API security is enforced via JWT") but an open CORS policy allows cross-origin credential exfiltration from browser-based XSS attacks. In production, `ALLOWED_ORIGINS` MUST be set. | High | Set `ALLOWED_ORIGINS=https://saro.vercel.app` in Railway production environment. Add a startup assertion in `lifespan()` that logs a `CRITICAL` warning (not crash) when `ALLOWED_ORIGINS` is empty and `ENVIRONMENT=production`. | devops-engineer (env var) + backend-developer (startup warning) |
| G-08 | **No security response headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, and `Content-Security-Policy` are not set. Railway does not inject these automatically. | Medium | Add a `SecurityHeadersMiddleware` in `middleware/security_headers.py` and register it in `main.py`. Railway enforces HTTPS at the edge (TLS termination) so HSTS in the app is belt-and-suspenders but correct for defence-in-depth. | backend-developer |
| G-09 | **`/api/v1/auth/bootstrap` is unauthenticated and not rate-limited** — while the 409 guard is correct (rejects after first user), an attacker could probe it without restriction. | Low | Include `/api/v1/auth/bootstrap` in the per-IP login rate limit window (G-06 fix). No schema change needed. | backend-developer |
| G-10 | **`tenant_context.py` uses raw f-string SQL** — `db.execute(f"SET LOCAL app.current_tenant = '{tenant_id}'"`) is a SQL injection vector if `tenant_id` ever contains untrusted input. While UUIDs from JWT are structurally safe, this pattern is fragile. | Medium | Use SQLAlchemy `text()` with bound parameters: `db.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(tenant_id)})` | backend-developer |
| G-11 | **`last_login_at` and `failed_login_count` are not tracked on the User model** — no audit trail for suspicious login patterns, no account lockout capability. | Low | Add `last_login_at` (DateTime) and `failed_login_count` (Integer, default 0) to `User` model via `ALTER TABLE` (consistent with the project's no-DROP-TABLE policy). Lock account after configurable consecutive failures (e.g. 10). | backend-developer |

---

## 3. Sequenced Work Breakdown

Tasks are ordered by risk priority. Parallel execution opportunities are noted.

```
Sprint 1 — Critical path (can be done in parallel where marked)
────────────────────────────────────────────────────────────────
[P1-A] G-06: Per-endpoint login rate limit          backend-developer   ~2h
[P1-B] G-07: Set ALLOWED_ORIGINS in Railway prod    devops-engineer     ~30min  (parallel with P1-A)
[P1-C] G-07: Startup CORS warning (production)      backend-developer   ~30min  (parallel with P1-A)

Sprint 2 — High-impact structural changes
────────────────────────────────────────────────────────────────
[P2-A] G-01: Reduce ACCESS_TOKEN_EXPIRE_MINUTES     devops-engineer     ~15min
[P2-B] G-02: Refresh token model + endpoint         backend-developer   ~4h     (must precede P2-A deploy)
[P2-C] G-03: Logout endpoint (deletes refresh row)  backend-developer   ~1h     (parallel with P2-B, depends on model)

Sprint 3 — Defence-in-depth
────────────────────────────────────────────────────────────────
[P3-A] G-08: SecurityHeadersMiddleware              backend-developer   ~1h
[P3-B] G-05: Dual-key secret rotation support       backend-developer   ~2h     (parallel with P3-A)
[P3-C] G-05: Rotate JWT_SECRET_KEY in Railway       devops-engineer     ~30min  (after P3-B is deployed)
[P3-D] G-03a: jti denylist in Redis                 backend-developer   ~2h     (parallel with P3-A/B)
[P3-E] G-10: Fix SQL injection in tenant_context    backend-developer   ~15min  (quick win, do first in sprint)

Sprint 4 — Audit trail and future-proofing
────────────────────────────────────────────────────────────────
[P4-A] G-11: last_login_at + failed_login_count     backend-developer   ~2h
[P4-B] G-04: Document RS256 upgrade path            backend-developer   ~1h     (ADR doc, no code)
[P4-C] G-09: Bootstrap rate limit (included in G-06 fix, verify)
```

---

## 4. Backend Developer Task List

File references are relative to `C:\Users\shris\SARO\`.

### T-BE-01: Per-endpoint login rate limit (G-06, G-09) — Sprint 1

**File:** `middleware/rate_limiter.py`

Add a second check function `check_auth_rate_limit(ip: str, limit: int = 10)` using a separate Redis key pattern `auth:{ip}:{bucket}`. Apply it in `routers/auth.py` on `POST /token` and `POST /bootstrap` before calling `authenticate_user`.

Remove `/api/v1/auth/magic-link` and `/api/v1/auth/saml` from `_ALLOWLIST_PREFIXES`.

**File:** `routers/auth.py`

In the `login()` function, extract the client IP from the `Request` object (add `request: Request` parameter) and call `check_auth_rate_limit`. Return 429 with `{"error": "too_many_login_attempts", "retry_after": N}` on breach. Log the event at WARNING level.

### T-BE-02: Startup CORS production warning (G-07) — Sprint 1

**File:** `main.py`, `lifespan()` function

After the DB health check block, add:
```python
if os.environ.get("ENVIRONMENT", "development") == "production":
    if not os.environ.get("ALLOWED_ORIGINS", "").strip():
        logger.critical(
            "SECURITY: ALLOWED_ORIGINS is not set in production. "
            "CORS is open to all origins. Set ALLOWED_ORIGINS in Railway."
        )
```

### T-BE-03: Refresh token model and endpoint (G-02) — Sprint 2

**File:** `models.py`

Add a `RefreshToken` model:
- `id` UUID PK
- `user_id` FK → `users.id` (CASCADE DELETE)
- `token_hash` String(64) — SHA-256 of the opaque token, never store plaintext
- `expires_at` DateTime(timezone=True)
- `revoked_at` DateTime(timezone=True), nullable
- `created_at` DateTime(timezone=True)
- Index on `(user_id, revoked_at)` for efficient lookup

**File:** `auth.py`

Add `create_refresh_token(db, user) -> str` — generates `secrets.token_urlsafe(48)`, stores SHA-256 hash in `RefreshToken`, returns plaintext to caller once.

Add `rotate_refresh_token(db, raw_token) -> tuple[User, str]` — verifies hash, checks expiry and revocation, revokes old row, creates new refresh token + new access token. Raises 401 on any failure.

**File:** `routers/auth.py`

- Modify `login()` to return `TokenOut(access_token=..., refresh_token=..., token_type="bearer")`.
- Add `POST /api/v1/auth/refresh` accepting `{"refresh_token": "..."}`, calling `rotate_refresh_token`.
- Update `TokenOut` schema in `schemas.py` to add `refresh_token: str | None = None`.

### T-BE-04: Logout endpoint (G-03) — Sprint 2

**File:** `routers/auth.py`

Add `POST /api/v1/auth/logout` (requires `get_current_user`). Accepts optional `{"refresh_token": "..."}` body. Finds and revokes the `RefreshToken` row. Returns 204. Log the logout event.

### T-BE-05: SecurityHeadersMiddleware (G-08) — Sprint 3

**New file:** `middleware/security_headers.py`

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "0"  # modern browsers use CSP instead
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response
```

**File:** `main.py` — register `SecurityHeadersMiddleware` before `RateLimiterMiddleware`.

### T-BE-06: Dual-key secret rotation (G-05) — Sprint 3

**File:** `auth.py`

Modify `_decode_token()`:
```python
def _decode_token(token: str) -> dict:
    keys_to_try = [_secret_key()]
    prev = os.environ.get("JWT_SECRET_KEY_PREV", "")
    if prev:
        keys_to_try.append(prev)
    for key in keys_to_try:
        try:
            return jwt.decode(token, key, algorithms=[_algorithm()])
        except JWTError:
            continue
    raise HTTPException(status_code=401, detail="Invalid or expired token",
                        headers={"WWW-Authenticate": "Bearer"})
```

### T-BE-07: jti denylist (G-03a) — Sprint 3

**File:** `auth.py`

Add `jti` (UUID) to the JWT payload in `create_access_token()`. In `_decode_token()`, after successful decode, call `_is_jti_revoked(jti)` which checks Redis key `jti:{jti}`. If revoked, raise 401.

Add `revoke_jti(jti: str, ttl_seconds: int)` — sets `jti:{jti}` in Redis with expiry. Call from logout and from account deactivation paths.

### T-BE-08: Fix SQL injection in tenant_context (G-10) — Sprint 3

**File:** `middleware/tenant_context.py`

Replace:
```python
db.execute(f"SET LOCAL app.current_tenant = '{tenant_id}'")
```
With:
```python
from sqlalchemy import text
db.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": str(tenant_id)})
```

### T-BE-09: Login audit trail (G-11) — Sprint 4

**File:** `models.py`

Add to `User` model:
- `last_login_at: Mapped[datetime | None]` — nullable DateTime
- `failed_login_count: Mapped[int]` — Integer, default 0

Apply via `ALTER TABLE` in `database.py`'s `ensure_app_schema()` (consistent with existing pattern — no DROP TABLE).

**File:** `auth.py`, `authenticate_user()`

On success: update `user.last_login_at = datetime.now(tz=timezone.utc)`, reset `user.failed_login_count = 0`.
On failure: increment `user.failed_login_count`. If count exceeds env var `MAX_LOGIN_FAILURES` (default 10), set `user.is_active = False` and log a WARNING. The existing `is_active` check in `get_current_user` then handles token rejection.

---

## 5. DevOps Engineer Task List

### T-DO-01: Set ALLOWED_ORIGINS in Railway (G-07) — Sprint 1

In Railway dashboard for the SARO production service:

**Set environment variable:**
```
ALLOWED_ORIGINS=https://saro.vercel.app
```

If a custom domain is in use, add it as a comma-separated value:
```
ALLOWED_ORIGINS=https://saro.vercel.app,https://your-custom-domain.com
```

Do NOT leave this unset. The startup warning added in T-BE-02 will log a CRITICAL message to Railway Observability if it is missing.

### T-DO-02: Reduce token expiry (G-01) — Sprint 2

**Coordinate with T-BE-03 (refresh tokens) before deploying this change.** Deploying a shorter expiry before the refresh endpoint is live will cause all existing sessions to expire and lock users out with no way to renew.

Deploy order:
1. Deploy T-BE-03 (refresh endpoint) to Railway.
2. Then update the environment variable:
   ```
   ACCESS_TOKEN_EXPIRE_MINUTES=60
   ```
3. Trigger a Railway redeploy.

### T-DO-03: Configure Redis for auth operations (G-03a, G-06) — Sprint 3

The Railway Redis instance is already provisioned (`REDIS_URL`). Verify:
- Redis memory policy is `allkeys-lru` or `volatile-lru` — ensures TTL-expired jti keys are evicted under memory pressure.
- Redis persistence (`appendonly yes`) is enabled if you want the jti denylist to survive a Redis restart. If Redis restarts without persistence, revoked tokens become valid again for up to their remaining TTL period.

Set in Railway Redis config (or via `redis-cli CONFIG SET`):
```
maxmemory-policy volatile-lru
appendonly yes
```

### T-DO-04: Rotate JWT_SECRET_KEY (G-05) — Sprint 3

After T-BE-06 (dual-key support) is deployed:

1. Generate a new 256-bit secret:
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. In Railway dashboard:
   - Set `JWT_SECRET_KEY_PREV` = current value of `JWT_SECRET_KEY`
   - Set `JWT_SECRET_KEY` = new value
3. Redeploy. Existing tokens signed with the old key continue to work during their remaining TTL. New tokens are signed with the new key.
4. After the longest-lived existing token has expired (current: 8 hours; post-hardening: 1 hour), remove `JWT_SECRET_KEY_PREV`.

### T-DO-05: Document RS256 upgrade path (G-04) — Sprint 4

When a second backend service is added, switch from HS256 to RS256:

1. Generate RSA key pair:
   ```bash
   openssl genrsa -out jwt_private.pem 2048
   openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
   ```
2. Set `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` as Railway secrets (base64-encoded PEM).
3. Update `auth.py`: sign with private key, verify with public key. Consumer services receive only the public key.
4. Set `JWT_ALGORITHM=RS256` in Railway.

No implementation required now. Record this as an Architecture Decision Record when the second service is scoped.

---

## 6. What NOT to Change

These patterns are correct. Any PR that modifies them must have explicit justification from Venky (Lead) and Jordan Lee (Backend).

| Pattern | Location | Why it must be preserved |
|---|---|---|
| Lazy env var helpers (`_secret_key()`, `_algorithm()`, `_expire_minutes()`) | `auth.py:32–47` | Prevents KeyError crashes during Railway startup before secrets are injected. Reading at import time is a known deployment footgun. |
| Argon2id as primary hasher | `auth.py:69` | OWASP best practice; memory-hard; no 72-byte truncation. Do not reintroduce passlib. |
| Transparent bcrypt fallback | `auth.py:98–104` | Preserves existing user accounts without a data migration. Remove only after all bcrypt hashes have been re-hashed on next login (future sprint). |
| `get_current_user` re-fetches from DB | `auth.py:146–165` | This is what makes the `is_active` check effective in real time. Do not switch to pure-JWT (stateless) validation — it would break account deactivation. |
| Single error message for login failures | `routers/auth.py:98–101` | "Incorrect email or password" prevents username enumeration. Do not split into separate "user not found" vs "wrong password" messages. |
| `require_role` as a dependency factory | `auth.py:168–187` | Consistent pattern across all routers. Do not replace with ad-hoc `if current_user.role != ...` checks inline. |
| Fail-open rate limiter on Redis unavailability | `middleware/rate_limiter.py:102–103` | Correct availability-over-security trade-off for the rate limiter. A Redis outage should not take down SARO. The auth-specific per-IP rate limit (T-BE-01) should use the same fail-open pattern. |
| `bootstrap` 409 guard | `routers/auth.py:55–59` | Prevents re-bootstrapping after first user is created. This is the correct idempotency check. |
| `allow_credentials=False` when `allow_origins=["*"]` | `main.py:189` | This is technically required by the CORS spec. Changing it would either break browsers or require removing the wildcard. |

---

*Owner: Venky (Lead) | Contributors: Jordan Lee (Backend), Sam Patel / Taylor Kim (QA review of T-BE-03/04)*
*All PRs implementing this plan must pass `pytest tests/ -q` and target `venkybobby/SARO` main branch.*
