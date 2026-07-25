# demo-runbook-gcp-worked-example — concrete GCP values for the Vertex export setup
Stage: trivial

Single-file docs change (follow-up to merged PR #138). The runbook's Part 2
placeholders are filled with the VeriAegis demo environment as a worked
example, and a new §2.4 documents creating SARO's read-only reader principal
(`saro-reader@project-b73b6bc1-e4a6-4ee1-961.iam.gserviceaccount.com`) with a
bucket-scoped `roles/storage.objectViewer` grant — answering "what is SARO's
service account email": it is customer-created, per SARO's no-own-credentials
posture (INV-6), and never sets tenancy (INV-3).

No code, tests, or generated artifacts touched; runner output unchanged, so
the screencast byte-sync pin is unaffected.

## Deviations
None.
