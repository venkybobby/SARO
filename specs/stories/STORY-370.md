# STORY-370: DR & Backup — Verified Restore, RTO/RPO

**Status:** ready (rehearsal execution human-gated)
**Screen/Area:** Ops docs + scripts (Pack Epic 16)

## Goal
DR is a tested procedure with stated RTO/RPO: backup inventory documented,
restore runbook with attestation-hash verification, rehearsal procedure ready to
execute against a scratch project.

## Acceptance Criteria
- AC-1: Backup inventory doc (`docs/ops/dr-backup.md`): Supabase PITR/backup
  settings (documented as config-to-confirm checklist), rule-pack snapshot
  immutability + off-platform copy plan.
- AC-2: Restore runbook incl. post-restore attestation-hash verification step
  (script: recompute hash chain over restored traces, compare to exported
  evidence) — proves evidence integrity survived.
- AC-3: Verification script committed (`scripts/verify_restore_integrity.py`)
  and unit-tested against fixture data.
- AC-4 **[HUMAN — OPEN]**: rehearsal executed to a scratch project; timings
  recorded → stated RTO/RPO filled in. Never prod.
- AC-5: Backup-failure alerting hooked into STORY-368 alert doc.

## Out of Scope
- Executing the rehearsal (operator action on Supabase account).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
