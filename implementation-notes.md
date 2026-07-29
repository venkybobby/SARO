# vertex-demo-traffic — generate a ~100-call Vertex corpus for the demo
Stage: standard

Goal (expert phrasing): a committed, reusable script that issues ~100 varied
Vertex AI GenerateContent calls in the CUSTOMER's own GCP project, so the Cloud
Logging audit sink delivers a richer export for the SARO demo (more findings:
provider errors, region spread, streaming). This is **demo tooling that
exercises the customer's Vertex endpoint** — it is NOT part of SARO's scoring
pipeline (INV-1 is untouched: SARO still never calls a model to score).

## Lifecycle
- [x] discover   (Vertex REST generateContent shape + audit-log fields mapped from adapters/vertex_ai/records.py & docs/adapter-design.md §3.3)
- [x] shape      (autonomous session — decisions defaulted + logged below)
- [x] preview    (skipped — CLI script, no UI)
- [x] plan
- [x] build      (generator + 4 tests + runbook §2.5; dry-run verified, 100-call mix exact)
- [x] verify     (ruff/mypy clean; dry-run + tests green; no GCP needed)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| Referenced artifact | Verified? | File path |
|---|---|---|
| Vertex audit fields the adapter reads (methodName, status, region) | yes | `adapters/vertex_ai/records.py` (RPC_CODE_NAMES, SUPPORTED_SERVICE) |
| Adapter interprets only aiplatform.googleapis.com | yes | `adapters/vertex_ai/records.py` (`SUPPORTED_SERVICE`) |
| Errors surface as OBS-ERROR-INVOCATION | yes | `rule_packs/observation/rp_obs_complete/1.0.0/pack.yaml` (error_present) |
| google-auth available (transitive of google-cloud-storage) | yes | added in prior PR; `requirements.txt` |
| Ingest reads whole bucket / prefix | yes | `scripts/demo_vertex_to_ui.py`, `adapters/export_source.py` (GcsExportStore) |

## Decision Log

(format: question → answer → architectural consequence)

| Question | Answer | Architectural consequence |
|---|---|---|
| Which identity calls Vertex? | ADC with `cloud-platform` scope — the caller's own principal (user ADC or a SA with `roles/aiplatform.user`). NOT saro-reader (that's read-only storage). Documented loudly. | Separates the invoke identity (writes traffic) from SARO's read-only reader (INV-6 boundary stays clean). |
| SDK or REST? | REST via `google.auth` token + stdlib `urllib` — no vertexai SDK dep. google-auth is already installed. | Zero new dependency; runs anywhere the demo runner already does. |
| Scenario mix for 100? | Deterministic by index: ~70 happy-path generateContent across 4 verticals, ~15 streamGenerateContent, ~8 bad-model (→ NOT_FOUND), ~7 malformed (→ INVALID_ARGUMENT); spread over 2 regions. | Produces OBS-ERROR-INVOCATION (~15) + region variety + streaming operation names; OBS-TOKEN-COUNTS fires on every record (INFO). Deterministic → testable via --dry-run. |
| Safe to test here (no GCP)? | `--dry-run` builds and prints the plan with zero auth/network; a unit test asserts the 100-item distribution. Real calls need the operator's project + creds. | CI/local verifiable without GCP; live run is the operator's. |
| Gentle on the API? | `--pace` sleep between calls (default 0.25s); `--count` configurable (default 100). | No burst; operator controls volume. |
| Where does it live? | `scripts/generate_vertex_demo_traffic.py` + a note in the runbook Part 2. | Reusable, versioned; not wired into product code. |

## Plan (tweak-likelihood order)

1. `scripts/generate_vertex_demo_traffic.py`: `build_plan(count) -> list[Call]`
   (deterministic scenario mix), `--project/--count/--regions/--model/--pace/
   --dry-run`, ADC token + urllib POST to the regional aiplatform endpoint,
   per-call status line, summary. Loud docstring on the invoke-vs-reader
   identity split and INV-1.
2. `tests/test_generate_vertex_demo_traffic.py`: plan is 100 items, category
   distribution exact, regions/models valid, dry-run makes no network call.
3. Runbook Part 2: short "generate a bigger sample" subsection.
4. Gates; commit; new PR (prior branch PR merged).

## Deviations
None. (Live issuance needs the operator's GCP project + aiplatform.user creds; verified via --dry-run + deterministic-plan tests, which is the CI-safe equivalent.)
