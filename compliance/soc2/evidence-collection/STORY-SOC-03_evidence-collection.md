# STORY-SOC-03 — Evidence-Collection Wiring for the Observation Period

**Epic:** 15 — Trust & Compliance Enablement · **Workstream:** SOC 2 Type II
**Status:** DRAFT — layout + low-risk automation defined; **[HUMAN] cadence confirmation pending**
**Depends on:** STORY-SOC-02 (the matrix defines what to collect)
**Owner (artifact):** Jordan Lee (Backend/Infra) · **Reviewer:** Sam Patel (QA)
**Human gate:** Security owner confirms collection cadence meets the auditor's expectations

> **Purpose.** Type II proves controls operate **over time**. Evidence must be captured
> **continuously across the window, not reconstructed at the end.** This story defines the
> collection structure + low-risk automation for recurring evidence.
>
> **Hard constraint (AC-3 / DoD):** nothing here alters runtime behavior and nothing builds the
> missing controls themselves. The export automation is **read-only** — it reads git/CI/quality
> artifacts and writes an evidence bundle to an output dir; it never touches the app, the database,
> or the network.

---

## 1. Scope

**In scope:** the collection layout (per control: artifact, cadence, store); the STORY-404 schema
sufficiency check; low-risk recurring-evidence automation that doesn't touch runtime.

**Out of scope:** building missing controls (each is its own follow-on, SOC-02 §5); anything that
changes runtime behavior; WORM storage (client SIEM owns durable audit retention).

---

## 2. Evidence-collection layout (AC-1)

Per in-scope control: **what artifact** is captured, **how often**, **where** it's stored for the
auditor. Stores: **`git`** (in-repo, versioned) · **`CI`** (GitHub Actions run artifacts) ·
**`SIEM`** (client SIEM, system-of-record for runtime audit events) · **`DMS`** (secure document
management system — off-repo, per `docs/soc2-readiness-roadmap-v1.0.md` §6; **not committed**) ·
**`provider`** (Fly.io/Supabase console exports, manual).

| Control (SOC-02 ref) | Evidence artifact | Cadence | Store | Automated? |
|---|---|---|---|---|
| CC5/CC6 access controls | Auth/RBAC/persona code + tests; authz-denial logs (`auth.py` `_log_authz_denial`) | Per change + continuous logs | git + SIEM | ✅ export script (code state) |
| CC6.1 provisioning (SSO/SCIM) | `AuditEvent` rows (`sso_configured`, `scim_token_rotated`, `user_enrolled`) `models.py:464-483` | Continuous (event-driven) | DB → SIEM | 🟡 emitted at runtime; export = DB read |
| CC6.3 deprovisioning | Access-removal records | Continuous | DB → SIEM | ⛔ **blocked by G-SOC-01 (no API)** |
| CC6.2 privileged access / MFA | MFA-policy-change events (`mfa_policy_changed`); privileged-role assignments | Per change + quarterly review | DB + DMS | 🟡 partial (MFA optional — G-SOC-08) |
| CC6.6 access-change logging | Immutable `AuditEvent` stream | Continuous | DB → SIEM | ✅ runtime-emitted |
| CC7.3 vuln management | CI security-job artifacts (Bandit/Safety/TruffleHog) | Per PR + weekly scheduled | CI | ✅ export script (CI run refs) |
| CC8.1 change management | PR-merge records, CI gate results, quality-ratchet snapshots | Per PR | git + CI | ✅ export script |
| CC4.1 control monitoring | `quality/baseline.json` ratchet history; Prometheus counters | Per PR (ratchet) + continuous (metrics) | git + provider | ✅ export script (ratchet); 🟡 metrics |
| CC7.4 incident response | Incident records + `docs/incident-response-plan.md` | Per incident + annual review | DMS | ⬜ manual (during window) |
| CC7.2 monitoring | Log samples; health-check history; **Sentry (once wired — G-SOC-02)** | Continuous | provider + DMS | 🟡 partial |
| C1.x confidentiality | Redaction SLIs (`edge_redaction.py`); content-free audit-schema test | Per batch + per CI run | SIEM + CI | ✅ (schema test in CI) |
| CC6.8 / retention | Retention config; GDPR deletion certificates (`retention_service.py`) | Per erasure request + quarterly | DMS | ⬜ manual (event-driven) |
| A1.2 availability | `/health` + Fly.io health-check history; uptime | Continuous | provider | ⬜ manual export |
| A1.3 recovery / DR | DR-test record (**G-SOC-06**); Supabase PITR config | Semi-annual test | DMS | ⬜ manual (during window) |
| CC1.2 governance | Oversight minutes (**G-SOC-07**) | Quarterly | DMS | ⬜ manual |
| CC4.1 access review | Quarterly access-review records (**G-SOC-12**) | Quarterly | DMS | ⬜ manual |

