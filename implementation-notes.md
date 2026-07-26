# observation-to-evidence-bridge — Vertex findings persisted for persona UI review
Stage: standard

Goal (user request): make a real Vertex AI log flow end-to-end — adapter fetches
from the export, processes, evaluates observation findings, **stores them in the
DB the UI reads**, so the three personas (AI Auditor / Risk Officer / Compliance
Lead) review and act (remediation/disposition) in the existing UI. User picked
"Build the DB bridge (full E2E)" over observation-only or the Bedrock path.

## Lifecycle
- [x] discover   (two-plane map via Explore agent: Pipeline A content-scoring writes Audit/ScanReport/AuditTrace which the UI reads; Pipeline B observation terminates at print/JSON — no writer, no UI surface)
- [x] shape      (fork resolved by AskUserQuestion → "Build the DB bridge (full E2E)"; sub-decisions defaulted + logged below)
- [x] preview    (skipped — reuses existing TRACE/Risk/Compliance UI unchanged; no new visual design)
- [x] plan
- [x] build      (services/observation_ingest.py writer + scripts/demo_vertex_to_ui.py + runbook Part 7 + 5 pins)
- [x] verify     (full E2E run in-session on the real corpus: 53 records → 66 observation traces persisted; hash chain valid; ORM-verified rows)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| Referenced artifact | Verified? | File path |
|---|---|---|
| Vertex adapter parse (body-free) | yes | `adapters/vertex_ai/parse.py:146` `parse_record` |
| Vertex export reader (GCS/local) | yes | `adapters/vertex_ai/source.py` `VertexExportReader.for_tenant` |
| Observation evaluate → Finding | yes | `rule_packs/observation/evaluate.py:194` `evaluate_records` |
| Finding schema (rule_id/severity/title/remediation/request_id/detail) | yes | `rule_packs/observation/evaluate.py:24-51` |
| Audit table (parent, tenant NOT NULL, sample_count NOT NULL) | yes | `models.py:107` |
| ScanReport (overall_risk_score, report_json NOT NULL) | yes | `models.py:146` |
| AuditTrace (check_type/check_name/result/reason/remediation_hint, hash chain) | yes | `models.py:289` |
| Hash-chain helpers | yes | `services/hash_chain_service.py:32,53` `build_event_payload`/`compute_event_hash`; sentinel `:29` |
| Reference writer to mirror | yes | `routers/scan.py:139` `_persist_traces` |
| UI reads these tables (TRACE/Risk/Compliance) | yes | `routers/trace_view.py:128,162`; `routers/risks.py:77`; `routers/compliance_hub.py:88` |
| Remediation action personas take | yes | `routers/remediation.py` (AuditTrace.is_remediated / remediated_by_id) |
| Existing offline runner to extend | yes | `scripts/demo_azure_vertex_e2e.py` |

## Decision Log

(format: question → answer → architectural consequence)

