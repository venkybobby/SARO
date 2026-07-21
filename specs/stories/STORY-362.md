# STORY-362: Adapter Capability Matrix (Buyer-Facing)

**Status:** ready
**Screen/Area:** Docs (Pack Epic 14)
**Depends on:** STORY-359/360 field-mapping tables

## Goal
A one-page capability matrix (fields, rule-packs, trigger modes per adapter) a
technical buyer can use during evaluation.

## Acceptance Criteria
- AC-1: `docs/adapter-capability-matrix.md` covers Bedrock, Azure OpenAI,
  Vertex; generated or hand-authored **with a CI freshness check** against the
  field-mapping tables in docs/adapter-design.md.
- AC-2: Explicitly lists non-supported fields/modes (e.g., Azure streaming
  rows, live polling) — no aspirational rows.
- AC-3: Linked from README and the Compliance Hub docs area.

## Non-Functional Requirements
- Language guardrails per docs/compliance-claims.md (no "certified", no client results).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_matrix_file_is_current`, `test_covers_all_three_adapters`, CI `--check` | `scripts/generate_capability_matrix.py` → `docs/adapter-capability-matrix.md`; `.github/workflows/conformance.yml` |
| AC-2 | `test_unsupported_fields_are_marked_not_omitted`, `test_limitations_section_is_populated`, `test_live_interception_is_explicitly_not_offered`, `test_provider_caveats_reach_the_document` | generated Limitations section |
| AC-3 | `test_linked_from_compliance_hub_and_adapter_design` | `compliance/README.md`, `docs/adapter-design.md` |
| NFR (language) | `test_generated_document_contains_no_prohibited_claim_language`, `test_language_check_would_catch_each_prohibited_phrase` (parametrized over all prohibited phrases) | generator refuses to write prohibited claim language |

## Deviation — AC-3 "linked from README"
**No root `README.md` exists in this repo** (premise check, PLAN 3a). Rather
than create one as a side effect of this story, the matrix is linked from the
two real entry points: `compliance/README.md` (Compliance Hub docs area) and
`docs/adapter-design.md`. A test asserts no root README has appeared — if one
is added later, it fails and prompts the link. **Owner decision needed:** create
a root README?

## Design note — derived, not authored
Field rows read each adapter's `field_availability` after parsing that
provider's **stock** log shape (`standard_schema_record()`), so a buyer is never
shown a ✅ that depended on a non-default configuration. Availability — not the
sample value — is the authority: `error_code` is `None` on a successful record,
and reading that as "unsupported" would have understated every adapter's error
handling (caught during build). Configuration-dependent cases (Azure token
counts, Vertex endpoint model identity) are declared by the provider next to
the adapter and rendered as caveats.
