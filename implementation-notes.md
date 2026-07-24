# STORY-TAB-008 — Tab consolidation (fold 5 tabs into their hosts)

Stage: standard

## Lifecycle
- [x] discover   (skipped — all five surfaces + hosts audited across TAB-001..007 this session; premise table in specs/stories/STORY-TAB-008.md)
- [x] shape      (sign-off = owner invoking /story STORY-TAB-008; remaining decisions defaulted + logged below)
- [x] preview    (skipped — no new visual design: hosts embed the existing components unchanged, STORY-112 precedent)
- [x] plan       (host-by-host plan in task list; spec finalized to ready with G/W/T ACs + edge cases)
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## Premise check (Stage 3a)

See the Premise verification table in specs/stories/STORY-TAB-008.md — every
referenced artifact cites a file path; the one load-bearing discovery is that
`PATCH /remediation/traces/{id}/remediate` lacks `require_write_access`
(routers/remediation.py:168; helper exists at auth.py:238) — hardened here as
FND-085 because the consolidation embeds the queue on a demo-visible page.

## Decision Log

(format: question → defaulted answer → architectural consequence)

| Question | Answer | Architectural consequence |
|---|---|---|
| Rewrite relocated features into hosts, or embed the components? | Embed unchanged (STORY-112 precedent) with an `embedded` prop that suppresses the page chrome (h1/padding). | Every TAB-001..007 FND pin on those components stays valid; hosts gain a section, not logic. |
| ai_auditor loses coverage_gap — grant them compliance_hub? | No. Compliance Hub aggregates compliance-persona endpoints (readiness, EVF calendar) not all verified for ai_auditor — adding it risks the FND-077 visible-but-403 class. Coverage rollup is compliance-lead material; auditor keeps TRACE/Rule Packs/drift/remediation. | Deliberate persona-surface narrowing, logged in spec Edge Cases. |
| Trust Center detection-quality card: /latest is super_admin/operator-only | Use the LIST endpoint (`?status=completed&limit=1`) which admits admin too (TAB-004), and render the card only when `user.role ∈ {admin, operator, super_admin}` — others get no card, no fetch, no 403. | No authz widening; no dead card. |
| Demo session sees TRACE View + Compliance Hub (DEMO_TABS) — do embeds change the demo surface? | Remediation embed hidden entirely for `role=demo_viewer` (defense in depth on top of the new backend write gate); coverage embed is fine (endpoint already demo-census-safe via ComplianceHub). | STORY-412 census unchanged. |
| remediate PATCH write gate | Add `Depends(require_write_access)` (FND-085, red-first pin). UI additionally hides Mark Complete for `read_only` users (FND-054 pattern). | routers/ touched → security-auditor required. |
| Onboarding banner vs existing first-login wizard | Both stay: wizard = first-login modal (TAB-002); banner = persistent Dashboard card until complete/dismissed, embedding the same API-driven component. Separate localStorage keys. | One data contract, two presentations; no duplicated step logic. |
| Removed page keys in AppShell | Drop from PAGE_COMPONENTS + Sidebar registry/personas; component files stay (they are the embedded implementations). Stale keys fall back to Dashboard (existing behavior). | No dead nav entries; no deleted pins. |

## Build progress
- folds 1-2 committed (59b9a85); fold 3 (remediation → TRACE View + FND-085
  write gate) in progress.

## Deviations
None yet.
