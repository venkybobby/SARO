# STORY-331 — Configurable policy layer

**Epic:** GRC-6 — Lifecycle Gates, Sign-off & Output Contract
**Priority:** P0 · **Status:** READY · **Depends on:** none

## Context
Policy must change without code changes. Tier rules, risk-band thresholds, gate aggregation rules,
and sign-off role mappings live in config and are read by the tiering, scoring, gate, and sign-off
stories.

## Framework mapping
- ISO/IEC 42001: policy.
- NIST AI RMF: GOVERN.

## Scope (in)
- A versioned config store covering: tiering rules (STORY-303), band thresholds (STORY-310), gate rules incl. the High-FAIL threshold N (STORY-326), and sign-off role→tier map (STORY-327).
- Config changes take effect without redeploying audit logic.

## Out of scope
- A config-editing UI. Per-tenant config (single-tenant assumption for MVP).

## Acceptance criteria (binary)
- [ ] Changing a band threshold in config changes a finding's band without a code change.
- [ ] Changing the High-FAIL threshold N changes the gate outcome accordingly.
- [ ] Config is versioned; the active version is recorded on each audit result for traceability.
- [ ] Invalid config (e.g., overlapping band ranges) is rejected at load.

## Technical notes
- Validate config on load (fail fast). Stamp the config version onto emitted results so an audit is reproducible against the policy that produced it.

## Test requirements
- [ ] Unit: threshold change alters band/gate output; invalid config rejected at load.

## Definition of done
Policy values are config-driven and versioned; changes take effect without redeploy; invalid config fails fast; tests green.
