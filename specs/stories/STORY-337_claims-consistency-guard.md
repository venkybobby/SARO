# STORY-337 — Claims-consistency guard (locked Compliance Claims Matrix)

**Epic:** GRC-9 — Architectural Invariants & Claims Integrity
**Priority:** P1 (highest-leverage preventative) · **Status:** READY · **Depends on:** STORY-336

## Context
DEC-4 contradicted a locked claim and a single-axis gap analysis could not catch it. This story is the
durable fix: make the Compliance Claims Matrix machine-checkable so any new story, PR, or doc that
introduces a capability contradicting a locked claim is flagged automatically — "prompts suggest, hooks
enforce, CI guarantees" applied to claims integrity.

## Framework mapping
- AIGP: accountability / truthful representation.
- NIST AI RMF: GOVERN.

## Scope (in)
- A structured registry of locked claims as checkable assertions, seeded from the Compliance Claims
  Matrix, including at least:
  - SARO never calls external AI models at runtime (enforced concretely by STORY-336).
  - SARO never certifies compliance.
  - SARO always requires human-in-the-loop review.
  - SARO never writes to client systems.
  - AIGP = principles evaluation only (never "framework" or "certification").
  - EU AI Act coverage = evidence support for Articles 9/13/17 only.
  - ISO 42001 support = lightweight document lifecycle linking only.
- A CI step + required PR checklist: each new story/PR is checked against the registry; a contradiction
  blocks merge or requires an explicit, logged claim-change decision.
- Targeted automated checks where a claim is mechanically verifiable (e.g., the external-model claim
  delegates to STORY-336; framing-language checks flag forbidden terms like "certification"/"framework"
  applied to AIGP).

## Out of scope
- Full NLP contradiction detection (out of reach; not attempted). Auto-resolving contradictions.

## Acceptance criteria (binary)
- [ ] The claims registry exists and is versioned.
- [ ] A PR introducing an external-model runtime call is blocked (via STORY-336).
- [ ] A doc/story describing AIGP as a "certification" or "framework" is flagged by the framing check.
- [ ] Changing a locked claim requires an explicit, logged decision — it cannot happen silently.

## Technical notes
- Keep it pragmatic: a registry + required checklist + a few mechanical checks beats an unachievable
  general contradiction detector. The mechanical checks grow over time.

## Test requirements
- [ ] Negative: an AIGP-as-"certification" string is flagged; an external-model call is blocked.
- [ ] Positive: a compliant story passes the guard.

## Definition of done
Locked claims are a versioned, CI-checked registry; mechanical violations are blocked; claim changes are logged; tests green.

## Traceability (implementation)
`grc/guards/claims_registry.py`: 7 locked claims (versioned, SHA-256 integrity
lock at `claims_registry.lock.json`). External-model claim delegates to STORY-336
(Path A wording — the disclosed off-by-default Gate-3 judge remains, so the
registry never contradicts the matrix). Framing check flags AIGP-as-framework /
AIGP-as-certification, excluding the matrix-approved "AIGP-certified human
reviewer" by span. CI gate + required PR checklist.

| AC | Test(s) / mechanism |
|---|---|
| Registry exists and is versioned | `test_registry_exists_and_is_versioned`, `REGISTRY_VERSION` + lock file |
| PR introducing an external-model runtime call is blocked (via 336) | `test_external_model_call_is_blocked`, `test_clean_product_path_satisfies_external_model_claim`; CI `python -m grc.guards.claims_registry` |
| AIGP-as-certification / -framework flagged | `test_framing_flags_aigp_certification_and_framework`, `test_certification_with_trailing_reviewer_noun_still_flagged`, `test_framing_resists_unicode_and_markdown_evasion`; approved phrase passes (`test_framing_allows_matrix_approved_aigp_language`) |
| Changing a locked claim cannot happen silently | `test_silent_claim_change_breaks_integrity`; digest mismatch fails CI until lock regenerated + logged in `docs/CLAIMS_AUDIT_LOG.md` |

Review: `reviewer` APPROVE; `security-auditor` PASS. Hardened per their findings —
F1 (trailing-noun lookahead false-negative → span-based approved-phrase exclusion),
F3 (unicode-dash/markdown evasion → NFKC + dash normalization), F4 (basename excludes
→ path-anchored). Documented limitations (pragmatic scope, "checks grow over time"):
the broad forbidden-phrase repo scan stays owned by `scripts/evf_retrospective_audit.py`;
frontend UI copy is covered by the frontend gate, not this one; bounded-gap rephrasings
(e.g. "AIGP compliance framework") and full NLP contradiction detection are out of scope.
