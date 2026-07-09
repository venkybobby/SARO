# STORY-411 — Model-Allowlist Envelope Rule (fires UC-5)
Stage: standard

## Lifecycle
- [x] discover   (recon: rule-pack schema/loader, engine Gate 3 envelope-blindness, tenancy, ADR-004, UC-5 manifest state)
- [x] shape      (AskUserQuestion → Decision Log: new Governance & Compliance category, global rule-pack allowlist)
- [x] preview    (skipped — no UI, per story Non-Goals)
- [x] plan
- [x] build
- [x] verify     (gates 1-7 green; security-auditor PASS (2 low/info, fixed);
                   reviewer REQUEST CHANGES → FND-050 (metadata-drop bug, no
                   regression test) + 3 minors fixed → re-verify pending)
- [ ] sell       (not design-partner-facing this story; on request only)

## Discover — recon findings (Explore agent, file:line cited)

- **Rule pack loader (`rule_packs/loader.py`)** is a compliance-*citation* mapper
  (`Rule{rule_id, title, domain_trigger, obligation, fixtures}` → framework
  obligation text attached to an already-triggered MIT domain). It does NOT fit
  an allowlist (no field for a model-ID list). Content scanning itself is a
  separate hardcoded dict, `_RISK_SIGNALS` (`engine.py:145-283`), keyed by MIT
  domain with keywords/regex/weight. Neither mechanism detects anything from the
  envelope — both operate on `prompt`/`raw_output` text only.
- **`run_output_audit(audit_id, raw_output, prompt=None, source_model="Unknown")`**
  (`engine.py:1097-1103`) receives **no metadata/envelope fields at all** — not
  even `modelId`. Metadata (`modelId`, `requestId`, ...) IS already built by
  `adapters/bedrock/parse.build_audit_submission` (`parse.py:314-326`) into
  `AuditSubmission.metadata`, threaded through `_default_submit`
  (`replay.py:113-132`) into `submit_audit_sync(metadata=...)`
  (`services/audit_submission.py:42-108`) — but `submit_audit_sync` receives
  `metadata` and never forwards it to `run_output_audit`
  (`audit_submission.py:103-108` calls it with only
  `audit_id/raw_output/prompt/source_model`). This is the actual gap to close —
  everything upstream of the engine already carries `modelId`/`requestId`.
- **Rule-pack temporal integrity**: no time-travel mechanism exists.
  `AuditTrace.rule_pack_version_id`/`rule_pack_content_hash`
  (`models.py:1923-1930`) are placeholder columns for future STORY-RPV-002 work,
  not yet read/enforced. Today "the rule pack active at HEAD is authoritative" —
  AC-2.3 is satisfiable by construction (same code + same config = same result,
  deterministic, no actual historical-window resolution needed).
- **Rule packs are global**, not per-tenant. `TenantRiskConfig`
  (`models.py:1053-1087`) only overrides Gate-3 domain *weights* and *keyword
  suppressions* — no envelope-policy mechanism exists to extend.
- **MIT_DOMAINS** (`engine.py:133-141`) is a fixed 7-entry list;
  `_DOMAIN_REMEDIATION_HINTS` (`engine.py:614+`) has one entry per domain;
  `_compute_rule_pack_hash` (`engine.py:973-991`) iterates `_RISK_SIGNALS`/
  `_COMPLIANCE_TRIGGERS.items()` directly (not `MIT_DOMAINS`), so a new domain
  with no `_RISK_SIGNALS` entry cannot change the existing hash. No code greps
  index `_RISK_SIGNALS[domain]` by key elsewhere (checked) — safe to add a
  domain with zero content-scan signals.
- **`_SampleFlag`** (`engine.py:579-585`): `{sample_id, domain, signal, weight,
  text}` — accumulated by Gate 3's keyword loop into both `flags` (→
  `_record_gate3_domain_traces` → `AuditTrace` rows, `check_type="risk_domain"`)
  and `self._sample_findings` (→ `SampleFinding` persistence). `flags` is a
  plain list returned by `_gate3_risk_classification` and consumed at
  `engine.py:1178-1183` before Gate 4/scoring — appendable before
  `_record_gate3_domain_traces` runs.
