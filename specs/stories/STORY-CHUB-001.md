STORY-CHUB-001: EVF Validation Status card — wire to real tier data, fix name key, enforce tier-with-coverage invariant
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P0 · Depends on: —

Goal
The Compliance Hub "EVF Validation Status" card reads `fw.name` and `fw.evf_tier`/`fw.evf_label`/`fw.evf_qco_reference` from `/api/v1/compliance-matrix/coverage`, but that endpoint returns the framework under key `framework` (not `name`) and returns no EVF fields at all. Result: blank framework labels and no tier badges — coverage percentages render as if validated. Per ADR-004 this is the exact overclaiming risk the EVF tier exists to prevent. Rewire the card to source tier data from `/api/v1/evf/validation-status` and make it structurally impossible to show a coverage % without its validation tier.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency — accurate representation of validation state to the user).
- ISO/IEC 42001: document-lifecycle linking only (tier/QCO provenance display).
- AIGP: principles evaluation only — the tier badge must label internal-only assessments as such, never as audit evidence.
- ADR-004 enforcement: directly implements the anti-overclaiming lock.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the EVF Validation Status card in `frontend/src/pages/ComplianceHub.jsx`, When `coverage.frameworks` renders, Then each card's framework label reads `fw.framework` (not `fw.name`) and is never blank.
AC-2: Given the card needs tier data, When the page loads, Then it fetches `/api/v1/evf/validation-status` and maps each framework's `tier`/`label`/`qco_reference`/`qco_expiry_date` onto the matching coverage row, using a single normalization helper that reconciles `/coverage` `framework` display strings with `/validation-status` enum values (e.g. "EU AI Act" ↔ "EU_AI_ACT").
AC-3: Given a framework has a coverage % but no resolved tier, When it renders, Then it displays the Tier 3 / "INTERNAL ONLY" badge by default — a coverage % is never shown without a tier badge in the same card.
AC-4: Given `/api/v1/evf/validation-status` returns 403/empty/error, When the card renders, Then all frameworks fall back to Tier 3 with a visible "validation status unavailable — treated as internal only" note, and no card implies external validation.
AC-5: Given the existing `TierBadge` component, When tier is `tier_1`/`tier_2`/`tier_3`, Then the badge text, color, and QCO reference render exactly as the Compliance Calendar already renders them (single shared `TIER_CONFIG`).

Edge Cases
- Framework-name normalization mismatch between `/coverage` (regulation_name display string) and `/validation-status` (enum value) must not silently drop a row — unmatched rows default to Tier 3, never disappear.
- A framework present in `/validation-status` but absent from `/coverage` must still surface (no coverage bar, tier badge only) rather than vanish.
- Tier 1 with an expired QCO must NOT render as green/validated — expiry overrides tier to a warning state.

Out of Scope
- Editing EVF tier or QCO records (read-only display here).
- Changing the `/coverage` response shape to embed EVF fields (kept as a separate normalization concern; this story joins client-side).
- Calendar section (already correct).

Non-Functional Requirements
- No coverage-%-without-tier state is reachable in any code path (enforce via a single render function, asserted by test).
- Two fetches resolve independently; tier fetch failure degrades to Tier 3, it does not blank the coverage card.

Test Requirements
- Unit (frontend, `frontend/src/pages/ComplianceHub.test.jsx`): renders `framework` label from `fw.framework`; missing tier → Tier 3 badge present; expired Tier 1 → warning not green.
- Unit: normalization helper maps "EU AI Act"↔"EU_AI_ACT", "NIST AI RMF"↔"NIST_AI_RMF", etc., both directions.
- Integration: `/validation-status` 403 → all-Tier-3 fallback with unavailable note; no "validated" wording present in DOM.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	ComplianceHub.test.jsx "AC-1: framework label reads fw.framework"	frontend/src/pages/ComplianceHub.jsx (buildEvfRows + EVF card render)
AC-2	"AC-2: canonicalFramework normalizes..." + "buildEvfRows: every coverage row carries a tier"	frontend/src/pages/ComplianceHub.jsx (canonicalFramework, buildEvfRows; /evf/validation-status fetch)
AC-3	"AC-3: ...no resolved tier shows Tier 3 INTERNAL ONLY"	frontend/src/pages/ComplianceHub.jsx (makeEvfRow default tier_3)
AC-4	"AC-4: validation-status 403 → all Tier 3 + unavailable note"	frontend/src/pages/ComplianceHub.jsx (tierUnavailable fallback + note)
AC-5	"AC-5: tier_1 status renders EXTERNALLY REVIEWED badge with QCO ref"	frontend/src/pages/ComplianceHub.jsx (shared TIER_CONFIG / TierBadge)
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
