# SARO Pilot — One-Pager

> **Niche:** independent auditing of **third-party vendor AI outputs** for mid-market,
> regulated buyers. Led by the **Compliance Lead** persona. (FB-033, FB-044 / S-1205)

---

## The problem we solve

Mid-market regulated firms increasingly buy AI-powered tools from vendors (chat assistants,
underwriting models, clinical summarisers). They are accountable for those outputs but have **no
independent, evidence-based way to audit them** — vendor self-attestations are not enough for an
internal risk function or an external examiner.

## What SARO does in the pilot

Paste or stream a vendor AI **output** (plus the prompt that produced it). SARO runs its 4-gate
pipeline and returns, in seconds:

- a 0–100 **risk score** with a TRACE timeline (Ingest → Classify → Match → Score → Explain → Remediate),
- **evidence mapping** to NIST AI RMF, EU AI Act, AIGP, and ISO 42001 criteria (evidence support only),
- **remediation guidance** for a human reviewer.

SARO is read-only: it never writes to vendor or customer systems, never generates the audited
output, and never certifies compliance — it produces evidence for a human sign-off.

## Pilot scope (deliberately bounded)

| Dimension | Pilot boundary |
|---|---|
| Business units | **One** business unit |
| AI models / vendor tools in scope | **Maximum 25** |
| Lead persona | Compliance Lead (Risk Officer + AI Auditor support) |
| Duration | 6–8 weeks |
| Frameworks | Evidence support only; labels shown at the QCO/validation tier they have earned |

Out of scope for the pilot: org-wide rollout, model-lifecycle / pre-deployment coverage,
writing back to any system, and any external compliance certification.

## Success criteria

- The Compliance Lead can audit a vendor output end-to-end and export a TRACE evidence pack
  for human review.
- At least one real vendor tool's outputs audited across the pilot window with reproducible,
  sample-level findings (provenance-stamped).
- Compliance/risk stakeholders agree the evidence is decision-useful for their internal review.

## What the buyer provides

- One business unit sponsor (Compliance Lead) and up to 25 in-scope vendor tools/models.
- Representative prompt + output samples (or a feed) for those tools.
- A named human reviewer to validate findings (SARO is human-in-the-loop by design).

## Boundaries (non-negotiable)

SARO accepts only `prompt` + `raw_output`; returns only a risk score, TRACE timeline, and
remediation guidance; never writes to client systems; never certifies compliance; always keeps a
human in the loop. Framework references appear only at the validation tier they have earned
(FR-EVF-16); no Tier-3 language is used in pilot collateral.

---

*This one-pager is sales/pilot collateral. It does not constitute regulatory certification or
legal advice; compliance sign-off requires qualified human review.*
