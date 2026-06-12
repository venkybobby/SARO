STORY-009: Fly.io Completion and Stack Freeze (S-1201)
Status: draft    Screen/Area: Infrastructure / Deployment

Goal
Resolve the saro-backend health-check failure, freeze the stack, and write the architecture of record. Draft until VERIFY V-3 (actual failure mode diagnosed — machine 2872750b090e28, region dfw). Closes FB-008/023/042.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the failing health check, When V-3 diagnosis runs (internal_port vs gunicorn bind 8080, health endpoint path, grace period — confirm, don't assume), Then the root cause is recorded in CONCERNS and the fix applied
AC-2: Given fly.toml, When configuration is reviewed, Then auto_stop_machines=false is set and verified
AC-3: Given the deployed backend, When 7 consecutive days elapse, Then health checks are green for the full window
AC-4: Given docs/ARCHITECTURE.md, When it is written, Then it states Fly.io + Supabase PostgreSQL + FastAPI v8.0 + Streamlit as the stack of record and is registered in DOCUMENT_REGISTER.md as superseding all conflicting statements
AC-5: Given the Railway deployment, When decommission completes, Then the procedure and date are documented

Edge Cases
- Health endpoint must not require auth or DB warm-up beyond the grace period.
- If Fly fix requires machine recreate, confirm Postgres connection strings unchanged (Supabase external — survives).

Out of Scope
- React migration — Streamlit is the frontend of record this phase.
- Multi-region scaling.

Non-Functional Requirements
CI smoke test hits the health endpoint post-deploy. Zero secrets in fly.toml.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
