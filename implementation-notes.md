# STORY-AISEC-001 — Deterministic prompt-injection normalization + detection rule-pack
Stage: standard

## Lifecycle
- [x] discover   (engine scoring path mapped; placement question resolved by code)
- [ ] shape      (interview — load-bearing scoring/posture decisions below)
- [x] preview    (skipped — backend-only, no UI surface)
- [ ] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## DISCOVER findings
- Core scoring = 4-gate batch pipeline (`engine.py` `SARoEngine.run_audit`).
  Gate 3 (`_gate3_risk_classification`, signals at `engine.py:160+ _RISK_SIGNALS`)
  already does keyword/regex over sample prompt/output text, emitting weighted
  `_SampleFlag`s → Bayesian domain scores → risk. This is the body-bearing path.
- Observation packs (`rule_packs/observation/rp_obs_complete`, `rp_tool_scope`)
  are body-free (INV-2) — envelope logs only. => injection detection (needs text)
  belongs in the CORE scan path (Gate 3), NOT the observation family.
- Single-output + batch ingestion both exist (`schemas.py` prompt/raw_output).
- Optional Gate-3 LLM judge is the ONLY external-model exception (SARO-102);
  this story is deterministic and must not touch that boundary.

## Premise check (Stage 3a)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Gate-3 keyword/regex signal mechanism | yes | `engine.py:160+` (`_RISK_SIGNALS`), `_gate3_risk_classification` |
| Per-sample findings stream | yes | `engine.py` `_sample_findings`, `get_sample_findings()` |
| Rule-pack loader (core) | yes | `rule_packs/loader.py`, `rule_packs/envelope_loader.py` |
| Body-bearing scan inputs | yes | `schemas.py:601-605` (`prompt`, `raw_output`) |
| Upstream normalization + heuristics | yes | cloned `detecting-indirect-prompt-injection/scripts/agent.py` |

## Decision Log
| Question | Answer | Architectural consequence |
|---|---|---|
| Injection findings affect risk score? | **Evidence-only (advisory)** | Detector emits findings onto the TRACE; does NOT feed Bayesian Gate-3 score. Existing score/flag tests do not move. Smallest, reversible increment. |
| Normalization scope? | **New detector only** | Normalize inside the injection detector; existing `_RISK_SIGNALS` matching untouched → no existing detection/score behavior changes. Hardening all signals deferred to a follow-up. |
| Corpus packaging? | **Versioned YAML rule-pack + SHA-256 hash** | Heuristics ship as `rule_packs/injection/<ver>/pack.yaml`, hashed like observation packs (satisfies AC-6). Editable without code change; auditable provenance. |

## Plan (tweak-likelihood order)
1. **New rule-pack data** (most tweak-likely): `rule_packs/injection/1.0.0/pack.yaml`
   — name/version/title, `normalization` config (max_decode_depth, max_scan_chars),
   `rules[]` (rule_id, title, severity, regex `pattern`, optional
   `atlas_technique_id`). Ports the upstream HEURISTICS corpus. Verify: pack loads
   + hash test.
2. **Detector module** `rule_packs/injection/detector.py`:
   - `normalize(text) -> (str, list[str])` — zero-width strip, tag-range drop,
     NFKC, bounded base64/ROT13 decode (depth+size capped). Verify: unit tests
     AC-1/AC-2/edge.
   - `load_injection_pack() -> InjectionPack` (compiles patterns, SHA-256 hash).
     Verify: AC-6 provenance test.
   - `scan(text, pack) -> list[InjectionFinding]` (evidence-shaped, matched_on
     raw|decoded). Verify: AC-1..AC-3 unit tests + AC-4 no-network fixture.
3. **Engine wiring** (`engine.py`): load pack once in `__init__` (warn-and-continue
   like envelope allowlist); `_scan_injection(batch)` appends evidence-only
   entries to `self._traces` (check_type `injection_scan`), PII-redacted fragments;
   called in `run_audit` after `_record_gate3_domain_traces`. NOT added to `flags`
   → zero score impact. Verify: integration test through `run_audit` (AC-1/AC-5).
4. Mechanical: tests in `tests/test_aisec_001_injection_detector.py`; gates 1-7;
   reviewer + security-auditor (rule_packs/ + input-handling touched); story index
   row → IMPLEMENTED with SHA; docs/traceability. Trusted refactoring: none.

## Compliance guardrails (enforced in code)
- Evidence-shaped trace language only ("indicators consistent with…", "human
  review required"); forbidden-phrase unit test guards it.
- PII-redacted fragments only (reuse `self._redact_pii`).
- Zero external model/network calls (no-network fixture asserts).
- Decoded payloads recorded as evidence, never re-executed/interpolated.

## Review round 1 (reviewer + security-auditor agents)
- **security-auditor: PASS.** No FAIL findings; DoS/ReDoS bounds empirically
  validated; PII redaction + inert-data handling confirmed. INFO-2 (wrap scan in
  try/except) applied. INFO-1 (redactor covers PII not secrets) is pre-existing
  gate-3 behavior, not newly introduced — no FND.
- **reviewer: REQUEST-CHANGES → all addressed:**
  1. [BLOCKER] Out-of-scope demo-file edits on the branch → **root cause: FND-087
     already merged on main (d6a14e6/#139)**; my working tree carried a divergent,
     inferior duplicate (dropped line-53 encoding). Restored all three demo files
     to main via `git checkout main --`; demo test 7/7 green. AISEC branch now
     carries only AISEC files.
  2. [MAJOR] Tests not in tests/regression/ → story NFR corrected: feature-story
     tests live in `tests/` (regression/ is for FND pins). This is a feature.
  3. [MINOR] Fragment offset misalignment → `_match` now searches original text
     (patterns are IGNORECASE); dropped the separate `.lower()`.
  4. [MINOR] `isprintable()` dropped newline-bearing decoded payloads → new
     `_is_texty()` allows `\t\n\r`.
  5. [MINOR] Untracked artifacts (demo-*/, .claude/launch.json) → not staged;
     confirmed excluded from the AISEC commit.

## Deviations
- `_scan_injection` guards `_injection_pack` with `getattr(self, ..., None)`
  (not `self._injection_pack`): some tests construct the engine via `__new__`
  and set only a subset of attributes. Conservative option mirrors the engine's
  existing `getattr(self, "_sample_findings", [])` pattern. Aggressive option
  (edit every bypass helper) rejected — brittle and wider blast radius.
- Trace emission changed from one row PER SAMPLE (incl. pass) to one row per
  FLAGGED sample + a single aggregate 'clean' trace. Reason: per-sample pass
  rows bloat the TRACE (n rows/batch) and broke `TestEngineTracing` count/shape
  assumptions. Cleaner and evidence-focused; my ACs unaffected.
