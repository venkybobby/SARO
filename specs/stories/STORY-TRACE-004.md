STORY-TRACE-004: Make the integrity banner honest (verify the real signature, or remove)
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P0 · Depends on: STORY-TRACE-001

Goal
The TRACE View renders a banner asserting "Hash chain integrity: verified — TRACE chain integrity verifiable via SHA-256 hash chain" based on `trace.hash_chain_valid`. That field is returned by neither endpoint, so today the banner either never renders or would assert a verification the client never performed. The real integrity signal is an HMAC `_signature` over the canonical export plus `export_hash` (`routers/trace_view.py:135`). On the screen whose entire purpose is tamper-evidence, asserting an unbacked "verified" is exactly the overclaiming ADR-004 forbids. Either compute/consume a real verification result and state precisely what was checked, or remove the claim.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency — integrity claims must be truthful and specific).
- NIST AI RMF: MEASURE/MANAGE (evidence integrity).
- ADR-004: anti-overclaiming lock applies directly.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the trace evidence, When integrity is shown, Then the UI derives its verdict from a real backend-provided verification result (e.g. signature-valid boolean computed server-side over the canonical export), not from an absent `hash_chain_valid`.
AC-2: Given a valid signature, When the banner renders, Then it states specifically what was verified (e.g. "HMAC signature valid over canonical export; export hash {short}") — no generic unscoped "hash chain verified" wording.
AC-3: Given an invalid or unavailable verification, When the banner renders, Then it shows "integrity not verified" / "verification unavailable" — never a green "verified".
AC-4: Given the chosen verification cannot be performed for this audit, When the screen renders, Then the integrity element is hidden or shows "unavailable", and no positive integrity claim is made.

Edge Cases
- Older audits lacking an `EnhancedTrace`/`export_hash` → "verification unavailable", not failure or success.
- Signature present but mismatching the recomputed canonical form → explicit "BROKEN/invalid" state.

Out of Scope
- Implementing a new cryptographic chaining scheme beyond the existing HMAC/export-hash mechanism.
- Export actions (STORY-TRACE-006).

Non-Functional Requirements
- Wording passes `/saro:compliance-check` scope-lock validation.
- The positive ("verified") state is reachable only when a real verification returned true — asserted by test.

Test Requirements
- Frontend unit (`TraceView.test.jsx`): valid → specific verified wording; invalid → BROKEN; unavailable → neutral; absent verification → no positive claim.
- Backend/contract: verification result field is present and correctly computed for a signed export fixture.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
