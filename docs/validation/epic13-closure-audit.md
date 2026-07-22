# Epic 13 Closure Audit

**Story:** STORY-380 · **Owner:** Venky · **Date:** 2026-07-21

---

## The correction this audit records

The Epics 14–19 story pack assumed **"Epic 13 = STORY-340..357"** — a set of
validation stories to be triaged and closed. **No such stories exist in this
repository, and never did.** `specs/stories/` goes from STORY-338 straight to
STORY-400; there is no STORY-340..357, no "validation strategy v1.1", no "20k
Evidence Corpus Factory", and no 4-tier labeled corpus predating this pack.
(Full premise verification: `specs/stories/STORY-PACK-14-19-INDEX.md`.)

So this is not a triage of phantom stories. It is an honest audit of the
validation-adjacent work that **does** exist, plus the record that Epic 13 as
described was a planning artifact carried forward as fact — the same
claimed-without-evidence pattern the pack's own controls (CLAUDE.md FM-1/FM-2)
now guard against.

---

## What actually exists (the real validation machinery)

Each item is `Done` with a code+test evidence pointer, `Superseded` (by a
Pack-Epic-18 story), or `Deliberately dropped` with a reason.

| Item | Verdict | Evidence |
|---|---|---|
| **STORY-335** — runtime groundedness (non-LLM) | **Done** | `grc/checks/groundedness.py`; `tests/test_story335_groundedness.py` |
| **STORY-336** — no-external-model runtime guard (INV-1) | **Done** | `grc/guards/external_model.py`; `tests/test_story336_external_model_guard.py`. Extended by this pack (endpoint-literal exemption, STORY-360). |
| **STORY-337** — claims-consistency guard | **Done** | `grc/guards/claims_registry.py`; `tests/test_story337_claims_registry.py` |
| **STORY-338** — offline LLM-judge labeling harness (qa_lab) | **Done** | `qa_lab/labeling.py`; `tests/test_story338_offline_labeling.py`. This is the **T3 tier** source for the completion bar. |

These four are the validation foundation the pack's Epic 18 built on — not a
missing Epic 13.

---

## What Pack-Epic-18 added (the completion bar the pack actually asked for)

The pack's Epic 18 (STORY-377..380) is where "validated" becomes a number with a
method. It **creates** the bar rather than completing prior work, precisely
because the prior work assumed did not exist.

| Item | Verdict | Evidence |
|---|---|---|
| **STORY-377** — completion bar (FP/FN targets) | **Done — SIGNED 2026-07-21, Profile A** | `docs/validation/validation-strategy-v1.0.md` §6; `quality/validation/completion-bar.yaml` (`status: SIGNED`); `services/validation_bar.py` |
| **STORY-378** — confusion-matrix harness | **Done — enforcing (Profile A) on measured tiers** | `scripts/confusion_matrix_harness.py`; `quality/validation/confusion-latest.json` + `trend.jsonl`. Surfaced and fixed **FND-068** on its first run; now passes T1 at 1.0/1.0. |
| **STORY-379** — buyer-facing validation report | **Done** | `scripts/generate_validation_report.py` → `docs/validation/validation-report.{md,pdf}` |
| **STORY-380** — this closure audit | **Done** | this document |

---

## Numbering correction (so no future plan re-assumes it)

- There is **no Epic 13** in this repository. The validation machinery lives in
  STORY-335..338 and Pack-Epic-18 (377..380).
- The validation strategy is **v1.0** (this pack), not v1.1/v1.2. Those version
  numbers referred to documents that never existed here.
- Recorded also in `docs/validation/validation-strategy-v1.0.md` and the pack
  index's premise-verification table.

---

## Open items — the validation track is not "complete", and says so

- **The completion bar is signed (Profile A, 2026-07-21), but coverage is
  tier-limited.** Only tier **T1** is measured. T2 (adversarial), T3
  (offline-labeled, via the STORY-338 harness), and T4 (pilot) are defined but
  not yet populated — see the validation report's Limitations section. A T1 pass
  is not full validation.
- **T4 stays blank by condition of the sign-off** — pilot thresholds are set
  jointly with SummitCare once pilot-labeled data exists, and must not be
  backfilled. The **profile choice itself is revisited at T4**.
- **Thresholds are provisional** until validated against real (T3/T4) data.

The human gate that blocked the track — the STORY-377 sign-off — is **now
closed** (Profile A, with a per-pack precision floor and the T4/revisit
conditions). What remains open is data coverage, not a decision.

## Verdict

Epic 13 as described did not exist; the validation foundation (335..338) and the
completion bar (377..380) do, with the evidence linked above. This audit is the
closure — an honest one, with the numbering corrected and the remaining coverage
gaps named, rather than a claim of a completeness the track has not yet reached.