> **Reading the table:** ✅ = the SOC-03 export script (§4) captures it read-only. 🟡 = partially
> automated / runtime-emitted but needs a periodic pull. ⬜ = manual capture during the window.
> ⛔ = cannot be collected until the underlying gap is closed.

---

## 3. STORY-404 audit-schema sufficiency check (AC-2)

SARO runs **two** audit streams; the auditor draws from both:

1. **Governance-runtime events** — `services/audit_emitter.py` (STORY-404). Content-free, per-tenant
   SHA-256 hash chain. Fields: `tenant_id, policy_version, trigger_mode, decision, rationale,
   evidence_pointers, actor, timestamp, input_hash, output_hash, latency_ms, fail_mode_applied,
   prev_hash, event_hash, chain_seq`. **This is decision-level evidence** (what SARO scored/decided).
2. **Application admin events** — `AuditEvent` ORM model `models.py:464-483` (`event_type` ∈
   `client_created, sso_configured, scim_token_rotated, user_enrolled, mfa_policy_changed,
   sso_test_passed/failed`). **This is the access/change stream** the auditor needs for CC6.x.

### Does STORY-404's schema suffice for the auditor?

| Auditor need | 404 field that covers it | Sufficient? |
|---|---|---|
| Who acted | `actor` | ✅ |
| When | `timestamp` | ✅ |
| What was decided + why | `decision`, `rationale`, `evidence_pointers` | ✅ |
| Which policy was in force | `policy_version` | ✅ (ties to STORY-401 policy version) |
| Tamper-evidence / ordering | `prev_hash`, `event_hash`, `chain_seq` (per-tenant chain) | ✅ |
| No raw content leakage (confidentiality) | `input_hash`/`output_hash` only, no raw content | ✅ (pinned by schema test) |

**Verdict: STORY-404's schema is sufficient for the *decision-level* (Measure/Manage) evidence it is
designed to carry — do not re-open 404 to add fields for it.**

### Fields the auditor needs that STORY-404 does NOT carry (flag, don't force into 404)

