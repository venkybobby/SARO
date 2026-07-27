# gcs-direct-read — pull Vertex logs straight from the customer GCS bucket
Stage: standard

Goal (expert phrasing): implement a real `gs://` ObjectStore backend so SARO
reads the Vertex export directly from the customer-owned GCS bucket — no manual
`gcloud storage cp` download. This is the load-bearing sales claim ("we pull
from your logs"). Must preserve INV-6 (read-only), INV-3 (tenancy from operator
config, never the log/bucket), and INV-2 (body-free — unchanged; parsing is
untouched).

## Lifecycle
- [x] discover   (ObjectStore protocol mapped: list_keys/read_text; LocalExportStore is the reference; build_store is the factory; VertexExportReader.uri_scheme="gs" already)
- [x] shape      (autonomous session — decisions defaulted + logged below)
- [x] preview    (skipped — backend/adapter only, no UI change)
- [x] plan
- [x] build      (GcsExportStore + parse_gs_uri/build_gcs_store; demo gs:// wiring; requirements; 7 tests; runbook)
- [x] verify     (44 tests green incl. conformance + vertex adapter; security-auditor review requested)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| Referenced artifact | Verified? | File path |
|---|---|---|
| ObjectStore protocol (list_keys/read_text) | yes | `adapters/export_source.py:33-42` |
| LocalExportStore reference impl | yes | `adapters/export_source.py:83-106` |
| Scope guards (normalize_key, in_scope) | yes | `adapters/export_source.py:57-82` |
| build_store factory | yes | `adapters/export_source.py:219-227` |
| Vertex reader binds scheme "gs" | yes | `adapters/vertex_ai/source.py:25` (`uri_scheme = "gs"`) |
| Demo driver rejects gs:// today | yes | `scripts/demo_vertex_to_ui.py` ("gs:// sources are not yet wired") |
| GCS SDK NOT installed | yes | `python -c import google...` → ModuleNotFoundError |
| Reader downloads text per key | yes | `adapters/export_source.py:190` (`store.read_text(...)`) |

## Decision Log

(format: question → answer → architectural consequence)

| Question | Answer | Architectural consequence |
|---|---|---|
| SDK or raw REST for GCS? | `google-cloud-storage` SDK, **lazy-imported** inside the store (only when no client is injected). Add to requirements.txt. | Module import stays dependency-free (guard cleanliness, CI without the dep); missing SDK → one actionable error, not an opaque ImportError. |
| Auth model? | Application Default Credentials (ADC) — picks up the `saro-reader` SA via `GOOGLE_APPLICATION_CREDENTIALS`, gcloud ADC, or workload identity. No keys in code/config. | Matches the runbook's read-only reader-principal story; no new secret to store; INV-6 read-only (SDK client used only for list+download). |
| How is tenancy kept out of the bucket identity (INV-3)? | `container` = bucket name is operator-supplied via `--source gs://<bucket>`; the store never reads project/tenant hints from object content. Prefix scope enforced by the SAME `in_scope`/`normalize_key` used for local. | One isolation code path for local + GCS; no GCS-specific bypass. |
| Read-only guarantee (INV-6)? | Store implements ONLY `list_keys`+`read_text` (list_blobs + download_as_text). No write/delete method exists to call by accident — same structural guarantee as LocalExportStore. | The Protocol has no write surface; a write can't be reached. |
| Testable without network/SDK? | `GcsExportStore(bucket, client=<fake>)` — client is injectable; unit tests pass a fake exposing `list_blobs`/`blob().download_as_text()`. Real SDK only built when client is None. | CI needs no google dep and makes no network call; isolation logic tested on the real store class. |
| gs:// parsing lives where? | New `build_gcs_store(source)` + a `parse_gs_uri` helper; demo script derives `container`=bucket and `prefix` from the `gs://bucket/prefix` URL so the operator passes one flag, not three. | Fewer mismatched-flag errors; `--container`/`--prefix` become optional when `--source` is a gs:// URL. |

## Plan (tweak-likelihood order)

1. `GcsExportStore` in `adapters/export_source.py` — `list_keys` (list_blobs +
   in_scope filter), `read_text` (download_as_text), injectable client, lazy SDK
   import with actionable error. `parse_gs_uri("gs://b/p") -> (bucket, prefix)`
   and `build_gcs_store(...)`.
2. Wire `scripts/demo_vertex_to_ui.py`: when `--source` starts `gs://`, build the
   GCS store, derive container/prefix, drop the "not wired" bail-out.
3. requirements.txt: add `google-cloud-storage`.
4. Tests: fake-client store (list scoping incl. tenant-10 vs tenant-1, traversal
   reject, read one blob), gs:// URI parse, missing-SDK error message.
5. Runbook Part 2/7: replace the "download first" hop with the direct gs:// run.
6. security-auditor review (new egress + input-handling path in adapters/).

## Review round (security-auditor)

Verdict: PASS — no FND. INV-6/INV-3/INV-2 + tenant isolation preserved; GCS path
reuses the identical scope logic as the local store, no bypass. Applied
defense-in-depth obs. #1: read_text now normalize_key()s the key so traversal is
rejected at the store even if used outside the reader. Obs. #2 (traversal blob
aborts batch) and #3 (empty prefix = whole bucket) are documented parity with
LocalExportStore, no change.

## Deviations
None.
