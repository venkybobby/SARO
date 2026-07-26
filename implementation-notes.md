# STORY-AISEC-007 — Semantic prompt-injection on the optional Gate-3 judge
Stage: standard

## Lifecycle
- [x] discover   (existing judge infra + _redact_pii + cap + provider seam mapped)
- [x] shape      (design determined by the existing judge pattern; decisions below)
- [x] preview    (skipped — backend, no UI)
- [x] plan
- [x] build
- [x] verify     (full suite 2378 passed; reviewer APPROVE + security-auditor PASS)
- [ ] sell       (n/a)

## DISCOVER findings
- Existing Gate-3 judge (`engine.py`): `ANTHROPIC_API_KEY` gates `hybrid_mode`;
  `_gate3_llm_verify_sync(client, text, domain)` does `client.messages.create(...)`,
  parses JSON, fails safe (except → None). Bounded by `MAX_LLM_CALLS_PER_BATCH`.
  Provider seam `LLM_JUDGE_PROVIDER` (anthropic default). `_redact_pii` applied to
  fragments before egress.
- The current judge only re-checks FLAGGED samples (FP reduction) → never sees
  held-out (un-flagged) injection. New pass assesses UN-flagged samples (FN/held-out).
- Injection scan is evidence-only (`_scan_injection_impl` → traces, no _SampleFlag).
- SARO-102 (COMPLIANCE_CLAIMS_MATRIX) discloses the judge as flagged-sample re-check
  → must be updated to also disclose the un-flagged injection assessment (AC-6).

## Decision Log
- Where does the semantic pass live? → **inside `_scan_injection_impl`** (injection
  evidence is cohesive there), reusing env vars + client pattern + `_redact_pii`,
  NOT entangled with the MIT-domain Gate-3 judge.
- Default behavior? → **off** (no key → skipped; deterministic-only default unchanged).
- Which samples? → only those the deterministic detector did NOT flag (avoid dup
  cost/finding), bounded by `MAX_LLM_CALLS_PER_BATCH`.
- Test strategy? → **monkeypatch `anthropic.Anthropic`** (installed 0.84.0) to a
  fake client whose `.messages.create` returns canned JSON; assert zero calls
  when no key; PII redaction of egress text; cap; evidence-only; fail-safe.

## Plan (tweak-likelihood order)
1. **Semantic verify** `_semantic_injection_verify_sync(client, text) -> dict|None`
   in engine.py (mirrors `_gate3_llm_verify_sync`; asks injection yes/no + technique;
   parse JSON; fail safe). Verify: unit test with mock client.
2. **Pass** in `_scan_injection_impl`: after the deterministic loop, if key set +
   provider anthropic, iterate un-flagged samples (≤ cap), `_redact_pii` the
   fragment, call verify, emit evidence-only injection trace (`source:
   semantic-judge`, ATLAS AML.T0051) for "injection" verdicts. Off by default;
   fail-safe. Verify: AC-1..AC-5 tests.
3. **Disclosure** update `docs/COMPLIANCE_CLAIMS_MATRIX.md` SARO-102 (AC-6):
   optional judge now also assesses un-flagged samples for injection — still
   off-by-default, PII-redacted, bounded.
4. Tests `tests/test_aisec_007_semantic_injection_judge.py`. Gates 1-7; reviewer +
   security-auditor (engine + external-model egress); index → IMPLEMENTED; docs.

## Compliance guardrails
- Non-Negotiable #1: only the DISCLOSED off-by-default judge exception calls a
  model; core deterministic scoring untouched. Default = zero external calls.
- PII-redacted before egress (mandatory, SARO-102). Evidence-only (no score
  change). Bounded by cost cap. Disclosure updated to match code (compliance-guard).

## Review round 1 (reviewer + security-auditor agents)
- **security-auditor: PASS.** Egress-focused audit: only the PII-redacted,
  500-char-capped fragment egresses (redaction precedes every call, same text
  sent); zero client construction without a key; triple-layer fail-safe; bounded;
  provider seam fail-safe; key never logged; verdict confined to an evidence
  trace (no tool use/action). Disclosure matches. INFO (pre-existing): _redact_pii
  is structured-PII best-effort — not widened here.
- **reviewer: REQUEST-CHANGES → addressed:**
  1. [MAJOR/FM-4] No AISEC-007 index row → added IMPLEMENTED row at commit (below).
  2. [MINOR] Each judge role has its own MAX_LLM_CALLS_PER_BATCH counter →
     combined per-batch ceiling is up to 2× cap. Disclosed accurately in SARO-102.
  3. [MINOR/pre-existing] _redact_pii free-text limit — not introduced here.
  4. [MINOR] Untracked artifacts → only intended files staged.

## Deviations
- Branch off main (fresh, AISEC 001-006 merged). Independent story.
