# STORY-102: Reconcile "never calls external AI models" claim with the Gate-3 LLM judge

**Status:** ready (decision resolved 2026-06-12: keep judge, make model swappable, honest claim)
**Screen/Area:** Compliance posture — engine.py Gate 3, docs/COMPLIANCE_CLAIMS_MATRIX.md, CLAUDE.md, UI copy

## Goal
SARO's constraint #1 (CLAUDE.md) states SARO "Accepts only `prompt` + `raw_output` — never calls external AI models." But `engine.py` constructs `anthropic.Anthropic(...)` and calls it in the Gate-3 hybrid pass when `ANTHROPIC_API_KEY` is set (`engine.py:1352-1361`). The blanket claim is repeated verbatim in ~8 code/UI locations. **Decision (owner, 2026-06-12): keep the LLM judge — Anthropic for now — but make the model/provider swappable so a cheaper model can be adopted later without code surgery, and make the public claim honest about the optional pass.** This story therefore does two things: (1) reword the external-model claim into a bounded carve-out; (2) abstract the judge's model/provider behind configuration, defaulting to the current Anthropic model.

## Decision (resolved)
- **KEEP** the Gate-3 LLM-judge verification pass (do **not** delete it).
- **Make it model/provider-configurable:** the model id (currently hardcoded `claude-sonnet-4-20250514` at `engine.py:1411`) and provider become config/env-driven (e.g. `SARO_LLM_JUDGE_MODEL`, and a provider seam so a non-Anthropic cheap model can be slotted in later). Default stays Anthropic + the current model so behavior is unchanged today.
- **Reword the claim** (Option B): core scoring never calls external models; an **optional, off-by-default** Gate-3 LLM-judge pass calls the configured provider only when its API key is set. Update CLAUDE.md #1, COMPLIANCE_CLAIMS_MATRIX.md, and all UI/doc copies to this honest, bounded wording — **without** broadening any compliance claim.

## Context (file:line)
- `engine.py:1345-1355` — reads `ANTHROPIC_API_KEY`, sets `hybrid_mode`, builds `anthropic.Anthropic(api_key=...)`.
- `engine.py:1361,1411` — calls the judge; records `"model": "claude-sonnet-4-20250514"` in `llm_classification`.
- Claim copies: `CLAUDE.md:44`, `routers/output_audit.py:7`, `routers/ingest.py:180`, `routers/insights.py:10`, `frontend/tabs/dashboard.py:829`, `frontend/src/pages/HowSaroReasons.jsx:37`, `frontend/src/pages/Upload.jsx:54`, `veriaegis-landing/app/components/FAQ.tsx:9`.
- `docs/COMPLIANCE_CLAIMS_MATRIX.md` — currently has **no** carve-out for the LLM judge.

## Acceptance Criteria (Given/When/Then)
- **AC-1 (claim):** Given the codebase, When searched, Then every blanket "never calls external AI models" string is replaced with the bounded carve-out wording, and `docs/COMPLIANCE_CLAIMS_MATRIX.md` documents the optional Gate-3 judge with its off-by-default condition. No compliance claim is broadened.
- **AC-2 (single source of truth):** Given the build, When complete, Then there is exactly **one** authoritative statement of SARO's external-model posture and zero locations that contradict it (verified by a grep-based test).
- **AC-3 (configurable model):** Given the Gate-3 judge, When it runs, Then the model id and provider are resolved from configuration/env (default = current Anthropic model `claude-sonnet-4-20250514`), not hardcoded; the recorded `llm_classification.model` reflects the configured model.
- **AC-4 (provider seam):** Given a future cheaper model, When its config is supplied, Then it can be selected without editing `engine.py`'s call sites (a thin provider/model indirection exists); with no config, today's Anthropic behavior is byte-for-byte unchanged.
- **AC-5 (compliance-guard):** Given the compliance-guard rules, When reviewed, Then no forbidden overclaiming phrase is introduced and the read-only audit posture is unchanged.

## Edge Cases
- Copies inside files that other stories delete (`frontend/tabs/dashboard.py` → STORY-105; `veriaegis-landing/...` → STORY-106) — coordinate so the claim isn't "fixed" in a file that's about to be removed.
- Coupling with STORY-101: 101 fixes the input to this judge call; since the judge is being kept, 101 stays fully relevant. Order 101 before 102 so the configurable-model work lands on a correct call site.

## Out of Scope
- Fixing the judge's input mechanics (STORY-101).
- Any change to scoring math.

## Non-Functional Requirements
- Follow `.claude/skills/compliance-guard`. Do not weaken SARO positioning except via the explicit, user-approved Option B edit.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 (claim) | `test_no_unqualified_never_calls_external_ai_models` | CLAUDE.md, .cursor/rules, .github/workflows/claude-pr-review.yml, 2×SKILL.md, routers/insights.py, frontend/src/pages/{HowSaroReasons,Upload,KnowledgePortal}.jsx, tests/test_insights_api.py |
| AC-2 (single source) | `test_no_unqualified_never_calls_external_ai_models`, `test_matrix_documents_optional_gate3_judge`, `test_claude_md_discloses_the_exception` | docs/COMPLIANCE_CLAIMS_MATRIX.md, CLAUDE.md |
| AC-3 (config model) | `test_gate3_judge_model_is_configurable`, `test_llm_classification_model_name` | engine.py |
| AC-4 (provider seam) | seam at engine.py ~1366 (unknown provider → keyword-only fail-safe); `test_engine_judge_model_and_provider_are_config_driven` | engine.py |
| AC-5 (compliance-guard) | `test_matrix_documents_optional_gate3_judge` (no forbidden phrases) | docs/COMPLIANCE_CLAIMS_MATRIX.md |

**Decision-as-built:** kept the judge (Anthropic default), model swappable via `SARO_LLM_JUDGE_MODEL` / provider via `SARO_LLM_JUDGE_PROVIDER`. Reworded the **authoritative** posture statements + enforcement-rule mirrors; left the per-router/UI "you provide the output" copies (output-generation framing, contextually accurate). Independent `reviewer`: initial CHANGES REQUESTED (3 bare-absolute restatements + missing AC-2 grep test) → all addressed (reworded insights.py/HowSaroReasons×2/Upload/KnowledgePortal/test comment; added grep pin) → resolved. Branch `story/STORY-102_external_model_claims_reconciliation` (stacked on 101).
