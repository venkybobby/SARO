STORY-017: Niche Demo Narrative and Pilot Collateral (S-1205)
Status: ready    Screen/Area: Demo / GTM Collateral

Goal
Reposition the demo to the winnable niche — independent auditing of third-party vendor AI outputs for mid-market regulated buyers — with defined pilot scope. Depends on STORY-007 badges. Closes FB-033/044.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the demo script, When it is rewritten, Then it leads with the Compliance Lead journey auditing third-party vendor AI outputs, and the persona journey E2E suite remains green
AC-2: Given docs/pilot-one-pager.md, When it is created, Then it defines pilot scope as one business unit and a maximum of 25 models, with exit criteria
AC-3: Given every compliance statement in the script and demo tenant copy, When the FR-EVF-16 language audit runs, Then only Tier-1 or Tier-2 approved language appears and the audit record is filed
AC-4: Given the demo flow, When framework claims render, Then QCO badges from STORY-007 are visible

Edge Cases
- If no QCO is published yet at demo time, all badges must read 'Internal Review Only' — never hide the badge.
- Pilot one-pager must not promise SOC 2 or pen-test artifacts (deferred items).

Out of Scope
- Website or marketing assets.
- Pricing.

Non-Functional Requirements
Prohibited-words lint applies to script and tenant copy. Demo data uses the seeded demo tenant only.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
