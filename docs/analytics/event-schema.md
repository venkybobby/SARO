# SARO Product Analytics — Event Schema

**Story:** STORY-381 · **Owner:** Venky · Written **before** any code emits an
event (AC-1), so the closed vocabulary is the contract, not an afterthought.

---

## The one rule: PHI-free by construction

A product-analytics event carries **only** a closed-vocabulary event name, a
tenant id, a timestamp, and closed-vocabulary property tags of bounded scalars.
**There is no free-text field.** Payload content, prompt/output text, patient
information, and email addresses cannot enter an event because there is nowhere
to put them — the same INV-2-by-construction discipline as usage metering, not a
redaction step that can be forgotten.

This is enforced in `services/product_analytics.py`: an unknown event name or
property key is rejected, and a property value that is not a bounded scalar (or
exceeds the length cap) is rejected. A caller cannot smuggle content in.

## Capture is first-party

Events are written to the `product_events` table in SARO's own Supabase — no
third-party analytics SaaS. A hosted analytics vendor would be a **security-review
question** (Epic 15: it becomes a sub-processor with access to usage data) and is
**not adopted without owner sign-off**. Self-hosted keeps the analytics data
inside the same trust boundary as everything else.

---

## Event vocabulary (closed)

| Event name | Fires when | Funnel it serves |
|---|---|---|
| `login` | A user authenticates successfully | entry to every funnel |
| `attestation_viewed` | A user opens a TRACE / attestation record | login → view attestation |
| `rule_pack_subscribed` | A tenant pins a rule-pack version | subscribe → first evaluation |
| `first_evaluation` | A tenant's **first** evaluation in a period | subscribe → first evaluation |
| `compliance_hub_artifact_viewed` | A Compliance Hub artifact is opened | artifact adoption |

Adding an event means adding it to this table **and** to `EVENT_NAMES` in the
service. An unlisted name is rejected — the vocabulary cannot grow by accident.

## Property vocabulary (closed)

Property **keys** are limited to this allowlist; **values** are bounded scalars
(string ≤ 64 chars, int, or bool). No key or value may carry content.

| Property key | Meaning | Example values |
|---|---|---|
| `persona` | The acting persona role | `compliance_lead`, `risk_officer`, `ai_auditor` |
| `surface` | Which UI/API surface | `web`, `api`, `cli` |
| `artifact_type` | For hub-artifact views | `dpa`, `soc2_roadmap`, `ir_plan` |
| `adapter_id` | For evaluation events | `bedrock-invocation-log`, `azure-openai-diagnostic-log` |
| `outcome` | Coarse result class | `success`, `failure` |

**Explicitly forbidden by construction** (no key exists for them): user email,
user id as a value, prompt/output text, any free-text field, any patient
identifier. The tenant id is a column, not a property, and is the only
identifier stored.

---

## What is NOT captured

- **No PHI, ever** — there is no field it could occupy.
- **No individual user identity in the event body** — a tenant id scopes the
  event; who within the tenant did it is not an analytics concern and is not
  stored here. (Security-relevant actor tracking is the audit trail's job,
  STORY-366/FND-065, behind authorization — a different system with a different
  access model.)
- **No cross-tenant aggregation exposed** — the table is tenant-scoped by RLS
  (migration 040); the founder's internal query set aggregates across tenants,
  but that runs with operator authority, not through a tenant-facing surface.

---

## Retention & disclosure (AC-5)

Product-analytics collection is disclosed in the data-retention documentation
(`docs/sample-evidence-retention.md`) and the DPA template
(`docs/legal/saro-dpa-template-v1.0.md`), so a customer's privacy review sees it.
Because events carry no personal data by construction, they are not "personal
data" under the DPA — but the collection is disclosed regardless, because
"we told you" beats "you found out".
