# Azure OpenAI + Vertex AI — End-to-End Demo Setup & Runbook

> **Owner:** Venky (Lead) · **Status:** DRAFTED · **Scope:** demo kit for the
> Azure OpenAI (STORY-359) and Vertex AI (STORY-360) observation adapters.
> Pre-flight checklists RB-005 §§1–3/5–6 and RB-006 still apply before any
> external demo.

## What this demo shows

SARO's observation pipeline, end to end, for both providers:

```
customer-owned log export ──► adapter parse ──► NormalizedInvocationRecord ──► rule packs ──► evidence findings
 (Azure Diagnostic Settings /      (per provider)     (one body-free schema)     (RP-OBS-COMPLETE,     (for human
  GCP Cloud Logging sink)                                                         RP-TOOL-SCOPE)        auditor review)
```

**What this demo deliberately does NOT do** (positioning non-negotiables):

- SARO never calls Azure OpenAI or Vertex AI. The adapters parse the
  *customer's own log exports*; there is no SDK, no API key, and no model
  invocation anywhere in the pipeline (INV-1).
- SARO never reads prompt or completion content. The normalized record has no
  field capable of holding message content (INV-2) — step 3 of the demo proves
  this on screen.
- SARO never writes to the customer's cloud (INV-6). Access is read-only,
  scoped to one container/prefix per tenant.
- The output is audit **evidence for human review** — never a compliance
  verdict or certification.

The demo run itself is **fully offline and deterministic**: it replays the two
committed corpora (`tests/fixtures/azure/corpus.ndjson`, 54 records;
`tests/fixtures/vertex/corpus.ndjson`, 56 records) — the same bytes CI
byte-verifies. No cloud account is needed to *run the demo*. Parts 1–2 below
document how a real customer wires the equivalent exports in their own cloud.

---

## Part 1 — Azure OpenAI: producing the log export (customer's cloud)

Everything in this part happens in the **customer's** Azure subscription. SARO
receives read-only access to the resulting storage container, nothing else.

### 1.1 Prerequisites

- An Azure subscription with an **Azure OpenAI** resource and at least one
  model deployment (any chat/completions/embeddings deployment works — the
  demo corpus contains all three operation types).
- A **Storage Account** in the same region to receive diagnostic logs.

### 1.2 Enable Diagnostic Settings (category `RequestResponse`)

Portal: *Azure OpenAI resource → Monitoring → Diagnostic settings → Add
diagnostic setting* → check **RequestResponse** → destination **Archive to a
storage account**.

CLI equivalent:

```bash
RG=<resource-group>
AOAI=<azure-openai-resource-name>
SA=<storage-account-name>

az monitor diagnostic-settings create \
  --name saro-observation-export \
  --resource "$(az cognitiveservices account show -g $RG -n $AOAI --query id -o tsv)" \
  --storage-account "$(az storage account show -g $RG -n $SA --query id -o tsv)" \
  --logs '[{"category":"RequestResponse","enabled":true}]'
```

Azure delivers NDJSON log blobs to a container named
`insights-logs-requestresponse` within ~15 minutes of traffic. These records
carry `time`, `operationName`, `correlationId`, `location`, and a `properties`
bag with model identity and (on some configurations) token counts. They carry
**no prompt/completion content** — this source is body-free by nature.

### 1.3 Grant SARO read-only access

Create a role assignment scoped to the container (least privilege, read-only):

```bash
az role assignment create \
  --assignee <saro-reader-principal-id> \
  --role "Storage Blob Data Reader" \
  --scope "/subscriptions/<sub>/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$SA/blobServices/default/containers/insights-logs-requestresponse"
```

Operator-side binding in SARO (never read from the log — INV-3):
`tenant_id` + `container` + `prefix` are supplied as operator configuration
(`adapters/azure_openai/records.py::AzureAdapterConfig`).

---

## Part 2 — Vertex AI: producing the log export (customer's cloud)

Everything here happens in the **customer's** GCP project.

### 2.1 Prerequisites

- A GCP project with the **Vertex AI API** (`aiplatform.googleapis.com`)
  enabled and some generative traffic (e.g. Gemini via
  `GenerateContent`/`StreamGenerateContent`).
- A **GCS bucket** to receive the log export.

### 2.2 Enable Data Access audit logs for Vertex AI

Console: *IAM & Admin → Audit Logs → filter "Vertex AI API"* → enable
**Data Read** and **Data Write**. Or via the project IAM policy:

```yaml
auditConfigs:
  - service: aiplatform.googleapis.com
    auditLogConfigs:
      - logType: DATA_READ
      - logType: DATA_WRITE
```

