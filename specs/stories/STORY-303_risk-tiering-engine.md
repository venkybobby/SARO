# STORY-303 — Risk tiering engine

**Epic:** GRC-1 — AI Asset Registry & Risk Tiering
**Priority:** P0 · **Status:** READY · **Depends on:** STORY-301, STORY-331

## Context
Governance effort must scale with risk. Each system is classified into an internal tier, an
EU AI Act category, and a NIST impact level, which drives which controls, gates, and checks apply.

## Framework mapping
- EU AI Act: risk categories (unacceptable / high / limited / minimal).
- NIST AI RMF: MAP (categorization).
- ISO/IEC 42001: risk-based context.

## Scope (in)
- A config-driven classifier producing `{internal_tier, eu_ai_act_category, nist_impact_level}` for a registry entry.
- Re-tiering on metadata change, recorded with rationale + timestamp.

## Out of scope
- Tier-driven routing of control sets (STORY-304, Phase 2). The config schema itself (STORY-331).

## Acceptance criteria (binary)
- [ ] Classifier returns all three fields for any complete registry entry.
- [ ] Thresholds/rules come from config — no hard-coded tier boundaries.
- [ ] A metadata change that alters inputs re-tiers the system and logs the rationale.
- [ ] Sample systems classify to expected tiers in tests (e.g., healthcare triage agent → HIGH).

## Technical notes
- Keep the rule engine boring and inspectable (declarative rule set evaluated in order); avoid an opaque scoring black box an auditor cannot follow.
- `internal_tier` ∈ {LOW, MODERATE, HIGH, CRITICAL} to match the risk-band enum.

## Test requirements
- [ ] Unit: a fixture table of system profiles → expected `{tier, eu_category, nist_level}`.
- [ ] Unit: re-tiering fires on a relevant metadata change and records rationale.

## Definition of done
Known profiles classify correctly; rules are config-driven; re-tiering logged; tests green.
