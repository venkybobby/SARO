# Skill: SARO Codebase Standards

Apply these rules automatically on every coding task in the SARO platform.

## Output Rules

- **Show only changed code** — never output full files. Show diffs or changed sections only.
- **End every coding task** with this exact summary block:
  ```
  FILES CHANGED: [file path] — [what changed]
  FILES NOT TOUCHED: [file path] — [why left alone]
  CONCERNS: [any risks, follow-up needed, or TODOs]
  ```
- **Integrated delivery only** — all code goes into `github.com/venkybobby/saro-platform`. Never create standalone repos, separate folders, or detached scripts.
- **"Execute" or "proceed"** means act immediately — do not re-summarize the plan.

## Code Quality Rules

- Propose the simplest solution first. Ask before adding complexity.
- Ask, don't assume — surface ambiguity before implementing.
- Confirm before any destructive action (deletes, schema changes, endpoint removals).
- Stay in scope — do not refactor, clean, or touch code outside the stated task.
- No hardcoded secrets (JWT secrets, API keys, DB connection strings).

## Version Standard

- Platform version is locked at **8.0.0** across all files. Do not introduce version drift.
- Version string locations: `package.json`, `pyproject.toml`, `config/settings.py`, `__init__.py`, API response headers, health check endpoint, and any README badges.

## Async / Concurrency Rules

- No `time.sleep()` in async contexts — use `await asyncio.sleep()`.
- All database calls must be async-safe for Neon PostgreSQL.
- Redis session management: use the patched async client pattern from `auth.py` (post March 2026 fix). Do not reintroduce blocking patterns.

## Auth Rules

- JWT secret must come from environment variable — never hardcoded.
- `DELETE /auth/logout` endpoint must exist and invalidate the Redis session token.
- PWA router must be registered at app startup.

## Language Preferences

Python (primary backend), TypeScript/JavaScript (frontend/API clients), Go/Rust (performance-critical), Java/Kotlin (enterprise integrations).

## Environment

- Developer OS: Windows with PowerShell/CMD and Miniconda
- Deployment: Koyeb (primary), Neon PostgreSQL (DB)
- Python package installs: always use `--break-system-packages` if outside venv
