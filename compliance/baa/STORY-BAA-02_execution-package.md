# STORY-BAA-02 — BAA Execution Package & Tracking

**Epic:** 15 — Trust & Compliance Enablement · **Workstream:** BAA
**Status:** DRAFT — tracker OPEN; **execution gate incomplete (no PHI until signed)**
**Depends on:** STORY-BAA-01 (the approved data-flow diagram informs scope)
**Owner (artifact):** Venky (Lead) · **Reviewer:** Jordan Lee (Backend/Infra)
**Executors (human gate):** SummitCare counsel + SARO

> **Purpose.** Package what's needed to get the BAA signed with the right AI-processing exhibits,
> and track it to signature.
>
> **Not legal advice / not binding language.** Every item below is framed as an **item for counsel
> to confirm**, not as final contract language. SummitCare/SARO counsel own the binding text and the
> signature. This artifact is a checklist + tracker, nothing more.

---

## 1. Scope of this artifact

**In scope:** a requirements checklist of BAA components relevant to AI processing + exhibit
outlines + a status tracker to signature.

**Out of scope:** drafting binding legal language (counsel owns this); the signature itself
(human gate, AC-4); the data-flow diagram (STORY-BAA-01).

---

## 2. BAA component checklist — AI processing (AC-1)

> **Framing:** each row is an *item for counsel to confirm*. "Draft note" is engineering context to
> inform counsel, **not** proposed contract wording. HIPAA §164.504(e) is the reference frame for
> required BAA provisions; the AI-processing angle is what SARO adds context on.

| # | BAA component (AI-processing lens) | Item for counsel to confirm | Engineering draft note (context only) |
|---|---|---|---|
| C-1 | **Sub-processor list** | Full, current sub-processor inventory attached as an exhibit; flow-down BA obligations to each | SARO stack of record: **Fly.io** (compute, `dfw`) + **Supabase** (Postgres, RLS). See `docs/sub-processors.md` — ⚠️ that file still lists Railway/Streamlit and must be reconciled to the PT-012 stack (`docs/ARCHITECTURE.md`) before it goes into the BAA exhibit. |
| C-2 | **Breach-notification terms** | Notification trigger, timeline (e.g. without unreasonable delay / contractual clock), content, and channel | SARO incident-response process: `docs/incident-response-plan.md`. Content-free audit events (`services/audit_emitter.py`) aid breach *scoping* (what was touched) without exposing PHI. |
| C-3 | **Permitted uses & disclosures** | The only permitted use is the audit/evaluation purpose; no secondary use, no training on customer data | SARO accepts only `prompt` + `raw_output`, returns only score/TRACE/remediation, and **never generates the audited output** (CLAUDE.md Non-Negotiables 1–2). Core scoring makes zero external-model calls (SARO-102). |
| C-4 | **De-identification handling** | Whether de-identified data (Safe Harbor) is carved out of BAA obligations; treatment of the **residual-PHI path** | Edge redaction is **rule/catalog-based and not total** — residual PHI can cross the boundary (STORY-BAA-01 §1, path 3). Counsel decides the carve-out line; SARO supplies the residual-identifier SLI as the measured basis. |
| C-5 | **Data return / destruction** | On termination: return or destroy PHI; certification of destruction; timeline | SARO retains **no raw PHI** and only per-tenant chain *lineage* (head hash + seq), not event bodies (`audit_emitter.py` AC-4). Client SIEM is system-of-record. Existing DPA templates: `docs/legal/saro-dpa-template-v1.0.md`, `docs/dpa-template.md`. |
| C-6 | **Audit rights** | Customer's right to audit SARO's safeguards; evidence SARO will make available; frequency | SARO's own audit trail (content-free, per-tenant SHA-256 hash chain) + SOC 2 Type II evidence (Epic 15 SOC workstream, **in progress — not yet attested**). |
| C-7 | **Minimum-necessary / data-minimization** | Confirm SARO's minimal data intake satisfies minimum-necessary | Intake is `prompt` + `raw_output` only; no client-system read/write (Non-Negotiables 3 & 6, read-only posture). |
| C-8 | **Safeguards (admin/technical/physical)** | Reference SARO's technical safeguards + inherited provider safeguards | Tenant isolation (Supabase RLS + app-layer filters), JWT RBAC (`auth.py`), TLS in transit; host/physical inherited from Fly.io/Supabase (see `docs/ARCHITECTURE.md` shared-responsibility split). |
| C-9 | **Sub-processor change notice** | Advance-notice mechanism before adding/changing a sub-processor | Governed by `docs/VENDOR_CONTINUITY_PLAN.md` (PT-012 freeze; provider change requires documented exception + customer notice). |

**Exhibit outlines (attach to the BAA — counsel finalizes):**
- **Exhibit A — Sub-processor list** (from a *reconciled* `docs/sub-processors.md`).
- **Exhibit B — Data-flow & residency diagram** (STORY-BAA-01, once Privacy-Office-approved).
- **Exhibit C — Technical & organizational safeguards** (SOC 2 control matrix, STORY-SOC-02).
- **Exhibit D — Permitted-use / no-secondary-use statement** (SARO Non-Negotiables).

---

## 3. Narrowed-scope note (AC-2)

> **Where narrowed BAA scope is possible if edge redaction is proven.**

