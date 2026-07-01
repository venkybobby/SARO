# Epic 15 — Trust & Compliance Enablement (BAA + SOC 2 Type II)

> **Nature:** Parallel, calendar-bound governance workstream (runs alongside Epic 14).
> **Status:** In progress / roadmap. **SARO holds no certification described here.** "In progress /
> roadmap" is the honest posture until an executed BAA and a delivered SOC 2 Type II report exist.

This tree holds the **artifacts and tracking scaffolding** for two governance workstreams.
Claude Code produced the drafts; it does **not** perform the legal, procurement, or approval steps.
Every acceptance criterion in the source stories is tagged:

- **[CC]** — Claude Code produces the artifact (done here).
- **[HUMAN]** — a human gate (signature, procurement, official approval). Tracked here; **not** executed here.

> **Not legal or audit advice.** These drafts are starting points for SummitCare/SARO legal,
> privacy, and security owners. They do not constitute regulatory certification or legal advice.

## Layout

```
compliance/
├── README.md                                  # this file — index + posture
├── baa/                                       # BAA workstream (hard gate: no PHI until executed)
│   ├── STORY-BAA-01_data-flow-diagram.md      #   data-flow & residency diagram + narrative
│   └── STORY-BAA-02_execution-package.md       #   BAA components checklist + status tracker
└── soc2/                                       # SOC 2 Type II workstream (observation clock is the long pole)
    ├── STORY-SOC-01_scope-and-kickoff.md       #   TSC selection + boundary + auditor-engagement checklist
    ├── STORY-SOC-02_control-evidence-matrix.md #   TSC → actual SARO controls → gaps (no unbacked claims)
    └── evidence-collection/
        ├── STORY-SOC-03_evidence-collection.md #   per-control evidence-capture layout + cadence
        └── export_soc2_evidence.py             #   low-risk recurring evidence export (no runtime change)
```

Tracking story files (human-gate status) live alongside the rest of the repo's stories:
`specs/stories/STORY-BAA-01.md`, `STORY-BAA-02.md`, `STORY-SOC-01.md`, `STORY-SOC-02.md`, `STORY-SOC-03.md`.

## Critical path

```
BAA-01 (diagram) ──▶ BAA-02 (execution) ──▶ first PHI flow   ← hard gate: no PHI until BAA signed
SOC-01 (scope) ──▶ SOC-02 (control matrix) ──▶ SOC-03 (evidence wiring) ──▶ observation window
       └─ "clock start" (human sets observation-window start date)
```

BAA and SOC 2 run in parallel. BAA-01 → BAA-02 is the critical path to first PHI flow.
SOC-01 starts the clock and should kick off the same day.

## Anti-overclaim posture (ADR-004 / COMPLIANCE_CLAIMS_MATRIX)

Nowhere in these artifacts does SARO claim a certification it does not hold. Every SARO control
cited in the SOC 2 matrix carries a pointer to where it lives in the repo/infra; controls that do
not exist are flagged as **gaps with an owner**, not glossed over. Framework language stays at the
tier it has earned (see `docs/COMPLIANCE_CLAIMS_MATRIX.md`, EVF section).

## Owners (from CLAUDE.md team table)

| Area | Owner |
|---|---|
| Lead / final sign-off | Venky (Lead Engineer) |
| Backend / infra controls | Jordan Lee |
| ML / scoring controls | Alex Rivera |
| QA / test-gate evidence | Sam Patel, Taylor Kim |
| Legal / Privacy Office gates | **SummitCare + SARO counsel (external — human gate)** |
