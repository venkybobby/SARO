# Story Specs

One file per story. Workflow — nothing is ever pasted into chat:

1. Copy `_TEMPLATE.md` → `STORY-###.md`, fill it in, set Status: ready.
2. In Claude Code: `/story STORY-###`
3. The command enforces Definition of Ready, the TDD loop, all gates,
   independent review, and the regression/ratchet policies automatically.

A story with missing acceptance criteria will be rejected at step 0 —
underspecified stories are the root cause of review churn.
