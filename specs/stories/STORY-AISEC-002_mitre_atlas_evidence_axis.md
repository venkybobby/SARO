# STORY-AISEC-002: MITRE ATLAS evidence axis on findings + TRACE

**Status:** draft
**Screen/Area:** Scoring engine (finding→framework mapping) / TRACE export / reports

## Source & attribution
Crosswalk seeded from the Apache-2.0 `mukul975/Anthropic-Cybersecurity-Skills`
ATLAS mappings (e.g. `AML.T0051.001` indirect injection, `AML.T0054` jailbreak,
`AML.T0024` model extraction, `AML.T0053` plugin compromise). **Every mapping is
re-verified against upstream MITRE ATLAS** before use — see caveat below.

## Premise verification (FM-2 — verified before authoring)
| Referenced artifact | Verified? | File path / note |
|---|---|---|
| Finding→framework stamping | yes | `engine.py:303+` stamps `nist_subcategory_id` into AuditTrace `detail_json` |
| NIST AI RMF mapping table | yes | `rule_packs/nist_rmf_v1.0.yaml`, `rule_packs/nist-ai-rmf/` |
| TRACE export carries provenance | yes | `docs/ARCHITECTURE.md` — `GET /api/v1/trace/{id}/export` embeds engine/rule-pack metadata |
| Claims-matrix boundary | yes | `docs/COMPLIANCE_CLAIMS_MATRIX.md` (evidence-only, Tier-3 today) |
| Upstream ATLAS IDs | PREMISE-UNVERIFIED at upstream | community frontmatter stores ATLAS under mixed keys and files AI-RMF codes under a `nist_csf:` key — **do not trust; re-verify each ID against atlas.mitre.org before adopting** |

## Goal
Add MITRE ATLAS (the AI/ML adversary framework) as a **second evidence axis**
alongside the NIST AI RMF subcategory SARO already stamps on findings, so a TRACE
finding can say *which adversarial technique* the indicator is consistent with
(e.g. `AML.T0051.001`) in addition to *which risk-management subcategory* it
supports. This is an evidence-enrichment change only — no new scoring math and no
new compliance claim.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given a finding that today carries `nist_subcategory_id`, When it is
  produced, Then it MAY also carry an optional `atlas_technique_id` from a
  verified crosswalk, and the field is null when no mapping applies (never guessed).
- AC-2: Given a TRACE export, When rendered, Then any present `atlas_technique_id`
  appears with evidence-shaped language ("indicators consistent with ATLAS
  {id}") — never "ATLAS-compliant" / "certified" / a verdict.
- AC-3: Given the crosswalk table, When loaded, Then every ATLAS ID resolves to a
  real technique (validated in a test against a pinned ATLAS ID list), mirroring
  the existing NIST subcategory-count reconciliation discipline (STORY-104).
- AC-4: Given the injection detector from STORY-AISEC-001, When it fires, Then its
  findings map to `AML.T0051.001` (indirect) / `AML.T0054` (jailbreak) as
  appropriate.
- AC-5: Given external-facing report copy, When ATLAS is referenced, Then it stays
  Tier-3 (no framework-conformance claim), enforced by a forbidden-phrase test.

## Edge Cases
- A finding with a NIST mapping but no defensible ATLAS technique → `null`, not a
  forced/approximate ID.
- ATLAS revises/renames a technique → crosswalk is versioned; the validation test
  catches a now-invalid ID (same failure mode STORY-104 guards for NIST).

## Out of Scope
- Claiming ATLAS coverage/conformance anywhere (Tier-3 until EVF/QCO says otherwise).
- Re-scoring or changing risk numbers — mapping is descriptive metadata only.
- D3FEND / ATT&CK / F3 axes — separate stories if ever justified.

## Non-Functional Requirements
- Additive, backward-compatible: existing TRACE consumers that ignore the new
  field keep working; the field is optional in the schema.
- compliance-guard skill constraints hold; security-auditor reviews export copy.

## Benefits
- **Auditor-ready specificity:** "indicators consistent with ATLAS AML.T0051.001"
  is far more actionable for a security reviewer than a risk score alone — it
  names the adversary technique, closing the gap between SARO's risk output and a
  SOC's threat vocabulary.
- **Fills a real framework gap:** SARO already speaks NIST AI RMF; ATLAS is the
  AI-specific *adversary* framework it does not yet map — this is net-new evidence
  coverage no competitor mapping-to-RMF-only provides.
- **Low risk, high leverage:** additive metadata on an existing pipeline; no
  scoring change, no posture change, reuses the exact mechanism already proven for
  NIST subcategories.
- **Sales-safe:** stays inside the claims matrix (Tier-3), so it strengthens the
  evidence story without creating an overclaim liability.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
