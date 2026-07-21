# Tabletop Exercise — Leaked Credential

**Date:** 2026-07-21 · **Facilitator/participant:** Venky (solo) ·
**Duration:** ~45 min, desk exercise · **Story:** STORY-371 AC-3
**Scenario basis:** FND-003 — a plaintext `super_admin` credential was committed
to the public repository. A real historical exposure, chosen over an invented
one so the walkthrough hits real files and real gaps.

> **Nothing in this exercise was executed.** No credential was rotated, no
> production system was touched. Where a step could not be completed on paper,
> that is recorded as a gap rather than assumed to work.

---

## Scenario

> 09:40 CT, Tuesday. A security researcher emails `security@saro.app`: a
> `super_admin` password is visible in the public `venkybobby/SARO` git history.
> They have not used it. They intend to publish a write-up in 7 days.

---

## Walkthrough

### T+0 — Detection and triage

Detected by **external report**, not by SARO. Correct per current controls:
gitleaks (STORY-363) blocks *new* secrets on the current tree, and the
full-history scan is deliberately report-only, so a historical secret does not
block every build. Nothing scans history and pages anyone.

Severity: **S1** — credential exposure, per support-model §2. Response target 1
business hour; this arrived in hours, so the target applies and is met.

### T+10 — Establish exposure

Questions asked, and whether the repo can answer them:

| Question | Answerable today? |
|---|---|
| Is the credential still valid? | ✅ attempt a login with it |
| Was it used by anyone else? | ❌ **no** — see Gap 1. This is the finding that matters most |
| Which tenants could it reach? | ✅ `super_admin` — all of them |
| Was any evidence altered? | ✅ hash-chain verification, `GET /api/v1/audit/verify-chain` |

### T+20 — Containment

Follow `docs/security/secrets-runbook.md` §3: rotate in the store of record,
verify `/health`, confirm the old credential is dead, log the rotation.

**Gap found immediately (Gap 2):** rotating the password does **not** invalidate
already-issued JWTs. A token minted with the leaked credential stays valid until
expiry. There is no session-revocation path.

### T+40 — Assess evidence integrity

Run chain verification per tenant. If it passes, the strongest available
statement is *"no evidence record was altered"* — which is the question a
compliance customer will actually ask. This is the part of the platform that
held up best in the exercise.

### T+60 — Customer notification

Per support-model §4: no confirmed *reportable* incident (no evidence of misuse),
but a credential capable of cross-tenant access was exposed. Decision: **notify
affected tenants within 72 hours** with scope, actions taken, and the integrity
verification result. Do not wait for the researcher's publication date.

**Gap 3:** there is no notification template or tenant-contact list. Drafting one
under time pressure is exactly when wording goes wrong.

### T+1 day — Post-mortem

Template now exists (IRP §10, added by this story — it did not exist when the
exercise started).

---

## Gaps found

| # | Gap | Severity | Disposition |
|---|---|---|---|
| **1** | No way to answer "was this credential used, and by whom?" — auth events are recorded, but there is no query or view that reconstructs a session history for one credential | High | **FND-065** (open) |
| **2** | Password rotation does not invalidate live JWTs — no session-revocation or token-version mechanism | High | **FND-066** (open) |
| **3** | No customer breach-notification template and no maintained tenant security-contact list | Medium | **FND-067** (open) |
| **4** | Nothing scans git *history* on a schedule; the full-history gitleaks scan is report-only and would not have raised this | Medium | Accepted for now — rotation is the real control for a public-repo exposure (secrets-runbook §5). Revisit if repo visibility changes. |
| **5** | No named backup responder — a solo operator unreachable during an S1 has no cover | High | Already tracked: support-model §5 **[HUMAN — OPEN]** |

---

## What worked

- The secrets runbook (STORY-363) gave a followable containment procedure with a
  verification step, so containment was not improvised.
- Hash-chain verification answered the integrity question directly and quickly.
- Severity classification and the 72-hour notification clock were unambiguous —
  the support model was written the day before and survived first contact.
- `gitleaks` prevents a recurrence of the *forward* case.

## What did not

- **Detection depended entirely on a stranger's goodwill.** A researcher who
  chose to sell rather than report would have had a working `super_admin`
  credential and, per Gap 2, a session that outlived rotation.
- Two of the five gaps (1 and 2) mean SARO could not fully answer *"what did they
  do?"* — the question that determines whether an exposure is reportable.

## Actions

| # | Action | Type | Owner | Due |
|---|---|---|---|---|
| 1 | Credential-usage reconstruction from auth events (FND-065) | detect | Venky | before pilot conversion |
| 2 | Token revocation on password change (FND-066) | prevent | Venky | before pilot conversion |
| 3 | Breach-notification template + tenant security-contact list (FND-067) | mitigate | Venky | before pilot conversion |
| 4 | Name a backup responder (support-model §5) | mitigate | Venky | before pilot conversion |
| 5 | Complete the FND-003 rotation still open in secrets-runbook §4 | prevent | Venky | now |

**Next exercise:** January 2027 (IRP §9). Suggested scenario: cross-tenant data
exposure via a rule-pack or export path — exercises a different control set.
