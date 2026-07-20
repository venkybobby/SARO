# STORY-372: Status & Degradation Communication

**Status:** ready
**Screen/Area:** Ops (Pack Epic 16)
**Depends on:** STORY-368 canary

## Goal
A public status surface for both apps plus a documented maintenance-window
announcement procedure.

## Acceptance Criteria
- AC-1: Minimal static status page fed by the STORY-368 canary (GitHub Actions
  writes status JSON to a gh-pages-style artifact or the frontend serves a
  `/status` page reading the canary output). Hosted-SaaS option documented as
  the human-gated alternative.
- AC-2: Maintenance-window announcement procedure documented (`docs/ops/maintenance-windows.md`).
- AC-3: Linked from the SLA doc (STORY-369).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
