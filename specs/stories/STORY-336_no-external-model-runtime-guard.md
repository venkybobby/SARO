# STORY-336 — No-external-model-at-runtime invariant guard

**Epic:** GRC-9 — Architectural Invariants & Claims Integrity
**Priority:** P0 · **Status:** READY · **Depends on:** none

## Context
SARO's locked claim — "never calls external AI models at runtime" — must be enforced in code, not
trusted to reviewers. This is the durable fix for the class of error that DEC-4 represented: a guard
that fails CI the moment a product-path module reaches a third-party hosted model.

## Invariant (precise)
No code path in the **product/runtime path** may transmit client data to, or invoke, a **third-party
hosted model API**. Self-hosted models inside SARO infra are permitted. The **offline QA lab** module
(STORY-338) is explicitly exempt and must be isolated from the product path.

## Framework mapping
- NIST AI RMF: GOVERN (accountability for declared behavior).
- AIGP: accountability / claim integrity.

## Scope (in)
- A definitive allowlist/denylist of model-provider SDKs and API endpoints treated as "external."
- A static guard (import/dependency lint + call-site check) that fails if any product-path module
  references an external model SDK or endpoint.
- An explicit exemption for the offline QA lab package, asserted to be unreachable from product code.

## Out of scope
- Replacing legitimate self-hosted model usage. Network-layer egress policy (can be a fast-follow).

## Acceptance criteria (binary)
- [ ] A deliberately added external-model call in a product-path module fails the guard.
- [ ] A self-hosted model call passes the guard.
- [ ] The offline QA lab package is exempt and proven unreachable from the product path.
- [ ] The guard runs in CI and blocks merge on violation.

## Technical notes
- Implement as an architectural/import test plus a small registry of forbidden external model
  packages/endpoints. Wire into the existing quality-gates workflow.
- Pair with a runtime egress check as a later hardening step if desired.

## Test requirements
- [ ] Positive: clean product path passes.
- [ ] Negative: injected external-model import/call fails CI.

## Definition of done
Guard enforces the invariant in CI, exempts the offline lab, blocks violations; tests green.

## Traceability (implementation)
Decision (owner-approved): the guard is scoped to the GRC product path + FastAPI
surface + legacy `engine.py`; `engine.py`'s disclosed off-by-default Gate-3 judge
is the **only** allowlist entry (COMPLIANCE_CLAIMS_MATRIX §SARO-102) — allowlisted,
not removed. Self-hosted models pass. The offline QA-lab package (`qa_lab`,
STORY-338) must be unreachable from product code.

| AC | Test(s) | Files |
|---|---|---|
| Injected external-model call fails the guard | `test_injected_external_import_is_flagged`, `test_injected_from_import_is_flagged`, `test_modern_provider_on_ramps_flagged`, `test_dynamic_import_literal_flagged`, `test_bedrock_runtime_client_flagged`, `test_hosted_endpoint_string_is_flagged` | `grc/guards/external_model.py` |
| Self-hosted model call passes | `test_self_hosted_model_passes`, `test_unrelated_google_cloud_not_flagged` | `grc/guards/external_model.py` |
| Offline QA-lab exempt + proven unreachable | `test_lab_import_from_product_is_flagged`, `test_lab_subpackage_import_from_product_is_flagged` | `grc/guards/external_model.py` (`LAB_PACKAGE`) |
| Guard runs in CI and blocks merge on violation | `test_assert_raises_on_violation` + `python -m grc.guards.external_model` | `.github/workflows/quality-gates.yml` |
| engine.py disclosed judge allowlisted (not invisible) | `test_engine_judge_is_allowlisted_not_clean` | `grc/guards/external_model.py` (`DEFAULT_ALLOWLIST`) |
| Whole runtime path in scope (no blind spots) | `test_default_scope_includes_top_level_files_and_middleware`, `test_new_top_level_module_is_in_scope`, `test_guards_dirname_not_skipped_outside_grc` | `default_product_roots` |

Review: `reviewer` APPROVE; `security-auditor` PASS (HIGH-1 product-path scope,
HIGH-2 modern-provider denylist, MED-3 dir-skip all resolved). Static-only limits
(runtime-assembled names/URLs, transitive reaches) are documented and deferred to
the network-egress fast-follow.
