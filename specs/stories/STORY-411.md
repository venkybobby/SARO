# STORY-411 — Model-Allowlist Envelope Rule (fires UC-5)

**Status:** done — see Traceability + Decision Log below (implementation-notes.md has the full Decision Log/Deviations)
**Status (original):** Ready for build — **DEMO-CRITICAL, build second**
**Depends on:** STORY-405 (eval core), STORY-407 (corpus with UC-5 planted); rule-pack temporal-integrity story (versioning conventions)
**Delivery rule:** Integrated into the single SARO repo.

## Problem Statement

UC-5 (off-allowlist `modelId`) is planted in the demo corpus but fires nothing: the content engine (Gate 3) evaluates prompt+output text only and never inspects the envelope. "An unapproved model served production traffic" is one of the most visceral governance findings for a healthcare risk officer, and today SARO is structurally blind to it. This story adds the minimal envelope-attribute evaluation capability plus one rule: model allowlist.

## Goals

1. The engine can evaluate envelope-level attributes (starting with `modelId`) against versioned rule-pack rules, deterministically, with no model calls.
2. UC-5 fires in the demo corpus; E2E asserts 4 findings (UC-1, UC-2, UC-5, UC-6).
3. The finding's language survives ADR-004 review.

## Non-Goals

- No general-purpose envelope rule DSL — one rule type (`envelope_allowlist` on `modelId`) with room to extend. Resist generalizing (P2 parking lot: identity.arn patterns, region pinning, token-count anomalies).
- No UC-3 (disclaimer) or UC-4 (injection) rules — separately tracked Wave-2, owner decision stands.
- No UI for editing allowlists — configuration only.

## Functional Requirements

### FR-1: Envelope evaluation stage (P0)
A pre-content evaluation step that receives the envelope (metadata only, consistent with INV-2 discipline) and applies envelope-type rules from the active rule pack.

**AC-1.1:** Given a record whose `modelId` is not on the tenant's configured allowlist, when evaluated, then exactly one finding is emitted with category consistent with the existing risk taxonomy (owner to confirm category mapping — likely AI System Safety or a governance category; ask, don't assume).
**AC-1.2:** Given a record whose `modelId` is on the allowlist, no envelope finding is emitted and content evaluation proceeds unchanged.
**AC-1.3:** Envelope evaluation is deterministic and stateless, consistent with the STORY-405 core contract; same input + same rule-pack version = same finding, byte-stable.

### FR-2: Allowlist rule definition (P0)
Allowlist lives in the versioned rule pack (not in ad-hoc config), so findings are attributable to a rule-pack version like every other finding.

**AC-2.1:** Rule pack schema gains an `envelope_allowlist` rule type: list of exact `modelId` strings plus optional prefix entries (e.g., `anthropic.claude-*` style prefix match — exact-then-prefix, no regex).
**AC-2.2:** The finding records: the observed `modelId`, the rule id, the rule-pack version, and the record's `requestId` — sufficient for TRACE View drill-down parity with content findings.
**AC-2.3:** Rule-pack temporal integrity semantics apply: re-evaluating a historical window with the rule-pack version active at that time reproduces the same findings.

### FR-3: ADR-004 finding language (P0)
**AC-3.1:** Finding title/description claims only what is observable: "Model not on approved allowlist for this tenant" — NOT "unauthorized access," "security breach," or intent language. Copy reviewed against ADR-004 anti-overclaiming rules.

### FR-4: Demo corpus integration (P0)
**AC-4.1:** Demo rule pack for the demo tenant includes the allowlist rule with the manifest's approved `modelId`s; UC-5's planted record uses an off-list id.
**AC-4.2:** STORY-407 E2E updated: exactly UC-1, UC-2, UC-5, UC-6 fire; clean traffic still fires zero (clean traffic's modelIds must all be on the allowlist — update manifest/fixtures accordingly).
**AC-4.3:** STORY-407 debrief's UC table and the demo runbook's "fires today" notes updated to reflect 4 firing use cases.

## Verification (all-or-nothing)
- [ ] Determinism + temporal-integrity tests for the new rule type
- [ ] E2E asserts exactly 4 findings, zero clean-traffic findings
- [ ] TRACE View manually verified to render the envelope finding with requestId drill-down (screens, not just engine output)
- [ ] STORY-336 guard green; INV-2 untouched (envelope stage sees no bodies beyond what the engine contract already permits)
- [ ] Full existing suite passes

## Open Questions (blocking) — resolved
1. Risk-category mapping: **new "Governance & Compliance" MIT_DOMAINS entry** — owner chose this over the recommended reuse of "AI System Safety", accepting the added surface (a new taxonomy category, fed exclusively by envelope evaluation, never content-scan keywords).
2. Allowlist location: **in the versioned rule pack itself, global** — matches FR-2's own design directive; rule packs are global (not per-tenant) throughout this repo, and this story didn't invent per-tenant config. New dedicated `rule_packs/envelope_loader.py` + `rule_packs/envelope/1.0.0/envelope_allowlist.yaml` (the existing `rule_packs/loader.py` is a compliance-citation mapper with no field for a model-ID list).

## Traceability (AC → test → file)

| AC | Test | File |
|---|---|---|
| AC-1.1 | `test_off_allowlist_model_fires_exactly_one_governance_finding` | `tests/test_engine_envelope_allowlist.py` |
| AC-1.2 | `test_on_allowlist_model_fires_no_envelope_finding` | `tests/test_engine_envelope_allowlist.py` |
| AC-1.3 | `test_deterministic_same_input_same_finding` | `tests/test_engine_envelope_allowlist.py` |
| AC-2.1 | `test_exact_match_allowed`, `test_off_allowlist_model_is_not_allowed`, `test_prefix_match_checked_only_when_no_exact_match`, `test_empty_or_none_model_id_is_not_allowed` | `tests/test_envelope_loader.py` |
| AC-2.2 | `test_finding_records_model_id_rule_id_version_and_request_id` | `tests/test_engine_envelope_allowlist.py` |
| AC-2.3 | `test_hash_is_deterministic_and_changes_with_content` (no time-travel mechanism exists repo-wide; deterministic-by-construction, see Decision Log Q re: temporal integrity) | `tests/test_envelope_loader.py` |
| AC-3.1 | `test_finding_language_is_observable_only_adr_004` | `tests/test_engine_envelope_allowlist.py` |
| AC-4.1 | `rule_packs/envelope/1.0.0/envelope_allowlist.yaml` (allowlist sourced from `scripts/demo_manifest.yaml`) | — |
| AC-4.2 | `test_e2e_exactly_covered_findings_fire_and_gap_is_attested` (updated: 4 UCs) | `tests/test_story407_demo_corpus_builder.py` |
| AC-4.3 | STORY-407.md UC table updated | `specs/stories/STORY-407.md` |
| Backward compat | `test_no_metadata_is_a_no_op_backward_compat` | `tests/test_engine_envelope_allowlist.py` |
| security-auditor LOW | `test_oversized_model_id_and_request_id_are_truncated_before_storage` | `tests/test_engine_envelope_allowlist.py` |
| FND-050 (review-found) | `test_submit_audit_sync_forwards_metadata_to_run_output_audit` | `tests/regression/test_fnd_050_submit_audit_sync_forwards_metadata.py` |
