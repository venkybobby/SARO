# Tenant Onboarding Playbook

**Story:** STORY-373 · **Owner:** Venky · Companion:
[support-model.md](support-model.md) · [dr-backup.md](dr-backup.md) ·
cross-account setup: [../deploy/cross-account-onboarding.md](../deploy/cross-account-onboarding.md)

Onboarding tenant #2 should be a procedure, not a memory of how tenant #1 went.

---

## 1. Prerequisites

### ⛔ STOP — BAA gate (INV-6)

**Do not provision a tenant that may process PHI until a BAA is executed.**

- [ ] Signed BAA on file (see `compliance/baa/STORY-BAA-02_execution-package.md`)
- [ ] Data-flow diagram reviewed with the customer (`STORY-BAA-01`)
- [ ] Customer confirms which environments carry PHI

This is enforced in code, not just here: `saro tenant provision` **refuses**
without `--baa-confirmed`. A checklist item gets skipped under time pressure —
which is exactly when this one matters.

### Other prerequisites

- [ ] Commercial agreement signed; SLA shared ([../legal/sla-draft-v0.1.md](../legal/sla-draft-v0.1.md) — **counsel review still open**)
- [ ] Admin contact and email confirmed with the customer
- [ ] Security contact recorded for incident notification (**FND-067 — no field for this yet**)
- [ ] Customer's provider identified (Bedrock / Azure OpenAI / Vertex) and its coverage limits shared ([../adapter-capability-matrix.md](../adapter-capability-matrix.md))

---

## 2. Provision

```bash
saro tenant provision \
    --name "SummitCare Health" \
    --slug summitcare \
    --admin-email admin@summitcare.example \
    --vertical healthcare \
    --baa-confirmed
```

Creates: the tenant, a `super_admin` user, and a **disabled** log-source
placeholder. Writes an `ADMIN_ACTION` to the audit trail (STORY-366).

**The one-time password is printed once.** It is not stored, not logged, and
never appears in `--json` output — that would put it in shell history and CI
logs. If it is lost, issue a new credential rather than trying to recover it.

**Re-running is inert.** If the slug exists, nothing is written and the command
reports what it found. It deliberately does **not** reconcile drift: an operator
re-running to check state must not have configuration changed under them. See
FND-058 for what the opposite costs.

---

## 3. Manual steps (not scripted, on purpose)

1. **Cross-account log source** — the customer creates the read-only role; you
   complete the placeholder. Follow
   [../deploy/cross-account-onboarding.md](../deploy/cross-account-onboarding.md).
   Requires values only the customer can supply, so it is not automatable.
2. **Rule-pack subscriptions** — agree which packs apply, and share the
   capability matrix so coverage limits are understood *before* go-live rather
   than discovered in a report.
3. **Deliver the credential** out-of-band (not the same channel as the invite),
   and require a password change at first login.

---

## 4. Verification checklist

- [ ] `saro tenant verify-isolation --tenant <uuid>` → **PASS**
      (reports `meaningful: false` if this is the only tenant — re-run once a
      second exists, since isolation cannot be demonstrated against nothing)
- [ ] Admin can log in; login appears in the audit trail (FND-065)
- [ ] `GET /health` → 200 with `db_ok: true`
- [ ] Log-source config completed and `enabled: true`
- [ ] A first ingest produces records: `saro ingest --tenant <uuid> --window ... --dry-run`
- [ ] Tenant appears in the operator dashboard with zero findings (not an error state)

---

## 5. Rollback

Provisioning commits as one transaction, so a failure leaves nothing behind. To
remove a tenant provisioned in error:

1. **Confirm no evidence exists** — `saro tenant verify-isolation` row counts
   must be zero. **If any audit records exist, stop.** Evidence is
   append-only by design; deleting it is not a rollback, it is destruction of
   the thing SARO sells.
2. Disable the tenant rather than deleting it, unless it is provably empty.
3. Record the removal — it is an admin action and belongs in the audit trail.

There is deliberately no `saro tenant delete` command. A destructive operation
on evidence should require thought, not a flag.

---

## 6. Open gaps affecting onboarding

| Gap | Impact |
|---|---|
| **FND-067** — no tenant security-contact field | Incident notification (support-model §4) has nowhere to look up the recipient |
| **Named backup responder** unset (support-model §5) | Customer has no cover if the operator is unreachable |
| SLA counsel review outstanding | Cannot be issued as a contractual commitment yet |
