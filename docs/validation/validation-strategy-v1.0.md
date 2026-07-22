# SARO Validation Strategy v1.0 — The Completion Bar

**Story:** STORY-377 · **Owner:** Venky · **Status:** **PROPOSED — awaiting
owner sign-off (§6).** No threshold in this document is active until signed.

> **Numbering correction.** Earlier planning referred to a "validation strategy
> v1.1/v1.2". No such document ever existed in this repository (see the premise
> table in `specs/stories/STORY-PACK-14-19-INDEX.md`). This is **v1.0** — the
> first version. Recorded so a future plan does not re-assume a predecessor.

> **This is a proposal, not a decision.** The thresholds below are a **product
> decision** that the pack's own acceptance criterion (AC-3) reserves for the
> owner. They are presented with rationale and tradeoffs so that decision can be
> made — not so it can be skipped. Until §6 is signed, the confusion-matrix
> harness (STORY-378) and the rule-pack validation stage (STORY-376) treat the
> bar as `bar_pending` and enforce nothing.

---

## 1. What "validated" will mean

"What are your false-positive and false-negative rates?" is the first
technical-buyer question. Today the honest answer is "we have the machinery to
measure it but no agreed bar." This document defines the bar so that
*validated* becomes **a number with a method**, not an adjective.

Scope: the two genesis observation rule-packs, `RP-OBS-COMPLETE@1.0.0` and
`RP-TOOL-SCOPE@1.0.0`. Other packs adopt this framework as they reach validation.

A note on what these packs are: they are **deterministic envelope rules**, not
ML classifiers. On clean synthetic data a correct rule is essentially exact, so
a low score on a synthetic tier is a *rule bug*, not model variance. The
interesting error rates emerge on adversarial and real-world-labeled data —
which is why the tiers matter.

---

## 2. Ground-truth tiers

Four tiers, weakest-to-strongest evidence of real-world behaviour:

| Tier | Source | What it proves | Status today |
|---|---|---|---|
| **T1 — synthetic-deterministic** | `tests/fixtures/{azure,vertex}/corpus.ndjson` — planted, labeled by construction | The rules fire correctly on known-good/known-bad inputs | ✅ available |
| **T2 — synthetic-adversarial** | Edge cases: malformed records, boundary values, ambiguous fields | The rules degrade gracefully, not catastrophically | ◐ partial (corpora include some; a dedicated adversarial set is follow-on) |
| **T3 — offline labeled** | `qa_lab` human-adjudicated labels on redacted real fragments (STORY-338) | Behaviour on real data shapes | ◐ harness exists; a labeled set must be built |
| **T4 — pilot-labeled** | SummitCare pilot data, labeled with the partner | Behaviour on the actual deployment | ❌ not available until the pilot runs |

**A threshold may only be set for a tier that has data.** Proposing a T4 number
before pilot data exists would be exactly the fabricate-a-metric failure this
whole document is written to avoid.

---

## 3. The tradeoff the owner must decide

Precision and recall trade against each other, and for a compliance-evidence
tool the balance is **not obvious** — which is precisely why it is not mine to set.

- A **false positive** (SARO flags an observation gap that is not real) wastes a
  compliance reviewer's time and, repeated, erodes trust in the tool.
- A **false negative** (SARO misses a real gap) means SARO's evidence *claims
  coverage it does not have* — and for a tool sold on audit evidence, silently
  under-reporting is arguably the worse failure.

That argument leans toward **weighting recall over precision**. But it is a
judgement about how the product is positioned and how a design partner will
react to noise, so §4 offers two profiles rather than embedding one.

---

## 4. Proposed thresholds — TWO profiles, pick one

Both are **proposals**. Numbers are expressed as precision/recall floors per
pack per available tier.

### Profile A — Recall-weighted (proposed default)
Prioritises catching real gaps; tolerates more false positives.

| Pack | Tier | Precision ≥ | Recall ≥ | Rationale |
|---|---|---|---|---|
| RP-OBS-COMPLETE | T1 | 0.99 | 0.99 | deterministic on clean data — anything lower is a rule bug |
| RP-OBS-COMPLETE | T2 | 0.90 | 0.95 | tolerate FP on adversarial input; do not miss real gaps |
| RP-OBS-COMPLETE | T3 | 0.85 | 0.90 | real fragments are messier; recall floor stays high |
| RP-TOOL-SCOPE | T1 | 0.99 | 0.99 | tool-name matching is exact on clean data |
| RP-TOOL-SCOPE | T2 | 0.90 | 0.95 | ambiguous/enriched exports |
| RP-TOOL-SCOPE | T3 | 0.85 | 0.90 | |

### Profile B — Balanced
Treats FP and FN symmetrically; a quieter tool at the cost of some missed gaps.

| Pack | Tier | Precision ≥ | Recall ≥ |
|---|---|---|---|
| RP-OBS-COMPLETE | T1 | 0.99 | 0.99 |
| RP-OBS-COMPLETE | T2 | 0.93 | 0.93 |
| RP-OBS-COMPLETE | T3 | 0.88 | 0.88 |
| RP-TOOL-SCOPE | T1 | 0.99 | 0.99 |
| RP-TOOL-SCOPE | T2 | 0.93 | 0.93 |
| RP-TOOL-SCOPE | T3 | 0.88 | 0.88 |

T4 (pilot) thresholds are **deliberately left blank** in both profiles — set them
with the design partner once pilot-labeled data exists.

The machine-readable form of both profiles is
`quality/validation/completion-bar.proposed.yaml`, marked
`status: PROPOSED_AWAITING_SIGNOFF`.

---

## 5. Measurement protocol

- **Corpus composition per measurement:** all of T1 and T2; T3 as it is built.
  T4 joins once available. A run states which tiers it covered — a score without
  its tier coverage is not interpretable.
- **Tier weighting:** the overall verdict is **per-tier, not a blended average.**
  A pack must meet the floor for *every tier it is measured against*; a strong T1
  must not paper over a weak T3. (Averaging across tiers is how a good synthetic
  score hides poor real-world behaviour.)
- **Exclusion rules:** records the adapter marks structurally `UNAVAILABLE` for a
  rule's input are excluded from that rule's denominator — you cannot score a
  rule on data the provider cannot emit (see the adapter capability matrix).
  Exclusions are counted and reported, never silent.
- **Re-measurement cadence:** on every rule-pack version publish, and weekly on
  a schedule (drift from corpus growth).
- **Re-validation triggers:** a pack version bump, a new adapter (its corpus
  joins the relevant tiers), or a threshold change here.

---

## 6. Sign-off — [HUMAN — OPEN]

**No threshold in this document is active until an owner signs below.** Until
then STORY-378's harness runs in report-only mode and STORY-376's validation
stage reports `bar_pending:STORY-377`.

- [ ] **Profile chosen:** ☐ A (recall-weighted) ☐ B (balanced) ☐ modified (attach)
- [ ] **FP/FN tradeoff (§3) accepted or amended:** _______________________
- [ ] **Signed:** ______________________  **Date:** __________
- [ ] On sign-off: set `status: SIGNED` and record the chosen profile in
      `quality/validation/completion-bar.proposed.yaml`, then rename it to
      `completion-bar.yaml`.

Do not self-certify. A validation bar SARO set for itself, unsigned, is exactly
the kind of unearned claim the compliance-claims discipline exists to prevent.
