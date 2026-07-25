# azure-vertex-e2e-demo — Azure OpenAI + Vertex AI end-to-end demo kit
Stage: standard

Goal (user request, expert phrasing): package SARO's existing Azure OpenAI and
Vertex AI observation adapters (STORY-359/360) into a runnable end-to-end demo:
(1) cloud-side + SARO-side setup instructions, (2) a deterministic offline demo
runner that walks export → adapter → contract → rule-pack findings → evidence
summary, (3) a screen-capture-style animated screencast of the run, embeddable
and committed.

## Lifecycle
- [x] discover   (adapters/rule-pack pipeline mapped; demo surface reviewed)
- [x] shape      (autonomous session — decisions self-answered, see Decision Log)
- [x] preview    (skipped — no app UI change; the screencast artifact IS the preview)
- [x] plan
- [x] build      (runner + screencast builder + doc + tests implemented; gates below)
- [x] verify     (change-debrief.html rewritten for this task; ruff/mypy/pytest green)
- [ ] sell       (n/a unless requested)

## Premise check (Stage 3a)

| Referenced artifact | Verified? | File path |
|---|---|---|
| Azure OpenAI adapter (STORY-359) | yes | `adapters/azure_openai/parse.py` (`parse_record`) |
| Vertex AI adapter (STORY-360) | yes | `adapters/vertex_ai/parse.py` (`parse_record`) |
| Normalized contract (STORY-358) | yes | `adapters/contract.py` (`NormalizedInvocationRecord`) |
| Observation rule packs | yes | `rule_packs/observation/rp_obs_complete/1.0.0/pack.yaml`, `rp_tool_scope/1.0.0/pack.yaml` |
| Evaluator | yes | `rule_packs/observation/evaluate.py` (`evaluate_records`) |
| Pack loader | yes | `rule_packs/observation/loader.py` (`load_genesis_packs`, `with_allowed_tools`) |
| Azure corpus (54 records) | yes | `tests/fixtures/azure/corpus.ndjson` (builder `scripts/azure_corpus_builder.py`) |
| Vertex corpus (56 records) | yes | `tests/fixtures/vertex/corpus.ndjson` (builder `scripts/vertex_corpus_builder.py`) |
| Adapter design doc | yes | `docs/adapter-design.md` |
| Capability matrix | yes | `docs/adapter-capability-matrix.md` |
| Demo pre-flight runbooks | yes | `RB-005-enterprise-demo-prep.md`, `RB-006-live-demo-verification.md` |

## Decision Log

Autonomous session (goal hook active, user away) — questions answered with the
conservative default and recorded here for review.

| Question | Answer | Architectural consequence |
|---|---|---|
| What does "set up Azure OpenAI and Vertex AI" mean given INV-1 (SARO never calls external models)? | Demo the **observation adapters**: customer-owned log exports → adapter → rule packs. Setup instructions cover the *customer's* cloud config (Diagnostic Settings / audit-log sink); SARO itself gets no cloud credentials. | No new external calls, no SDKs added; posture non-negotiables untouched. |
| Live cloud accounts or committed corpora for the demo run? | Committed deterministic corpora (54 Azure + 56 Vertex records). Live-export wiring is documented as the production path, not executed in the demo. | Demo runner is offline, deterministic, CI-testable; zero network. |
| New service/endpoint or a script? | A read-only CLI script (`scripts/demo_azure_vertex_e2e.py`) reusing existing parse/evaluate functions. No routes, no DB writes. | No API surface change; no AUDITED/DATA_PLANE classification work. |
| "Video" format? | Real captured run rendered as (a) animated SVG screencast committed to `docs/demo/` (plays inline on GitHub) and (b) self-contained HTML player. Generator committed (`scripts/build_demo_screencast.py`) so the capture reproduces from the deterministic run. | No binary video blobs in git; artifact regenerable; CSP-safe self-contained HTML. |
| Compliance language tier? | Tier 3 per COMPLIANCE_CLAIMS_MATRIX (no external framework-alignment claims in demo materials); evidence-shaped wording only; required disclaimer printed by the runner. | compliance-guard constraints satisfied by construction. |
| Tool-scope allowlist for the demo tenant? | Azure: `["search_care_guidelines"]`; Vertex: `["lookup_care_pathway"]` — matches the corpora's enriched records so TOOL-SCOPE findings actually fire on the violation records. | Pure evaluation-time config via `with_allowed_tools`; pack files unchanged. |

## Plan (tweak-likelihood order)

1. **Demo runner output shape** (most tweak-likely): staged 5-step terminal
   walk per provider — read export → parse → contract guarantees → rule-pack
   evaluation → evidence summary; `--json-out` for machine-readable summary.
2. **Doc structure**: `docs/demo/AZURE_VERTEX_E2E_DEMO.md` — Part 1 Azure cloud
   setup, Part 2 GCP setup, Part 3 SARO-side, Part 4 demo walk + talk track,
   Part 5 troubleshooting + screencast embed.
3. **Screencast pipeline**: run → transcript → SVG/HTML render (deterministic).
4. Mechanical: pytest coverage for runner determinism + forbidden-phrase guard;
   gates; commit; PR. Trusted refactoring: none — no existing code modified.

## Review round 1 (independent reviewer agent)

Verdict: APPROVE with 4 minor findings — all fixed before commit:
1. Step-5 narration overstated Finding contents (no cursor field on Finding) →
   reworded to "request id that joins back to the source cursor" (runner + doc).
2. Disclaimer not verbatim per COMPLIANCE_CLAIMS_MATRIX and missing from
   --json-out → matrix wording with v{__version__} used; `disclaimer` key added
   to the JSON summary.
3. Tier 3 not pinned → framework names (nist, ai rmf, eu ai act, iso 42001,
   aigp) added to the test's forbidden-phrase list.
4. Debrief said "8 pins", file has 7 tests → corrected.

## Deviations
- SHAPE interview not conducted live: session is autonomous (goal hook);
  conservative defaults chosen and logged above instead of blocking on answers.
  Aggressive option would have been live Azure/GCP provisioning in-session
  (rejected: credentials absent, and would blur SARO's read-only posture).