### 2.3 Route the audit logs to a customer-owned GCS bucket

Worked example below uses the VeriAegis demo environment; substitute your own
project id and bucket name.

```bash
PROJECT="project-b73b6bc1-e4a6-4ee1-961"      # your GCP project id
BUCKET="saro-vertex-export-veriaegis"         # your export bucket

gcloud logging sinks create saro-observation-export \
  storage.googleapis.com/$BUCKET \
  --project=$PROJECT \
  --log-filter='protoPayload.serviceName="aiplatform.googleapis.com"'

# Grant the sink's writer identity permission to write to the bucket
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="$(gcloud logging sinks describe saro-observation-export \
              --project=$PROJECT --format='value(writerIdentity)')" \
  --role=roles/storage.objectCreator
```

Cloud Logging delivers hourly NDJSON `LogEntry` objects.

### 2.4 Create SARO's read-only reader principal

SARO never brings its own credentials — the customer creates a reader
service account in their project and grants it **bucket-scoped, read-only**
access (INV-6). Never grant a project-wide role.

```bash
gcloud iam service-accounts create saro-reader \
  --project=$PROJECT \
  --display-name="SARO read-only log export reader"
# Resulting principal (the "SARO service account email"):
#   saro-reader@$PROJECT.iam.gserviceaccount.com
# Worked example: saro-reader@project-b73b6bc1-e4a6-4ee1-961.iam.gserviceaccount.com

gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:saro-reader@$PROJECT.iam.gserviceaccount.com" \
  --role=roles/storage.objectViewer
```

The reader's identity never sets SARO tenancy — the tenant binding stays
operator-supplied configuration (INV-3), exactly as the demo's step 2 shows.

### 2.5 Generate a bigger sample corpus (optional)

A fresh export may hold only a handful of records. To produce a richer corpus
for the demo, issue a batch of varied Vertex calls in your project and let the
sink deliver them:

```bash
# Dry run — see the plan, no calls, no auth:
python scripts/generate_vertex_demo_traffic.py --project $PROJECT --dry-run

# 100 calls (70 happy · 15 streaming · 15 deliberate errors), 2 regions:
python scripts/generate_vertex_demo_traffic.py --project $PROJECT
```

**Identity note:** this generator *calls* Vertex, so it needs an invoke
principal with `roles/aiplatform.user` — your own ADC
(`gcloud auth application-default login`) or a dedicated SA. That is **not**
`saro-reader` (read-only storage). It is demo tooling that produces
customer-side traffic; SARO's scoring still never calls a model (INV-1). The
error calls surface as `OBS-ERROR-INVOCATION` findings; every record yields an
`OBS-TOKEN-COUNTS` INFO. Wait for the hourly sink delivery, then re-run the
reader (Part 7).

> **Content hazard, handled by construction:** Vertex *Data Access* audit logs
> can include `protoPayload.request`/`.response` — for generative calls, the
> actual prompt and output. SARO's Vertex parser is **body-blind**: no code
> path reads those keys, pinned by
> `tests/test_story360_vertex_adapter.py::test_phi_payload_present_in_source_never_reaches_the_record`.
> The demo corpus plants PHI-shaped payloads so this guard is exercised, not
> vacuous.

---

## Part 3 — SARO side: running the demo

### 3.1 Setup

```bash
git clone https://github.com/venkybobby/SARO && cd SARO
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

No environment variables, no database, and no cloud credentials are required
for the demo run.

### 3.2 Run it

```bash
# Both providers, full walk (the version captured in the screencast):
python scripts/demo_azure_vertex_e2e.py

# One provider at a time:
python scripts/demo_azure_vertex_e2e.py --provider azure
python scripts/demo_azure_vertex_e2e.py --provider vertex

# Machine-readable summary for follow-up analysis:
python scripts/demo_azure_vertex_e2e.py --json-out artifacts/demo-e2e/summary.json

# Slowed output for live screen capture:
python scripts/demo_azure_vertex_e2e.py --pace 0.35
```

To point the same walk at a **real export** downloaded from Part 1/Part 2
storage (NDJSON, one record per line):

```bash
python scripts/demo_azure_vertex_e2e.py \
  --azure-corpus  /path/to/insights-logs-requestresponse/....ndjson \
  --vertex-corpus /path/to/gcs-export/....ndjson