These are **not** 404 gaps — they belong to the admin `AuditEvent` stream (#2) or to manual capture.
Flagging them so 404 isn't wrongly re-opened:

- **Access provisioning/deprovisioning + role changes** → live in the `AuditEvent` (`models.py`)
  stream, not the governance-runtime stream. **Deprovisioning events don't exist yet** (G-SOC-01) —
  that's a control gap, not a schema gap.
- **`request_id` / correlation to an HTTP request** → neither stream carries a request-correlation
  id today; if the auditor wants request-level traceability, add it to the **admin `AuditEvent`**
  stream, not 404. (Candidate follow-on — low risk.)
- **Actor authentication method (MFA used?)** → not in either stream; would attach to the admin
  event, tied to G-SOC-08.

> **Net:** confirm 404 sufficient for decision-level evidence ✅. The only auditor-required fields it
> lacks are access/identity fields that **belong to the admin stream by design** — captured there,
> not by widening 404. One genuinely-missing item (deprovisioning events) is a **control** gap
> (G-SOC-01), tracked in SOC-02, not a 404 schema change.

---

## 4. Low-risk recurring-evidence automation (AC-3)

`export_soc2_evidence.py` (this directory) — a **read-only** collector that snapshots recurring
evidence into a timestamped bundle for the auditor. It:

- reads **git history** (change-management: recent merges/commits), `quality/baseline.json` (quality
  ratchet), `tests/regression/manifest.yaml` (regression coverage), and the CI workflow inventory;
- writes a JSON manifest + copies to an output dir (default `compliance/soc2/evidence-collection/_exports/`, git-ignored);
- **makes no network calls, touches no database, imports no app module, and changes no runtime
  behavior.** It only reads repo artifacts and writes under the output dir.

Intended cadence: run on a schedule (e.g. a weekly GitHub Actions job) and/or on demand before a
fieldwork checkpoint. A sample scheduled-job stanza is documented in the script header; **wiring it
into CI is left for the human gate to approve** (it adds a workflow, which the security owner should
sanction). Access-review and provider (Fly.io/Supabase IAM, uptime) exports remain **manual** — they
live off-repo and require console access the script deliberately does not have.

```bash
# On demand (read-only):
python compliance/soc2/evidence-collection/export_soc2_evidence.py --out compliance/soc2/evidence-collection/_exports
```

---

## 5. Cadence confirmation — **[HUMAN] gate (AC-4)**

> The security owner confirms the collection cadence meets the auditor's expectations. Claude Code
> cannot confirm cadence with an external auditor. Open until a human signs off.

| Field | Value |
|---|---|
| **Auditor's evidence cadence expectations gathered** | ⬜ |
| **Per-control cadence (§2) confirmed adequate** | ⬜ |
| **Automated export scheduled (workflow approved)** | ⬜ (script ready; scheduling needs approval) |
| **Manual-capture owners assigned (⬜ rows in §2)** | ⬜ |
| **Confirmed by (security owner)** | _____________________ |
| **Date** | _____________________ |

---

## 6. Definition of done (tests)

- [x] **Every in-scope control has a defined evidence-capture path** — §2 table (automated / partial / manual / blocked-by-gap).
- [x] **404-schema sufficiency confirmed or gap flagged** — §3: sufficient for decision-level evidence; access/identity fields belong to the admin stream (not a 404 change); deprovisioning is a control gap (G-SOC-01).
- [x] **No runtime behavior changed** — the export script is read-only; no app import, no DB, no network (§4).
- [ ] **Security owner confirms cadence** — §5 human gate, open.

## CHANGES MADE
- Defined the per-control evidence-collection layout (artifact / cadence / store / automated?) across
  the three in-scope TSC categories, tied to SOC-02's controls and gaps.
- Ran the STORY-404 schema sufficiency check: sufficient for decision-level evidence; documented that
  access/identity fields belong to the admin `AuditEvent` stream (so 404 is not re-opened), and that
  the one truly-missing item (deprovisioning events) is a control gap (G-SOC-01), not a schema gap.
- Added `export_soc2_evidence.py`, a read-only recurring-evidence collector (no runtime touch).

## THINGS I DIDN'T TOUCH
- Runtime code, the database, `services/audit_emitter.py` schema (confirmed sufficient — not re-opened).
- The missing controls themselves (deprovisioning API, Sentry, DR test) — each its own follow-on.
- CI workflow wiring for the scheduled export — script is ready; scheduling awaits the human gate.

## POTENTIAL CONCERNS
- **⬜/⛔ rows depend on humans or on closing gaps.** Access reviews, uptime, DR tests, governance
  minutes are manual; deprovisioning evidence (⛔) can't be collected until G-SOC-01 ships.
- **Off-repo evidence store (DMS) is assumed, not provisioned.** The roadmap names `soc2-evidence/`
  (uncommitted); confirm the secure store exists before the window opens or evidence has nowhere to go.
- **Two audit streams must both be exported.** An auditor looking only at the 404 governance stream
  would miss access/change events (admin `AuditEvent`); the collection plan pulls both.
