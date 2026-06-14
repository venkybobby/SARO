# Source-Code Escrow Agreement — Terms of Record

> **Status:** v1.0 · CANONICAL (terms; counter-signature pending) · Owner: Venky (Lead) · 2026-06-12
> PT-012 AC-2 (Deal Condition #6). Defines the escrow terms referenceable in the MSA. The executed,
> counter-signed agreement is filed under `docs/legal/` once signed; this document holds the terms.

## Parties

- **Depositor:** SARO (vendor).
- **Beneficiary:** Enterprise customer (per MSA exhibit).
- **Escrow agent:** Independent third-party escrow provider (e.g., Iron Mountain / NCC Group / Escrow4all) — named in the executed agreement.

## Deposit

| Item | Detail |
|---|---|
| Material | Full SARO source repository (this repo) + deployment configuration (`fly.toml`, migrations) |
| Cadence | On a defined cadence — **monthly**, plus on each tagged release |
| Integrity | Each deposit is SHA-256 hashed; the hash manifest is verified by the agent on receipt |
| Exclusions | Customer data, production secrets/API keys, and training data are **never** deposited |

## Release conditions (objective, non-discretionary)

Escrowed material is released to the beneficiary only upon a verifiable, objective trigger:

1. Depositor bankruptcy or insolvency / cessation of business.
2. Material breach of the MSA support obligations uncured for 30 days after written notice.
3. A production outage unremediated for **30 continuous days** with no remediation plan.
4. Failure to maintain the service such that the beneficiary cannot operate, uncured for 30 days.

Disputes over a release condition are resolved by the escrow agent against the **objective** criteria
above — never by depositor or beneficiary discretion alone.

## Verification

- The beneficiary may request, up to twice per year, an agent-supervised verification that the
  deposited material builds and deploys per `VENDOR_CONTINUITY_PLAN.md` §4.
- The deposit hash manifest is auditable.

## MSA reference

This agreement is incorporated by reference into the MSA as the Source-Code Escrow Exhibit. The
continuity obligations it supports are described in `VENDOR_CONTINUITY_PLAN.md`.
