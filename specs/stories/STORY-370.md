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
| AC-1 | `test_dr_doc_exists_with_backup_inventory`, `test_dr_doc_marks_provider_settings_as_to_confirm_not_asserted` | `docs/ops/dr-backup.md` §1–§2 |
| AC-2 | `test_dr_doc_requires_the_manifest_to_be_stored_off_platform`, `test_dr_doc_forbids_rehearsing_against_production` | `docs/ops/dr-backup.md` §3–§5 |
| AC-3 | 13 unit tests incl. `test_truncated_chain_is_caught_even_though_it_verifies_internally` | `scripts/verify_restore_integrity.py` |
| AC-4 | **[HUMAN — OPEN]** `test_rto_rpo_are_blank_until_the_rehearsal_measures_them` | `docs/ops/dr-backup.md` §6 |
| AC-5 | `test_a7_alert_is_wired_rather_than_a_placeholder` | `docs/ops/alerts.md` A7 |

## The insight this story turns on
SARO already has **eight** hash-chain verifiers. Every one proves a chain is
*internally self-consistent*; **none** proves it is the same chain as before an
incident. A truncated chain hashes correctly — restore a backup missing 400
events and all eight report `valid: true` while evidence is silently gone.

So verification compares against a **reference manifest captured before the
loss** (tip hash + record count per chain), stored **off-platform**. Count and
tip fail differently and are both needed:

| Count | Tip | Verdict |
|---|---|---|
| equal | equal | `MATCH` |
| equal | differs | `TAMPER` — content changed |
| lower | any | `DATA_LOSS` — the delta **is** the measured RPO |
| higher | any | `AHEAD` — verified after traffic resumed (procedural error) |
| absent | — | `MISSING` — nothing fails when nothing is there |

`DATA_LOSS`/`TAMPER` are customer-notifiable (support-model §4), not merely
operational — evidence integrity is the product.

## RTO/RPO deliberately blank
Numbers are **measured by the rehearsal**, not estimated. Writing plausible
values before rehearsing would be a commitment with no evidence behind it
(FM-1), and DR figures are exactly what a buyer relies on. Pinned by test.

## Human gate
**AC-4 [HUMAN — OPEN]:** rehearsal to a **scratch project only** — never
production. Procedure in §5; §6 has the table to fill. Also §2's provider
checklist: the repo cannot see the Supabase console, so backup settings are
written as unchecked confirmations rather than asserted.
