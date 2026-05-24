# Command: /saro:compliance-check

Run a compliance alignment check against SARO's locked regulatory scope for any feature, document, or code change.

## Usage

```
/saro:compliance-check [feature or document description]
```

Example: `/saro:compliance-check "new audit trail endpoint for model decisions"`

## What This Command Does

1. Maps the input to SARO's compliance engines (Drift Sentinel, SEC Proof, eKYC Shield, Fairness/SHAP)
2. Checks alignment against locked scopes:
   - NIST AI RMF 1.0 (GOVERN, MAP, MEASURE, MANAGE)
   - EU AI Act Articles 9, 13, 17 **only**
   - ISO 42001 (document lifecycle linking only)
   - AIGP (principles evaluation only)
3. Flags any scope creep — claims beyond locked boundaries
4. Checks the three critical pre-external-sharing gates:
   - [ ] Incident Response Plan complete?
   - [ ] External Compliance SME review complete?
   - [ ] Data Retention / DPA Policy complete?
5. Checks TRACE view readiness if applicable

## Output Format

```
COMPLIANCE CHECK REPORT
========================
Feature: [name]
Date: [date]

NIST AI RMF Alignment:
  GOVERN: [covered / not applicable / gap]
  MAP: [covered / not applicable / gap]
  MEASURE: [covered / not applicable / gap]
  MANAGE: [covered / not applicable / gap]

EU AI Act (Articles 9, 13, 17 only):
  Article 9 (Risk Mgmt): [covered / not applicable / gap]
  Article 13 (Transparency): [covered / not applicable / gap]
  Article 17 (Quality Mgmt): [covered / not applicable / gap]
  Out-of-scope claims detected: [YES — list them / NONE]

ISO 42001: [document lifecycle link present / not applicable / gap]
AIGP: [principles-level only / overreach detected]

CRITICAL GATES:
  Incident Response Plan: [complete / OPEN ⚠️]
  SME Review: [complete / OPEN ⚠️]
  DPA Policy: [complete / OPEN ⚠️]

TRACE View: [not touched / Alex's doc required ⚠️]

VERDICT: [CLEAR TO PROCEED / BLOCKED — list reasons]
```