```

---

## Part 4 — The five demo steps and the talk track

Each provider walks the same five steps. Expected numbers below are exact —
the corpora and the pipeline are deterministic, so any drift from these values
is a regression, not noise.

| Step | What appears on screen | What to say |
|---|---|---|
| **[1/5] Read export** | 54 (Azure) / 56 (Vertex) records read from the corpus | "This is the customer's own log export. SARO reads it read-only — we hold no write scope in their cloud." |
| **[2/5] Adapter parse** | Azure: 52 normalized · 1 skipped · 1 rejected. Vertex: 53 normalized · 1 skipped · 2 rejected | "Records SARO can't interpret are skipped or rejected, never guessed at — a fabricated observation is worse than a missing one." |
| **[3/5] Contract invariants** | The full 15-field contract; availability rollup per field | "Notice what's *not* there: no prompt, no completion field at all. Content can't leak into evidence because the schema has nowhere to put it. And where a provider doesn't emit a field — Vertex never reports token counts — we say `unavailable`, we don't silently pass." |
| **[4/5] Rule-pack evaluation** | Pack refs + content hashes, findings by rule, the out-of-scope tool warning | "Two genesis packs, content-hashed for provenance. The high-signal one: the agent invoked `delete_patient_record` (Azure) / `purge_audit_log` (Vertex) — tools outside the tenant's declared scope." |
| **[5/5] Evidence summary** | Azure: 14 findings / 52 invocations. Vertex: 66 findings / 53 invocations. Disclaimer | "Every finding is evidence for a human auditor — rule id, pack hash, remediation guidance, and the request id that joins back to the record's source cursor. SARO does not certify; people do." |

Why Vertex shows more findings than Azure: Vertex audit logs never report
token counts, so `OBS-TOKEN-COUNTS-1` fires (at INFO severity — a disclosed
provider limitation, not a customer defect) on every record. That asymmetry is
itself a talking point: SARO reports coverage honestly instead of hiding gaps.

---

## Part 5 — Screencast & troubleshooting

### The screen-capture video

An animated screencast of the exact run above is committed at:

- **[`docs/demo/azure-vertex-e2e-screencast.svg`](azure-vertex-e2e-screencast.svg)**
  — plays inline on GitHub (open the file, it animates).
- **[`docs/demo/azure-vertex-e2e-screencast.html`](azure-vertex-e2e-screencast.html)**
  — self-contained HTML player with play/pause/restart/speed controls; open
  locally in any browser.

Regenerate both from a fresh run (output is deterministic, so this is
reproducible byte-for-byte):

```bash
python scripts/build_demo_screencast.py
```

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: pydantic` | Dependencies not installed — `pip install -r requirements.txt`. |
| Counts differ from Part 4's table | Corpus drift — run `python scripts/azure_corpus_builder.py --check` and `python scripts/vertex_corpus_builder.py --check`; CI enforces byte-identity. |
| No `TOOL-SCOPE-*` findings on a real export | Expected on standard Azure/Vertex logs: neither schema carries tool data (see `docs/adapter-capability-matrix.md`). Zero findings here means **no data to evaluate**, not a clean result — the demo corpora include enriched records precisely to show the rules firing. |
| Real Vertex export parses 0 records | The sink filter likely captured a different service — records with `protoPayload.serviceName != aiplatform.googleapis.com` are skipped by design. |

---

## Part 6 — Persona view verification (UI)

The pipeline walk (Parts 3–4) proves the engine; this part proves what each
**user persona sees in the UI** against the same seeded demo data. It uses the
product's own persona switcher — the control a presenter uses live to show the
AI Auditor, Risk Officer, and Compliance Lead views.

### 6.1 Run it

```bash
pip install playwright && playwright install chromium   # once

python scripts/seed_demo.py                             # demo tenant + corpus
python scripts/demo_persona_ui_verification.py --ensure-user
uvicorn main:app --port 8000 &                          # backend
(cd frontend && npm install && npm run dev) &           # Vite on :5173
python scripts/demo_persona_ui_verification.py          # the walk
```

Default walk covers the three business personas; `--all` adds admin,
super_admin, and operator. Screenshots land in `artifacts/persona-ui/<persona>/`,
a machine-readable `summary.json` beside them. Exit 0 = pass.

### 6.2 What each persona must see (parsed live from Sidebar.jsx)

| Persona | Expected tabs |
|---|---|
| **AI Auditor** (`ai_auditor`) | Dashboard · TRACE View · Rule Packs · Upload & Scan · Knowledge Portal |
| **Risk Officer** (`risk_officer`) | Dashboard · Risk Register · TRACE View · AI Insights · Reports |
| **Compliance Lead** (`compliance_lead`) | Dashboard · Compliance Hub · TRACE View · Trust Center · Model Inventory · Upload & Scan · Reports |

