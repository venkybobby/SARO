-- Migration 015: Allow NULL gate_id on audit_traces for post-gate summary rows.
--
-- The engine writes two summary trace rows that are not associated with
-- any specific gate: "Explain" (Bayesian risk summary) and "Remediate"
-- (remediation guidance).  These rows have gate_id=None which the DB
-- currently rejects with a NOT NULL constraint violation, causing every
-- scan to return a 500 Internal Server Error.
--
-- Fix: make gate_id nullable.  Existing rows (all real gate results) are
-- unaffected — they already carry a valid integer gate_id (1–4).
--
-- Safe to re-run: ALTER COLUMN is idempotent if already nullable.

ALTER TABLE audit_traces ALTER COLUMN gate_id DROP NOT NULL;
