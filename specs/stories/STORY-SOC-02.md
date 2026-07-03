# STORY-SOC-02: Control-to-evidence matrix (TSC → SARO controls → gaps)

**Status:** in-progress (artifact done; **[HUMAN] security-owner validation OPEN**)
**Screen/Area:** Epic 15 — Trust & Compliance Enablement / SOC 2 Type II workstream
**Artifact:** `compliance/soc2/STORY-SOC-02_control-evidence-matrix.md`
**Depends on:** STORY-SOC-01 (scope defines which criteria to map)

## Goal
The honest inventory: which controls SARO actually has (with pointers) and which are missing (with
owners) — no control claimed without a pointer to where it lives.

## Acceptance Criteria
- **AC-1 [CC] ✅** Per in-scope criterion (Security CC, Confidentiality C, Availability A): required
  controls mapped to **actual** SARO controls with in-repo pointers.
- **AC-2 [CC] ✅** Gap list: required-but-absent controls (G-SOC-01…14), each with severity + owner,
  surfaced as candidate follow-on stories.
- **AC-3 [CC] ✅** Evidence source per control (code/tests, CI runs, config, audit log, policies, metrics).
- **AC-4 [HUMAN] ⬜** Security owner validates the matrix and prioritizes gap remediation.

## Out of Scope
- Building missing controls (each gap is its own follow-on).

## Non-Functional Requirements
- Anti-overclaim: corrects the readiness-roadmap's optimistic "Implemented" states where in-repo
  evidence disagrees (MFA optional, Sentry not wired, no deprovision API, Railway references).

## Definition of Done
- [x] Every in-scope criterion mapped. [x] No unbacked claim. [x] Gaps with owners. [x] Evidence source per control.
- [ ] Security owner validates — OPEN.

## Traceability
| AC | Evidence | Files |
|---|---|---|
| AC-1/3 | CC/C/A control tables with pointers | `compliance/soc2/STORY-SOC-02_control-evidence-matrix.md` §2–4,6 |
| AC-2 | gap list G-SOC-01…14 | same, §5 |
| AC-4 | validation block (human-set) | same, §7 |
