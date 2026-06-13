# STORY-109: Fix stale "ai_auditor" persona mapping in the ORM fallback seed

**Status:** ready
**Screen/Area:** RBAC — database.py `_PERSONA_SEEDS`, services/persona_service.py, migrations/004

## Goal
The `ai_auditor` persona is defined in three places that disagree. `services/persona_service.py` and `migrations/004_add_persona_permissions.sql` match, but the ORM fallback seed in `database.py` (`_PERSONA_SEEDS`, used on fresh deploys where `create_all_tables()` runs before migrations) is stale/incomplete and the `admin` persona is missing from it entirely. Align the ORM seed with the authoritative persona definition so a fresh deploy grants `ai_auditor` (and `admin`) the correct tabs/actions.

## Context (file:line)
- Authoritative: `services/persona_service.py:52-65` (ai_auditor) and `:66-76` (admin).
- Matching SQL seed: `migrations/004_add_persona_permissions.sql:42-46` (ai_auditor), `:47-51` (admin).
- Stale ORM seed: `database.py` `_PERSONA_SEEDS` — ai_auditor has only `["dashboard","audit","trace","rule_packs","remediate"]` tabs / `["view_trace","view_rule_packs","remediate_trace"]` actions; missing `evidence_export, drift_alerts, upload`, missing the technical actions, no `denied_actions`, and **no admin persona row**.
- Related: FND-012 (`quality/findings.md:20`) — persona seed startup-path fragility.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given a fresh database seeded only by the ORM path (`database.py`), When persona permissions are seeded, Then the `ai_auditor` row's allowed_tabs/allowed_actions (and denied_actions + trace_mode where the ORM shape supports them) match `services/persona_service.py`'s `ai_auditor` exactly.
- **AC-2:** Given the same fresh-seed path, When seeding runs, Then the `admin` persona is present and matches the authoritative definition (no longer missing).
- **AC-3:** Given all three sources (service dict, SQL migration, ORM seed), When compared by a test, Then `ai_auditor` and `admin` are consistent across them (single source of truth honored).
- **AC-4:** Given an `ai_auditor` user after a fresh seed, When they authenticate, Then they can reach their full tab set (incl. `evidence_export`, `drift_alerts`, `upload`) and are denied `claims_matrix`/`admin_settings`/`gdpr_erasure`/`risk_summary_board`.

## Edge Cases
- Idempotent re-seed must not duplicate rows or overwrite migration-applied values incorrectly (respect FND-012's guarded-seed approach).
- ORM table shape may lack `denied_actions`/`trace_mode` columns — if so, encode the deny intent where the ORM model supports it and document the gap rather than crashing.

## Out of Scope
- Reports access for any persona (STORY-110).
- Redesigning the persona taxonomy or the role↔persona mapping.

## Non-Functional Requirements
- Follow `.claude/skills/api-conventions` + security-auditor review (touches RBAC seed). No privilege escalation: changes must not grant `ai_auditor` anything beyond the authoritative definition.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1/AC-4 | `test_ai_auditor_seed_matches_source_of_truth` (regains evidence_export/drift_alerts/upload) | database.py |
| AC-2 | `test_seed_covers_all_personas_including_admin` | database.py |
| AC-3 | `test_ai_auditor_seed_matches_source_of_truth`, `test_seed_only_uses_orm_columns` | database.py, services/persona_service.py |

**Status:** done. Replaced the stale hardcoded `_PERSONA_SEEDS` with `_build_persona_seeds()` deriving from `persona_service.PERSONA_PERMISSIONS` (single source of truth) — fixes the under-granted ai_auditor, adds the missing admin persona, drift now impossible. ORM table lacks `denied_actions`/`trace_mode` (enforced at service layer — documented gap). Independent `security-auditor`: APPROVE (no escalation; closes a privilege-regression; enforcement is allowlist via static dict, not the ORM row). Branch `story/STORY-109_ai_auditor_persona_mapping_fix` (stacked on 108).
