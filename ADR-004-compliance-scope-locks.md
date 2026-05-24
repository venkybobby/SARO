# ADR-004: Compliance Framework Scope Locks

## Status
Accepted — 2026-03. Do not modify without Venky sign-off and external SME review.

## Context

SARO targets multiple regulatory frameworks. Without explicit scope locks, there is risk of:
- Overclaiming compliance coverage to enterprise buyers
- Exposing Anthropic/SARO to liability for frameworks not fully implemented
- Inconsistent framing across team communications and product demos

## Decision

The following scope locks are hard constraints across all SARO code, documentation, demos, and communications:

| Framework | Locked Scope | What This Means |
|-----------|-------------|-----------------|
| NIST AI RMF 1.0 | Full self-assessment (GOVERN, MAP, MEASURE, MANAGE) | Evidence support + workflow — not certification |
| EU AI Act | **Articles 9, 13, 17 only** | No other articles may be claimed |
| ISO 42001 | Document lifecycle linking only | Not full ISO 42001 certification support |
| AIGP | Principles evaluation only | Not audit evidence, not certifiable compliance |

## Three Critical Gaps (Blocking External Sharing)

Until these are closed, no external sharing of SARO compliance capabilities:

1. **Incident Response Plan** — not complete as of v8.0
2. **External Compliance SME engagement** — rule pack editorial review not complete
3. **Data Retention / DPA Policy** — not complete as of v8.0

## TRACE View Gate

Alex Rivera (ML Lead) must author "How SARO Reasons" transparency document before any enterprise demo of the TRACE view.

## Consequences

**Easier:**
- Clear communication to enterprise buyers — no scope creep in sales materials
- Reduced compliance liability
- Consistent framing across all team members

**Harder:**
- Cannot rapidly expand compliance claims without formal SME review + ADR update
- Demo scripts must be pre-vetted against scope locks

## Enforcement

- Hooks: `pre-edit-standards-check.sh` flags scope overreach in code
- Commands: `/saro:compliance-check` validates any feature against locks
- Plugin: `skills/compliance-context.md` bakes locks into every Claude session
