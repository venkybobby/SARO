# STORY-AISEC-002 — MITRE ATLAS evidence axis on findings + TRACE
Stage: standard

## Lifecycle
- [x] discover   (Gate-4 compliance-trigger mapping + injection-finding ATLAS IDs mapped)
- [ ] shape      (interview — crosswalk scope is the load-bearing, anti-guessing decision)
- [x] preview    (skipped — backend-only, no UI surface)
- [ ] plan
- [ ] build
- [ ] verify
- [ ] sell       (n/a)

## DISCOVER findings
- `_COMPLIANCE_TRIGGERS` (engine.py:309+) maps 7 MIT **harm** domains
  (Misinformation, Malicious Use, AI System Safety, Human-Computer Interaction,
  Socioeconomic & Environmental, Discrimination & Toxicity, Privacy & Security)
  → framework trigger dicts, each with a nullable `nist_subcategory_id`. The
  ATLAS axis is a parallel optional `atlas_technique_id` field.
- Stamped into TRACE via `_record_gate4_rule_traces`; surfaced in `AppliedRuleOut`.
- **Taxonomy tension (load-bearing):** ATLAS = adversarial *attacks on* ML
  systems; MIT domains = *harms from* AI outputs. Mostly orthogonal. Forcing
  harm-domain→attack-technique mappings = guessing (AC-1 forbids). The genuinely
  defensible ATLAS anchor is the AISEC-001 injection detector, which already
  emits real ATLAS IDs (AML.T0051/.001, AML.T0054).
- Branch base: stacked on `story/STORY-AISEC-001` (unmerged, CI-billing-blocked)
  because AISEC-002 AC-4 consumes AISEC-001's injection ATLAS IDs and both touch
  engine.py. Deviation from "branch from main" logged below.

## Premise check (Stage 3a)
| Referenced artifact | Verified? | File path |
|---|---|---|
| Finding→framework mapping | yes | `engine.py:309+` `_COMPLIANCE_TRIGGERS`, `_record_gate4_rule_traces` |
| nist_subcategory_id precedent | yes | `engine.py:316+` (nullable field per trigger) |
| Injection ATLAS IDs (AISEC-001) | yes | `rule_packs/injection/1.0.0/pack.yaml` (AML.T0051/.001/T0054) |
| AppliedRuleOut schema | pending | `schemas.py` — to confirm in DISCOVER-2 |
| ATLAS technique IDs are real | pending | verify via atlas.mitre.org (AC-3) |

## Decision Log
| Question | Answer | Architectural consequence |
|---|---|---|
| Crosswalk scope? | **Detector-anchored only** | ATLAS IDs flow only from the AISEC-001 injection detector (precise, per-rule). All 7 MIT compliance-domain triggers get the optional `atlas_technique_id` field but **null** everywhere — no domain-level guessing (strict AC-1). AISEC-002 value = verified registry + validation + Tier-3 surfacing of the injection findings' real ATLAS IDs. |
| Refine AISEC-001 system-prompt map? | **Yes → AML.T0056** | INJ-SECRET-DISCLOSURE remapped AML.T0051 → AML.T0056 "Extract LLM System Prompt" (more precise, verified). Touches the AISEC-001 pack on this stacked branch; pinned by an updated test. |

## Verified ATLAS registry (source: github.com/mitre-atlas/atlas-data, ATLAS.yaml)
| ID | Exact name |
|---|---|
| AML.T0051 | LLM Prompt Injection |
| AML.T0051.000 | Direct |
| AML.T0051.001 | Indirect |
| AML.T0054 | LLM Jailbreak |
| AML.T0056 | Extract LLM System Prompt |
| AML.T0024 | Exfiltration via AI Inference API |
| AML.T0057 | LLM Data Leakage |

## Plan (tweak-likelihood order)
1. **ATLAS registry data** `rule_packs/atlas/1.0.0/atlas_techniques.yaml` — 7
   verified IDs + exact names + version. Verify: load + hash test.
2. **Registry loader** `rule_packs/atlas/registry.py` — `load_atlas_registry()`,
   `.resolve(id) -> name|None`, `.is_valid(id)`, version + SHA-256. Verify: unit
   tests (AC-3).
3. **ATLAS axis on compliance triggers** (engine.py): add `atlas_technique_id:
   None` to every `_COMPLIANCE_TRIGGERS` entry (null — detector-anchored);
   `rule._atlas_technique_id = t.get("atlas_technique_id")` in
   `_gate4_compliance_mapping`; surface in `_record_gate4_rule_traces`
   detail_json (mirrors nist_subcategory_id exactly). Demonstrates AC-1
   "null when no mapping applies".
4. **Injection ATLAS surfacing** (engine `_scan_injection_impl`): name the ATLAS
   technique + resolved name in the trace reason/detail, Tier-3 ("indicators
   consistent with MITRE ATLAS {id} {name}"). Verify: AC-2/AC-4 integration test.
5. **Refine AISEC-001 pack**: INJ-SECRET-DISCLOSURE AML.T0051 → AML.T0056
   (verified more-precise). Verify: registry-membership test over the pack.
6. Tests `tests/test_aisec_002_atlas_axis.py` (AC-1..5 incl. Tier-3 forbidden-
   phrase); gates 1-7; reviewer + security-auditor (engine + rule_packs);
   index → IMPLEMENTED; traceability. Trusted refactoring: none.

## Compliance guardrails (enforced in code)
- Tier-3 only: no "ATLAS-compliant"/"certified"/verdict; evidence-shaped
  "indicators consistent with ATLAS {id}"; forbidden-phrase test (AC-5).
- Additive/backward-compatible: atlas field is optional, null where absent;
  existing TRACE consumers unaffected.
- No scoring change — descriptive metadata only.

## Review round 1 (reviewer + security-auditor agents)
- **reviewer: APPROVE.** All 5 invariants verified. Minors addressed:
  (1) subtechnique labels lost parent context → registry now stores fully-
  qualified names ("LLM Prompt Injection: Indirect"); test updated.
  (3) inconsistent None-registry access → `_record_gate4_rule_traces` now uses
  `getattr(self, "_atlas_registry", None)`. (2) "uncommitted delta" → committing now.
- **security-auditor: PASS.** No FAIL; ATLAS id is a trusted config constant
  (never attacker-derived), inert dict lookup, yaml.safe_load, PII path
  unchanged. INFO-1 (narrow except could let a malformed registry crash init)
  → broadened `except` to include TypeError/AttributeError/ValueError.

## Deviations
- Branch stacked on story/STORY-AISEC-001 (not main): AISEC-002 depends on
  AISEC-001 (AC-4) and both edit engine.py; predecessor is unmerged only because
  CI is billing-blocked. Conservative choice to avoid a same-file conflict.
