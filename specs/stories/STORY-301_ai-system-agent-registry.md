# STORY-301 — AI system & agent registry

**Epic:** GRC-1 — AI Asset Registry & Risk Tiering
**Priority:** P0 · **Status:** READY · **Depends on:** none

## Context
SARO cannot govern what it cannot see. This is the single source of truth for every AI system
and agent in the portfolio, and every downstream story (tiering, audit, gates, reporting) reads
from it.

## Framework mapping
- ISO/IEC 42001: context of the organization; AI system lifecycle (inventory).
- NIST AI RMF: GOVERN, MAP.

## Scope (in)
- A persisted registry entity with CRUD API for AI systems and agents.
- Required metadata: id, name, version, owner (named human), purpose, data_sources, model/version, lifecycle_stage, deployment_status.
- List + filter by tier, owner, lifecycle_stage.

## Out of scope
- Risk tiering logic (STORY-303). Completeness enforcement (STORY-302). Auto-discovery of systems.

## Acceptance criteria (binary)
- [ ] An entry can be created with all required fields and retrieved by id.
- [ ] `owner` must be a non-empty named human; empty is rejected at the API boundary.
- [ ] Entries can be listed and filtered by tier, owner, and lifecycle_stage.
- [ ] Every create/update writes an immutable audit-trail row (who, what, when).
- [ ] A negative test confirms a malformed entry (missing required field) is rejected.

## Technical notes
- Stack: FastAPI + SQLAlchemy model + Alembic migration; Supabase Postgres. Pydantic v2 request/response models.
- `model/version` is free-text now; foundation-model vendor linkage is a later story.

## Test requirements
- [ ] Unit: model validation (happy + each missing-field case).
- [ ] Integration: create → retrieve → filter round-trip against a test DB.

## Definition of done
Entry can be created, retrieved, filtered; required-field validation enforced; audit trail recorded; tests green.