If the Privacy Office and counsel accept that SARO holds **mostly de-identified data** — because
edge redaction (`services/edge_redaction.py`) runs at the SummitCare boundary and its per-batch
residual-identifier SLI stays below an agreed threshold — then BAA obligations may be **narrowed to
the residual-PHI path only**, rather than treating all ingress as full PHI.

**This narrowing is conditional, not automatic. It requires, at minimum:**
1. An **agreed residual-identifier SLI threshold** and evidence it is met on representative data.
2. Acknowledgement that rule-based redaction **does not catch free-text PHI** (STORY-BAA-01 §1) — so
   the residual path never reaches zero and some BAA coverage always remains.
3. The **BYOC production topology** (STORY-BAA-01 §4 Variant B) narrows scope further by keeping the
   runtime in SummitCare's own VPC — but the pilot uses the PrivateLink variant (A), where SARO is
   the Business Associate and scope is broader.

**Do not present the narrowing as achieved.** It is a *possibility to negotiate*, gated on the SLI
evidence and counsel's judgment.

---

## 4. Status tracker (AC-3)

**Legend — Status:** ⬜ Not started · 🟨 In progress · ✅ Complete · **Blocking?** = does an
unfinished state block first PHI flow?

| # | Component | Owner | Status | Blocking? |
|---|---|---|---|---|
| C-1 | Sub-processor list (reconcile to PT-012 stack first) | Jordan Lee | ⬜ | No (but must precede Exhibit A) |
| C-2 | Breach-notification terms | SummitCare counsel + Venky | ⬜ | **Yes** |
| C-3 | Permitted uses & disclosures | SummitCare counsel | ⬜ | **Yes** |
| C-4 | De-identification handling (residual-path treatment) | Privacy Office + counsel | ⬜ | **Yes** |
| C-5 | Data return / destruction | Venky + counsel | ⬜ | **Yes** |
| C-6 | Audit rights | Jordan Lee + counsel | ⬜ | No |
| C-7 | Minimum-necessary / data-minimization | Venky | ⬜ | No |
| C-8 | Safeguards (admin/technical/physical) | Jordan Lee | 🟨 (SOC-02 matrix in progress) | No |
| C-9 | Sub-processor change notice | Venky | ⬜ | No |
| EX-A | Exhibit A — sub-processor list | Jordan Lee | ⬜ | No |
| EX-B | Exhibit B — data-flow diagram (STORY-BAA-01) | Jordan Lee | 🟨 (drafted; Privacy Office approval pending) | **Yes** |
| EX-C | Exhibit C — safeguards / SOC-02 matrix | Jordan Lee | 🟨 (drafted) | No |
| EX-D | Exhibit D — permitted-use statement | Venky | ⬜ | No |
| **SIGN** | **BAA execution (AC-4)** | **SummitCare counsel + SARO** | ⬜ **INCOMPLETE** | **HARD GATE — no PHI until ✅** |

---

## 5. Execution — **[HUMAN] HARD GATE (AC-4)**

> **No PHI flows until this AC is complete.** SummitCare counsel + SARO execute the BAA.
> Claude Code cannot execute or sign anything. This block stays visibly INCOMPLETE until a human
> records the signature.

| Field | Value |
|---|---|
| **BAA executed** | ⬜ **NO — HARD GATE OPEN** |
| **Signed by (SARO)** | _____________________ |
| **Signed by (SummitCare)** | _____________________ |
| **Execution date** | _____________________ |
| **Effective PHI-flow start date** | _____________________ (must be ≥ execution date) |
| **Governing topology at signature** | ⬜ Pilot / PrivateLink (Variant A) · ⬜ Production / BYOC (Variant B) |

---

## 6. Definition of done (tests)

- [x] **Checklist complete** — C-1…C-9 framed as items for counsel, with engineering draft notes (§2).
- [x] **Tracker shows every item's owner/status** — §4, including exhibits and the signature row.
- [ ] **Execution AC gated and visibly incomplete until signed** — §5 present and set to
      ⬜ **HARD GATE OPEN**; flips only when a human records the signature.

## CHANGES MADE
- Wrote the AI-processing BAA component checklist (sub-processors, breach notice, permitted uses,
  de-identification, return/destruction, audit rights, minimum-necessary, safeguards, change notice),
  each framed as an item for counsel with engineering context anchored to real SARO controls/docs.
- Added exhibit outlines (A–D) and the narrowed-scope note gated on residual-SLI evidence.
- Built the status tracker (component → owner → status → blocking) and the hard-gated execution block.

## THINGS I DIDN'T TOUCH
- Binding legal language — counsel owns it; nothing here is proposed contract text.
- The signature (human hard gate).
- `docs/sub-processors.md` — flagged as needing reconciliation to the PT-012 stack, but not edited
  here (out of Epic 15 scope; belongs to its own follow-on).

## POTENTIAL CONCERNS
- **`docs/sub-processors.md` is stale** — it lists Railway/Streamlit, superseded by Fly.io + React/Vite
  (`docs/ARCHITECTURE.md`). It must be reconciled before it becomes a BAA exhibit, or the BAA will
  name the wrong sub-processors. Flagged as a candidate follow-on story.
- **Narrowed scope is a negotiation, not a fact** — presenting SARO as "holds only de-identified data"
  would overclaim; the residual path is non-zero (see §3 and STORY-BAA-01 §1).
- **SOC 2 is not yet attested** — Exhibit C references the SOC-02 matrix (controls with evidence
  pointers), but the Type II *report* does not exist yet; do not represent it as attested in the BAA.
