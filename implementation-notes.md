# demo-runbook-gcp-worked-example — concrete GCP values for the Vertex export setup
Stage: trivial

Single-file docs change (follow-up to merged PR #138). The runbook's Part 2
placeholders are filled with the VeriAegis demo environment as a worked
example, and a new §2.4 documents creating SARO's read-only reader principal
(`saro-reader@project-b73b6bc1-e4a6-4ee1-961.iam.gserviceaccount.com`) with a
bucket-scoped `roles/storage.objectViewer` grant — answering "what is SARO's
service account email": it is customer-created, per SARO's no-own-credentials
posture (INV-6), and never sets tenancy (INV-3).

No code, tests, or generated artifacts touched; runner output unchanged, so
the screencast byte-sync pin is unaffected.

Second commit (same PR, owner request): pause all Anthropic-API-spending
GitHub Actions. `loops/limits.yaml` sets `enabled: false` for pr-babysitter,
ci-sweeper, and security-sweeper (the limits.yaml operator runbook's auditable
path; halted guards go GREEN). `claude-interactive.yml` gains a
`vars.CLAUDE_INTERACTIVE_ENABLED == 'true'` gate (off by default, re-enable
via repo variable without a commit). Non-Anthropic loops (changelog-drafter,
dependency-sweeper, post-merge-cleanup) stay enabled — they spend no Anthropic
tokens. tests/test_loop_guard.py: 21 passed.

## Deviations
None.