| Question | Answer | Architectural consequence |
|---|---|---|
| New table + UI, or map onto existing evidence tables? | Map onto existing Audit + ScanReport + AuditTrace. | Zero frontend change, zero migration; all three personas' existing pages render Vertex findings immediately. |
| How to keep this honest re INV-2 / "risk score" positioning? | `AuditTrace.check_type = "observation"` (NOT `risk_domain`); `ScanReport.report_json.score_basis = "observation_coverage"` + disclaimer string; `dataset_name = "Vertex observation — <system>"`. Score is a severity rollup, labeled, never called content risk. | Observation evidence is visibly distinct from content-scoring in the trace; no overclaim. compliance-guard: evidence-only language preserved. |
| Score derivation for overall_risk_score (UI ×100)? | Weighted severity rollup: HIGH=1.0, MEDIUM=0.6, LOW=0.3, INFO=0.05; report score = max finding weight in the batch (worst-observation), 0 if none. | A HIGH tool-scope violation surfaces as a high band on the persona dashboards; deterministic; documented in report_json. |
| AuditTrace.result value per finding? | severity HIGH→"flagged", MEDIUM→"warn", LOW/INFO→"warn" (all non-pass so they surface in TRACE/Remedy/Dashboard filters which key on {fail,warn,flagged,triggered}). A record with zero findings → one "pass" trace so the invocation still appears. | Findings are actionable (remediation/disposition) exactly like content-scoring traces. |
| One Audit per invocation, or per batch? | One Audit per source system per ingest run (sample_count = #records); one AuditTrace per finding, request_id in detail_json + signal_text. | Matches how a persona thinks ("this Vertex system's observation audit"); keeps the Audits list readable. |
| Fetch: live GCS or local export file? | Support both via the existing `VertexExportReader` (gs:// store or local root) — same reader the adapter already uses; demo defaults to a local NDJSON path, `--source gs://…` for the real bucket. | Real "adapter fetches" path; no new fetch code; INV-6 read-only preserved. |
| Entry point: extend cli.py ingest or new command? | New `services/observation_ingest.py` (reusable writer) + standalone `scripts/demo_vertex_to_ui.py`. cli.py `ingest` stays Bedrock/Pipeline-A only (it runs the content engine); mixing would blur semantics. (Deviation: built the standalone script rather than a `cli.py observe` subcommand — keeps cli.py's guard-cleanliness contract untouched and matches the existing demo-script pattern; a cli subcommand can wrap the same service later.) | Clean separation: content-scoring ingest vs observation ingest; both land in the same evidence tables the UI reads. |

## Plan (tweak-likelihood order)

1. **`services/observation_ingest.py`** (data-model heart): `persist_observation_findings(db, *, tenant_id, user_id, system_id, records, packs) -> IngestResult`. Fetches nothing itself; takes already-read records (caller uses VertexExportReader). Evaluates via `evaluate_records`, derives the severity rollup, writes Audit + ScanReport + AuditTrace (hash-chained, reusing hash_chain_service), returns audit_id + counts. Idempotency: skip if an Audit with the same batch_id exists.
2. **`cli.py observe`** subcommand + **`scripts/demo_vertex_to_ui.py`**: wire VertexExportReader (gs:// or local) → persist_observation_findings, print the audit_id + a per-persona "where to look" pointer.
3. **Runbook Part 7**: the full E2E — fetch → process → evaluate → store → each persona's review+action path, with the honest score-basis note.
4. **Tests**: `tests/test_observation_ingest.py` — persists to an in-memory DB, asserts Audit/ScanReport/AuditTrace rows, check_type=="observation", hash chain valid, score rollup, idempotency, tenant binding from config not log (INV-3).

## Review round 1 (security-auditor)

Verdict: CHANGES-REQUIRED → all 4 fixed before commit:
1. HIGH INV-3: idempotency query was not tenant-scoped (obs:<system> could match
   another tenant's audit → data loss + cross-tenant audit id). Fixed: filter
   adds Audit.tenant_id==tenant_id; regression test
   test_idempotency_is_tenant_scoped_no_cross_tenant_match.
2. MEDIUM: CRITICAL/unknown severity fell through to (0.3,"warn") — a downgrade.
   Fixed: added CRITICAL=(1.0,"flagged"); unmapped fails SAFE to (1.0,"flagged");
   pinned by test_unknown_severity_fails_safe_to_flagged.
3. MEDIUM positioning: board risk aggregate (routers/risk_dashboard.py) blended
   observation scores into the content-risk RAG number. Fixed: excludes
   score_basis=="observation_coverage" reports from the content aggregate.
4. LOW: gs:// path was non-functional (no GCS backend) yet documented. Fixed:
   script exits with a clear message; docs show download-then-local.
Cleared by the auditor: write-path tenant binding, hash-chain parity, INV-2
body-free, NOT-NULL coverage, INV-6 scope/read-only.

## Deviations
- Persona *read* endpoints (TRACE/Risk/Compliance) 500 under the SQLite
  fallback's UUID shim, same known limitation as the persona-walk PR; the WRITE
  path and persisted rows were verified directly via ORM (Audit + ScanReport +
  66 AuditTrace, all check_type=observation, chain valid). Postgres
  (run_local.ps1) is the read gate; documented in runbook Part 7.
- Hash-chain test reconstruction: SQLite drops tzinfo on datetime read and
  str(None)=='None' for gate_id — the writer mirrors production _persist_traces
  exactly (matches on Postgres); the TEST reconstruction re-labels naive UTC and
  uses str(gate_id) to match audit_chain._event_dict. Not a writer bug.