The harness asserts the rendered sidebar is **exactly** this set (parsed from
`frontend/src/components/Sidebar.jsx` at runtime, so the table above is
descriptive — the code is the authority), walks every tab, and fails on any
API response ≥ 400 during the walk.

### 6.3 Pass conditions (mirrors RB-006 discipline)

- [ ] Each persona's sidebar shows its exact tab set — nothing missing, nothing leaking in
- [ ] Every tab renders with seeded data (screenshots reviewed by a human)
- [ ] Zero API responses ≥ 400 across all persona walks
- [ ] Persona switcher itself works (each switch is a real `PATCH /api/v1/auth/users/{id}/persona`)

---

## Part 7 — Full E2E: Vertex log → DB → persona review & action

Parts 1–4 fetch, parse, and evaluate a Vertex export; this part **persists** the
findings into the evidence tables the UI reads, so the three personas review and
act on them in the running app. The writer is `services/observation_ingest.py`;
the entry point is `scripts/demo_vertex_to_ui.py`.

### 7.1 Fetch → process → evaluate → store (one command)

**Direct from the customer's GCS bucket** (the real posture — "we pull from your
logs"). SARO reads the bucket read-only via the `saro-reader` service account
(Application Default Credentials); nothing is downloaded by hand:

```bash
# Authenticate the reader principal once (or set GOOGLE_APPLICATION_CREDENTIALS
# to its key / use workload identity):
gcloud auth application-default login   # as saro-reader@<project>.iam.gserviceaccount.com

python scripts/demo_vertex_to_ui.py \
  --tenant <DEMO_TENANT_UUID> --system gemini-prod \
  --source gs://saro-vertex-export-veriaegis/demo-tenant \
  --allowed-tool lookup_care_pathway
```

The bucket and prefix come from the `gs://` URI, so `--container`/`--prefix`
are not needed. Read access is `roles/storage.objectViewer` scoped to the bucket
(INV-6); the store has no write method at all.

**Local export** (offline demo, or a downloaded copy) — same pipeline, filesystem
source:

```bash
gcloud storage cp -r gs://saro-vertex-export-veriaegis ./vertex-export
python scripts/demo_vertex_to_ui.py \
  --tenant <DEMO_TENANT_UUID> --system gemini-prod \
  --source ./vertex-export --container saro-vertex-export-veriaegis \
  --prefix demo-tenant/ --allowed-tool lookup_care_pathway
```

It prints each stage and the `audit_id` it created:

```
[1/4] fetch    — reading Vertex export from …
[2/4] process  — 53 invocations normalized (body-free, INV-2)
[3/4] evaluate — RP-OBS-COMPLETE@1.0.0, RP-TOOL-SCOPE@1.0.0
[4/4] store    — audit_id=…  (66 findings, score=1.0)
```

Tenancy is `--tenant` (operator config, never the log's — INV-3). Idempotent on
`--batch-id` (default `obs:<system>`): re-running never double-writes.

### 7.2 What each persona reviews and can do

The ingest writes one `Audit` + one `ScanReport` (labeled
`score_basis="observation_coverage"`, **not** a content-risk verdict) + one
hash-chained `AuditTrace` per finding, all `check_type="observation"`.

| Persona | Where it appears | Review / action |
|---|---|---|
| **AI Auditor** | TRACE View → the `audit_id` | Read the observation timeline (missing-field, tool-scope, provider-error findings), verify the SHA-256 chain, **flag/remediate** a finding on the Remedy screen |
| **Risk Officer** | Risk Register | See the system's observation-coverage score; dispose/assign |
| **Compliance Lead** | Compliance Hub | The tamper-evident-trail check includes these traces; export evidence |

### 7.3 Honesty guarantees (why this doesn't overclaim)

- Traces are `check_type="observation"`, visibly distinct from content-scoring
  `risk_domain` rows — an observation finding is evidence about **log coverage /
  tool-scope**, never a content-risk score.
- `report_json.score_basis="observation_coverage"` + a disclaimer are stored, so
  the dashboard number is labeled for what it is (a severity rollup).
- Records are body-free by construction (INV-2); no code path can write content.

> **Note:** the persona *reads* (TRACE/Risk/Compliance endpoints) require the
> Postgres stack (`scripts/run_local.ps1`); the SQLite fallback persists
> correctly but several read endpoints 500 under its UUID shim. Verified end to
> end: 53 records → 66 observation traces (57 warn, 9 flagged), chain valid.

---

> *This report is audit evidence generated by SARO v8.0.0. It does not
> constitute regulatory certification, legal advice, or compliance approval.
> Human review and sign-off by qualified personnel is required before any
> regulatory submission.*
