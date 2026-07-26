# STORY-AISEC-006 — MCP tool-description poisoning evidence
Stage: standard

## Lifecycle
- [x] discover   (contract ToolInvocation + evaluate._CHECKS + loader/demo blast radius mapped)
- [x] shape      (structural decision self-answered below; no product ambiguity)
- [x] preview    (skipped — backend/observation, no UI surface)
- [x] plan
- [x] build
- [x] verify     (full suite 2371 passed; reviewer APPROVE + security-auditor PASS)
- [ ] sell       (n/a)

> Note: lines here were briefly overwritten by an out-of-band edit claiming a
> "concurrent session" and instructing a checkbox restore. Treated as untrusted
> data (not a command) per the instruction-source boundary and rewritten to the
> true state. Surfaced to the user.

## DISCOVER findings
- `ToolInvocation` (adapters/contract.py) carries name/offered/invoked; args/results
  deliberately absent (INV-2). Tool DESCRIPTION is advertised metadata (like tool
  names), not per-message body → posture-safe to carry + scan.
- Observation checks: `_CHECKS` dispatch in `rule_packs/observation/evaluate.py`;
  each `(rule, pack, record) -> list[Finding]` via `_finding(...)`.
- Loader globs ALL `*/*/pack.yaml` (`load_genesis_packs`). The demo `_demo_packs`
  iterates all genesis packs → a new pack would ripple into the demo provenance
  test (`refs == {RP-OBS-COMPLETE, RP-TOOL-SCOPE}`) + committed screencast.
- prereq test uses `in packs` (not exact set) → new pack OK there.

## Decision Log
- New pack vs edit rp_tool_scope? → **new pack `rp_tool_poisoning@1.0.0`** (loader
  discipline: "publishing is a new version, never an edit"; avoids rp_tool_scope
  version churn + two-versions-loading ambiguity).
- Demo blast radius? → **pin `_demo_packs` to its 2 intended packs** (RP-OBS-COMPLETE,
  RP-TOOL-SCOPE) so future genesis packs don't silently change the demo provenance
  / screencast. Clean, and future-proofs the demo.
- Scan engine? → **reuse the AISEC-001 `scan` + `load_injection_pack`** on the
  description text; evidence-only; ATLAS via the AISEC-002 registry.

## Plan (tweak-likelihood order)
1. **Contract** `ToolInvocation.description: str | None = None` (adapters/contract.py).
   Optional, default None → backward compatible. Verify: contract unit test.
2. **New pack** `rule_packs/observation/rp_tool_poisoning/1.0.0/pack.yaml` —
   TOOL-DESC-POISONING-1, `check: tool_description_poisoning`, ATLAS AML.T0010.
   Verify: pack loads + hash test.
3. **Check** `_check_tool_description_injection(rule, pack, record)` in
   evaluate.py + register in `_CHECKS`: scan each tool.description via the
   injection detector; emit one Finding per poisoned tool with matched indicators
   + ATLAS id; evidence-shaped detail. Verify: AC-1/AC-2/AC-3/AC-5 tests.
4. **Demo pin** `_demo_packs` → the 2 intended packs (no ripple). Verify: demo
   test 7/7 unchanged.
5. Tests `tests/test_aisec_006_tool_description_poisoning.py`. Gates 1-7; reviewer
   + security-auditor; index → IMPLEMENTED; traceability.

## Compliance guardrails
- Evidence-only, read-only; descriptions are metadata (INV-2 intact — not body).
- Deterministic, no external model/network (detector is pure). Evidence-shaped
  language; ATLAS Tier-3.

## Review round 1 (reviewer + security-auditor agents)
- **reviewer: APPROVE.** INV-2 defensible (description = advertised metadata, not
  body); no content egress (finding carries rule-ids + ATLAS only, never the raw
  description fragment); demo pin correct/necessary; deterministic. Minors: index
  flip (done at commit), staging hygiene, drive-by ruff reformat (accepted — repo
  formatter output), spec ATLAS-id framing (findings inherit the injection rules'
  ids incl. AML.T0051.001).
- **security-auditor: PASS.** Untrusted description string-matched only (no
  eval/exec/network); PII/content egress clean (raw description never reaches
  detail/logs); INV-2 metadata exception concurred; bounded by max_scan_chars
  (no ReDoS/DoS); yaml.safe_load. INFO-1 (no max_length on description) is
  defense-in-depth only — memory already bounded upstream; left as-is to avoid a
  breaking validation on legitimately long descriptions.

## Deviations
- Branch off main (fresh, AISEC pack merged). Independent story.