- **ADR-004** (repo root): forbids overclaiming ("SARO achieves full ISO 42001
  certification") and intent/verdict language; approved pattern is
  observable-only phrasing ("EU AI Act Articles 9, 13, 17 evidence support").
  Story's own required title text — "Model not on approved allowlist for this
  tenant" — is already compliant.
- **STORY-407's `scripts/demo_manifest.yaml`** already anticipated this story:
  `allowed_model_ids` (4 Claude-on-Bedrock IDs) and UC-5's planted record
  (`model_id: "anthropic.claude-instant-v1"`, comment: "modelId-allowlist rule
  is future") already exist. `primary_model_id` (clean traffic's model) is
  `anthropic.claude-3-5-sonnet-20240620-v1:0`, already inside
  `allowed_model_ids` — clean traffic should stay envelope-clean without a
  manifest edit, to be confirmed in BUILD not assumed.
- **STORY-407's E2E test custom `submit` callback**
  (`tests/test_story407_demo_corpus_builder.py:241-251`) calls
  `engine_obj.run_output_audit(...)` WITHOUT `metadata=submission.metadata` —
  must be updated so envelope evaluation actually sees `modelId` (AC-4.2).
  STORY-410's CLI (`cli.py`) needs **no change** — it already calls
  `_default_submit` → `submit_audit_sync(metadata=submission.metadata, ...)`,
  so once `submit_audit_sync` forwards `metadata` into `run_output_audit`, the
  whole production ingest path gains envelope evaluation for free.

## Decision Log
Q1 Risk-category mapping (owner)? → **New "Governance & Compliance" MIT_DOMAINS
  entry.** Overrides my recommendation (reuse "AI System Safety") — owner chose
  the more semantically precise option, accepting the added surface (MIT_DOMAINS
  list, `_DOMAIN_REMEDIATION_HINTS` entry). Scope kept tight: the new domain is
  fed ONLY by envelope evaluation (never by `_RISK_SIGNALS` keyword scanning),
  so it participates in Gate-3 trace/coverage/scoring exactly like any other
  domain but has no content-scan surface of its own — no `_RISK_SIGNALS` entry,
  no rule_pack_hash change for the existing content-scan hash.

Q2 Allowlist storage (owner)? → **In the versioned rule pack itself, global** —
  confirmed the recommended option (matches FR-2's explicit design directive
  verbatim and every other rule type's existing global-pack convention). New
  small dedicated module (`rule_packs/envelope_loader.py` + `rule_packs/
  envelope/1.0.0/envelope_allowlist.yaml`) rather than forcing the allowlist
  into `rule_packs/loader.py`'s `Rule` dataclass, which has no field for a
  model-ID list and is schema-shaped for citation-attachment, not detection.
  A separate, additive SHA-256 hash for this pack (not folded into the existing
  `rule_pack_hash`) so no other audit's existing hash-chain evidence changes
  meaning.

Q3 Where does the envelope check hook into `run_output_audit` (mine)? →
  Add `metadata: dict[str, Any] | None = None` param to `run_output_audit`;
  after `flags, gate3 = self._gate3_risk_classification(batch)`
  (`engine.py:1178`), extend `flags` with `self._evaluate_envelope_allowlist
  (metadata)`'s result before `_record_gate3_domain_traces(flags, gate3)` runs
  — so the envelope finding flows through the SAME trace/scoring/coverage
  machinery as a content finding (AC-2.2 "TRACE View drill-down parity"), with
  zero special-casing downstream. `_SampleFlag` gains an optional `detail: dict
  | None = None` field to carry `{observed_model_id, rule_id, rule_pack_version,
  request_id}` through into the AuditTrace's `detail_json` (AC-2.2). The new
  method also appends the matching `self._sample_findings` entry itself, so
  `SampleFinding` persistence and STORY-407-style test capture continue to work
  unmodified.

Q4 Metadata threading (mine)? → `services/audit_submission.py`'s
  `submit_audit_sync` already receives `metadata`; forward it into
  `engine_obj.run_output_audit(metadata=metadata)`. Backward-compatible
  (optional param, existing non-Bedrock callers unaffected — envelope check
  simply no-ops without a `modelId`).

## Plan (ordered by tweak-likelihood)

1. **Rule pack data (tweak-likely):** `rule_packs/envelope/1.0.0/
   envelope_allowlist.yaml` — `rule_id: "ENV-MODEL-ALLOWLIST-1"`, `version:
   "1.0.0"`, `domain_trigger: "Governance & Compliance"`, ADR-004-safe
   `title`/`obligation`, `allowed_model_ids` sourced from `scripts/
   demo_manifest.yaml`'s existing list, `allowed_model_id_prefixes: []` (none
   needed for the demo; the field exists per AC-2.1's "optional prefix
   entries"). Verify: `python -c "from rule_packs.envelope_loader import
   load_envelope_allowlist; print(load_envelope_allowlist())"`.
2. **Loader (tweak-likely):** `rule_packs/envelope_loader.py` —
   `EnvelopeAllowlistRule` dataclass + `load_envelope_allowlist(path=...)` +
   `is_model_allowed(rule, model_id)` (exact-then-prefix match, AC-2.1) +
   `envelope_pack_hash(rule)` (SHA-256, matches existing hash-attribution
   style). Verify: `pytest tests/test_envelope_loader.py -q` (new unit tests:
   exact match, prefix match, no match, malformed YAML raises).
3. **Engine (tweak-likely):** `engine.py` —
   - `MIT_DOMAINS` += `"Governance & Compliance"`;
     `_DOMAIN_REMEDIATION_HINTS` += entry (ADR-004-safe wording).
   - `_SampleFlag` += `detail: dict[str, Any] | None = None`.
   - `_record_gate3_domain_traces`: include `f.detail` in the per-flag dict
     appended to `domain_flags[f.domain]` so it survives into `detail_json`.
   - New `_evaluate_envelope_allowlist(self, metadata: dict | None) ->
     list[_SampleFlag]`: loads the envelope pack once (module-level cache,
     matching `_RISK_SIGNALS`'s "load once at import" pattern but via a lazy
     cached loader so a bad/missing YAML doesn't crash unrelated engine
     imports — mirrors `load_all_packs`'s "warn and continue" philosophy at
     call time, not raise-on-import), checks `metadata.get("modelId")` via
     `is_model_allowed`; if not allowed, returns one `_SampleFlag` with
     `domain="Governance & Compliance"`, ADR-004-safe `text`, `detail=
     {observed_model_id, rule_id, rule_pack_version, request_id}`, and appends
     the matching `self._sample_findings` entry itself.
   - `run_output_audit`: add `metadata: dict[str, Any] | None = None` param;
     after Gate 3, `flags = flags + self._evaluate_envelope_allowlist
     (metadata)` before `_record_gate3_domain_traces(flags, gate3)`.
   Verify: `pytest tests/test_engine_envelope_allowlist.py -q` (new unit tests:
   AC-1.1 off-allowlist fires exactly one finding; AC-1.2 on-allowlist fires
   nothing and content evaluation unaffected; AC-1.3 determinism — same input
   twice = byte-identical finding; no `metadata` param = no-op, backward compat).
4. **Metadata threading (mechanical):** `services/audit_submission.py`
   `submit_audit_sync` — forward `metadata=metadata` into
   `engine_obj.run_output_audit(...)`. Verify: existing
   `tests/test_story406_bedrock_adapter.py::test_submit_audit_sync_persists_with_fake_engine`
   still passes (uses a fake engine — confirm it tolerates the new kwarg).
5. **STORY-407 E2E integration (tweak-likely, per AC-4.2):**
   `tests/test_story407_demo_corpus_builder.py`'s custom `submit` callback —
   pass `metadata=submission.metadata` into `run_output_audit`; update the
   E2E's fired-UC assertion from `{"UC-1", "UC-2", "UC-6"}` to `{"UC-1", "UC-2",
   "UC-5", "UC-6"}`, and UC-5's expected fired domain from `[]` to
   `["Governance & Compliance"]`. Confirm clean traffic still fires zero
   (primary_model_id is already allowlisted per recon — verify, don't assume).
   Verify: `pytest tests/test_story407_demo_corpus_builder.py -q`.
6. **Docs (mechanical, per AC-4.3):** `specs/stories/STORY-407.md`'s UC table +
   any demo-runbook "fires today" notes — update to 4 firing use cases.
7. **Guard cleanliness (mechanical, per AC-5.1):** confirm
   `rule_packs/envelope_loader.py` and the new engine code make zero external
   calls; `python -m grc.guards.external_model` stays green (rule_packs/ is
   likely already unscanned by the guard like adapters/ was pre-STORY-407 —
   confirm during BUILD, add to `PRODUCT_PACKAGE_DIRS` if not already covered
   and if that's the existing convention, matching STORY-407's Q4 precedent).
8. **Full gate suite (close):** ruff, mypy, pytest unit/integration/regression,
   quality ratchet, bandit — engineering-standards.md gates 1-7.

## Deviations
1. Adding a new `MIT_DOMAINS` entry (`"Governance & Compliance"`) broke two
   pre-existing tests that hardcoded assumptions about the domain count: a
   literal `assert len(gate3_traces) == 7` in `tests/test_new_features.py`
   (updated to 8 — every domain, including the new envelope-only one, gets a
   trace row whether "flagged" or "pass") and a missing
   `_MIT_DOMAIN_DEFINITIONS` entry caught by
   `tests/test_specs.py::test_llm_domain_definitions_defined` (added). Also
   added a matching `_REMEDIATIONS` entry (used by `_build_remediations`) for
   consistency with every other domain, though no AC strictly required it.
   `docs/metrics/detection-baseline.md` auto-regenerated (by
   `tests/test_fp_baseline.py`) with an `n/a` row for the new domain — correct,
   since it has zero content-scan fixtures (it's envelope-only by design).
2. **reviewer round 1 (REQUEST CHANGES) — blocker:** the `submit_audit_sync`
   metadata-forwarding fix (services/audit_submission.py) is itself a bug fix
   (metadata was silently dropped since STORY-406, per the engineering
   standards' "No bug fix without a regression test" rule) and shipped without
   an FND entry or pinning test. Fixed: filed an FND with a dedicated
   regression test (`tests/regression/test_fnd_050_submit_audit_sync_forwards_metadata.py`)
   that pins the forwarding independent of the envelope-allowlist feature (a
   fake engine capturing kwargs), plus `manifest.yaml`/`findings.md` entries.
   **Renumbering note:** originally filed as FND-048 (next-available off main's
   FND-047 baseline at branch time). STORY-410 (a parallel branch, also based
   off the same baseline) independently claimed FND-048/FND-049 for unrelated
   findings and merged to main first (PR #114). Resolved at rebase: renumbered
   to **FND-050** (ledger row, manifest entry, test filename) so both stories'
   findings coexist without collision.
3. **reviewer round 1 — minor:** stale docstring
   ("Classify each sample against the 7 MIT risk domains...") — fixed to not
   hardcode a count.
4. **reviewer round 1 — minor:** the YAML pack's comment described prefix
   matching with a misleading glob-style example (`"anthropic.claude-*"`) when
   the implementation is plain `str.startswith`, no wildcard support — fixed
   the wording so a future pack editor doesn't add a literal `*` character.
5. **reviewer round 1 — minor/accepted, no code change:** flagged
   `specs/stories/STORY-408.md`/`STORY-409.md` as scope beyond STORY-411's
   stated goals — confirmed intentional (filed in the same operator session
   per the stated SummitCare build sequence, markdown-only, no behavior
   change), same as the equivalent note on STORY-410.
6. **security-auditor — LOW, fixed:** `modelId`/`requestId` flowed into
   `AuditTrace.detail_json` (and `_SampleFlag.sample_id`) with no length cap,
   unlike prompt/output body text (`MAX_INLINE_BODY_CHARS` in
   `adapters/bedrock/parse.py`). Fixed: added `_MAX_ENVELOPE_FIELD_CHARS = 256`
   in engine.py, applied before storage in `_evaluate_envelope_allowlist`.
   Pinned by `test_oversized_model_id_and_request_id_are_truncated_before_storage`.
7. **security-auditor — INFO, accepted no action:** no dedicated
   tenant-isolation regression test for the envelope-derived `AuditTrace` path
   — low risk since it reuses the existing `tenant_id`-scoped `AuditTrace`
   query surface (no new query path introduced), confirmed by the auditor
   reading `routers/dashboard.py`'s existing tenant scoping. Recommended for a
   future doc/test addition, not required for this story.
