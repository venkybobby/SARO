# SARO Disaster Recovery — Backups, Restore, and Evidence Integrity

**Story:** STORY-370 · **Owner:** Venky · **Created:** 2026-07-21
**Status:** procedure ready; **RTO/RPO not yet measured** — see §6.

Companion: [alerts.md](alerts.md) A7 · [runbooks.md](runbooks.md) ·
[slo.md](slo.md) · script: `scripts/verify_restore_integrity.py`

---

## 1. What must survive, and why

SARO's product is evidence. A restore that brings the service back but loses or
alters audit chains has failed even if the API responds — a customer's
compliance position depends on the chain being complete, not merely present.

| Asset | System of record | Loss impact |
|---|---|---|
| TRACE / audit chains, scan reports | Supabase PostgreSQL | **Critical** — the evidence itself |
| Self-audit chain (`audit_events`) | Supabase | **Critical** — SARO's own operations record |
| Published rule-pack snapshots | Supabase (`rule_pack_snapshots`) | **Critical** — attestations reference exact versions (INV-7) |
| Tenant/user/config records | Supabase | High — recoverable by re-provisioning, but access is lost meanwhile |
| Rule-pack YAML source | Git | Low — version-controlled and reproducible |
| Application code / migrations | Git | Low — redeployable |
| Customer log exports | **Customer-owned storage** | Not SARO's to lose (INV-6, read-only) |

---

## 2. Backup inventory — **CONFIRM, do not assume**

These are provider console settings. This repository cannot observe them, so
they are written as an unchecked checklist rather than asserted as fact. Tick
each one only after looking at the console.

### Supabase (system of record)

- [ ] **CONFIRM** the project's plan includes Point-In-Time Recovery (PITR), and
      record the retention window (Pro tier is typically 7 days — verify).
- [ ] **CONFIRM** daily automated backups are enabled and record their retention.
- [ ] **CONFIRM** the most recent backup's timestamp and that it is recent.
- [ ] **CONFIRM** who besides the operator can initiate a restore (bus-factor).
- [ ] **CONFIRM** backups are encrypted at rest by the provider.

### Rule-pack snapshots

- [ ] **CONFIRM** an off-platform copy exists. Published snapshots are immutable
      by design (INV-7), but immutability is not durability — an immutable row
      in a lost database is lost. Export periodically to object storage.

### Integrity manifests (see §4)

- [ ] **CONFIRM** a manifest is captured with each backup and stored
      **off-platform**, alongside it.

> **Why off-platform matters.** A manifest stored only in the database it
> describes is destroyed by the same event it is meant to detect, and would in
> any case be restored *along with* whatever corrupted state you are checking —
> agreeing with itself perfectly and proving nothing.

---

## 3. Restore procedure

**Never rehearse against production.** Restores are performed to a **scratch
project**; production restore happens only during a real incident, under the
incident response plan.

1. **Declare the incident** (IRP) and stop write traffic if the service is up.
2. **Choose the restore target** — PITR timestamp or the backup to restore.
   Record it; the gap between it and the incident is your RPO for this event.
3. **Restore into a scratch project first** where feasible, so verification
   happens before anything customer-facing is repointed.
4. **Apply migrations** if the restored schema predates the running image
   (`/health` returns `schema_mismatch` when it does — alerts.md A3).
5. **Verify evidence integrity — before resuming traffic** (§4).
6. **Repoint** `DATABASE_URL` (secrets-runbook §3) and confirm `/health`.
7. **Resume traffic**, then run the canary manually to confirm the product path.
8. **Record timings** in §6 and write the post-mortem (IRP §10).

---

## 4. Evidence-integrity verification (the step that is easy to get wrong)

SARO has eight hash-chain verifiers. **Every one proves a chain is internally
self-consistent; none proves it is the same chain you had before.** A truncated
chain hashes correctly — restore a backup missing the last 400 events and every
verifier reports `valid: true` while evidence is silently gone.

Verification therefore compares against a reference captured **before** the loss:

```bash
# Routinely, with every backup — store the manifest OFF-PLATFORM:
python scripts/verify_restore_integrity.py snapshot \
    --out manifest-$(date -u +%F).json --label "nightly-backup"

# After a restore, BEFORE resuming traffic:
python scripts/verify_restore_integrity.py verify \
    --reference manifest-2026-07-21.json --out restore-report.json
```

| Verdict | Meaning | Action |
|---|---|---|
| `MATCH` | Tip hash and record count match | Proceed |
| `AHEAD` | More records than the reference | **Stop** — traffic resumed before verification; re-verify from a later manifest |
| `DATA_LOSS` | Fewer records; chain self-consistent but incomplete | **Do not resume.** The delta is your measured RPO. Notify affected tenants per support-model §4 |
| `TAMPER` | Count matches, tip differs — or the chain fails its own verification | **Do not resume.** Treat as a security incident (IRP) |
| `MISSING` | A whole chain family absent | **Do not resume.** Most severe: nothing fails when nothing is there |

A `DATA_LOSS` or `TAMPER` result is a customer-notifiable event, not just an
operational one — evidence integrity is the product.

---

## 5. Rehearsal procedure (AC-4)

**Scratch environment only. Never production.**

1. Create a scratch Supabase project.
2. Capture a manifest from production (read-only — `snapshot` performs no writes).
3. Restore the most recent production backup **into the scratch project**.
4. Apply migrations; run `verify --reference` against the manifest.
5. Time each phase and record below.
6. Delete the scratch project. It holds real evidence data and must not linger.

---

## 6. Measured RTO / RPO — **[HUMAN — OPEN]**

**Not yet measured.** These fields stay blank until a rehearsal fills them.
Plausible-looking numbers written before rehearsing would be a commitment with
no evidence behind it (CLAUDE.md FM-1), and DR numbers are exactly the kind a
buyer relies on.

| Metric | Target | **Measured** | Date | Notes |
|---|---|---|---|---|
| RTO (declare → service restored) | — | **not yet measured** | — | fill from rehearsal |
| RPO (max acceptable data loss) | bounded by PITR window | **not yet measured** | — | confirm the window in §2 first |
| Restore duration (backup → schema ready) | — | **not yet measured** | — | |
| Verification duration | — | **not yet measured** | — | |

Once measured, the SLA (STORY-369) and any customer DR commitment may reference
these numbers — **and not before**.

---

## 7. Alerting

Backup-verification failure is alert **A7** ([alerts.md](alerts.md)). The
manifest-capture job failing means the next restore has no reference to verify
against — an unverifiable backup is a belief, not a control.
