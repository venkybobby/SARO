---
name: ci-debugger
description: Autonomous CI failure diagnosis and fix for SARO. Triggered when CI is red on a PR, tests fail in the stop hook, or a deploy fails on Railway. Diagnoses root cause and pushes a fix without human intervention where possible.
---

Diagnose and fix CI failures autonomously. Follow this protocol in order.

## Step 1 — Collect Failure Context
- Fetch CI logs for the failing job (use mcp__github__get_job_logs)
- Identify the first failing line — not the cascade, the root cause
- Categorise: test failure | import error | lint error | type error | build error | deploy error

## Step 2 — Diagnose by Category

**Test failure**
- Read the failing test and the function it tests
- Determine: logic bug in implementation, or test assertion is wrong?
- Never delete or weaken a test to make CI pass — fix the implementation

**Import / ModuleNotFoundError**
- Check `requirements.txt` — is the package listed?
- Check if a new file has a circular import
- Fix: add to requirements or resolve the import cycle

**Lint / format error (ruff, black)**
- Run `ruff check . --fix` and `black .` locally, then commit

**Type error (mypy)**
- Read the full error; fix the type annotation — do not use `# type: ignore` unless the library has no stubs

**Build / Docker error**
- Read Dockerfile and railway.toml
- Check if a new dependency needs to be added to the build stage

**Railway deploy failure**
- Check health endpoint: `GET /health` must return `{"app":"SARO","db_ok":true}`
- Check env vars: `$PORT`, `$DATABASE_URL`, `$REDIS_URL` injected by Railway
- See deploy-railway skill for full topology

## Step 3 — Apply Fix
- Edit the minimum files needed
- Run `pytest tests/ -q --tb=short` locally to confirm fix
- Commit with `fix(ci): <root cause description>`
- Push to the same branch — do not open a new PR

## Step 4 — Verify
- Confirm CI re-run is triggered by the push
- Subscribe to PR activity if not already watching
- Report: root cause, fix applied, files changed

## Rules
- Never use `--no-verify` to skip hooks
- Never force-push
- Never mock away a real failure to make tests green
- If the failure is in a third-party service (Supabase down, Railway outage), report it and wait — do not retry infinitely
