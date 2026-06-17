<!-- SARO PR template. The claims-consistency checklist (STORY-337) is required. -->

## What & why

<!-- Short description of the change and the story/finding it closes. -->

Closes: STORY-### / FND-###

## Claims-consistency checklist (STORY-337 — required)

The locked Compliance Claims Matrix is machine-checkable (`grc/guards/claims_registry.py`,
CI gate `python -m grc.guards.claims_registry`). Confirm this PR does not contradict a
locked claim:

- [ ] No new third-party hosted-model call on the product/runtime path (STORY-336 guard green). The only sanctioned external-model use is the offline QA lab (STORY-338).
- [ ] No copy describes AIGP as a "framework" or as a "certification" SARO issues (AIGP = principles evaluation only).
- [ ] No certification / conformance / "compliant" claim for NIST AI RMF, EU AI Act, ISO 42001, or AIGP (evidence-support language only).
- [ ] SARO's read-only / human-in-the-loop / no-write-to-client posture is preserved.
- [ ] **If a locked claim genuinely changes:** the decision is recorded in `docs/CLAIMS_AUDIT_LOG.md`, `REGISTRY_VERSION` is bumped, and the lock is regenerated (`python -m grc.guards.claims_registry --update`). A locked claim never changes silently.

## Tests & gates

- [ ] `ruff check . && ruff format --check .`
- [ ] `pytest tests/ -m unit -q` and `pytest tests/regression -q` green
- [ ] Quality ratchet holds (`scripts/check_quality_ratchet.py`)
- [ ] Independent `reviewer` (and `security-auditor` if auth/routers/middleware/rule_packs touched) approve
