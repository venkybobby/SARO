# STORY-SOC-03: Evidence-collection wiring for the observation period

**Status:** in-progress (artifacts done; **[HUMAN] cadence confirmation OPEN**)
**Screen/Area:** Epic 15 — Trust & Compliance Enablement / SOC 2 Type II workstream
**Artifacts:** `compliance/soc2/evidence-collection/STORY-SOC-03_evidence-collection.md`,
`compliance/soc2/evidence-collection/export_soc2_evidence.py`
**Depends on:** STORY-SOC-02 (matrix defines what to collect)

## Goal
Define the continuous evidence-capture structure + low-risk automation so Type II can prove controls
operate over time — captured across the window, not reconstructed at the end.

## Acceptance Criteria
- **AC-1 [CC] ✅** Evidence-collection layout: per control, artifact + cadence + store (git/CI/SIEM/DMS/provider).
- **AC-2 [CC] ✅** Which evidence STORY-404's pipeline already emits vs what needs new capture; confirm
  404's schema is sufficient (decision-level) and flag fields that belong to the admin `AuditEvent`
  stream instead — so 404 is not re-opened.
- **AC-3 [CC] ✅** Low-risk automation (`export_soc2_evidence.py`) for recurring evidence — **read-only,
  no runtime touch, no DB, no network.**
- **AC-4 [HUMAN] ⬜** Security owner confirms the collection cadence meets the auditor's expectations.

## Out of Scope
- Building missing controls; anything that alters runtime behavior; WORM storage (client SIEM owns it).

## Non-Functional Requirements
- Export script imports no app module, opens no DB, makes no network call; passes `ruff`.

## Definition of Done
- [x] Every in-scope control has an evidence-capture path. [x] 404-schema sufficiency confirmed / gaps flagged. [x] No runtime behavior changed.
- [ ] Security owner confirms cadence — OPEN.

## Traceability
| AC | Evidence | Files |
|---|---|---|
| AC-1 | collection layout | `.../STORY-SOC-03_evidence-collection.md` §2 |
| AC-2 | 404 sufficiency check | same, §3 |
| AC-3 | read-only exporter | `.../export_soc2_evidence.py` |
| AC-4 | cadence block (human-set) | `.../STORY-SOC-03_evidence-collection.md` §5 |
