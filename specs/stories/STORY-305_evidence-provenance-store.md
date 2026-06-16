# STORY-305 — Append-only, tamper-evident evidence store

**Epic:** GRC-2 — Evidence & Provenance Layer
**Priority:** P0 · **Status:** READY · **Depends on:** none
**Encodes decision:** OPEN-DEC-3 → hash-chain in Postgres + daily external root-hash anchor (fast-follow)

## Context
This is the layer an auditor actually inspects. Every consequential output/action is persisted
with full provenance so audit conclusions are reproducible and defensible. Without it, "PASS" has
nothing behind it.

## Framework mapping
- ISO/IEC 42001: data for AI systems; logging / records.
- NIST AI RMF: MEASURE; accountable & transparent.

## Scope (in)
- An append-only evidence table capturing: model/version, prompt/inputs, retrieved_context, decision, confidence, timestamp, consumer (human/system id).
- Tamper-evidence via hash-chain: each row stores `content_hash = SHA256(payload)` and `chain_hash = SHA256(content_hash + prev_chain_hash)`.
- An integrity-verify routine that walks the chain and reports the first broken link.

## Out of scope
- The daily external anchor (separate fast-follow story). Provenance-completeness gating (STORY-306).
- Evidence-to-finding linking (STORY-307, Phase 2).

## Acceptance criteria (binary)
- [ ] A captured output is retrievable verbatim by id.
- [ ] Rows are append-only; an UPDATE/DELETE attempt on a record is rejected/blocked.
- [ ] `chain_hash` correctly chains each row to its predecessor.
- [ ] The integrity-verify routine passes on an untampered chain and flags a deliberately mutated row.

## Technical notes
- Supabase Postgres; enforce append-only at the DB layer (revoke UPDATE/DELETE; insert-only role) plus app-layer guard.
- Store the genesis (prev_chain_hash = constant) explicitly.
- Keep payload serialization deterministic (stable key order) so hashes are reproducible.

## Test requirements
- [ ] Unit: hash-chain construction and verify (clean + tampered fixtures).
- [ ] Integration: insert → retrieve → verify; mutation attempt rejected.

## Definition of done
Outputs captured with full provenance; append-only enforced; chain verifies and detects tampering; tests green.
