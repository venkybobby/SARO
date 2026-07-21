# Rule-Pack Authoring & Update Guide

**Story:** STORY-376 · For customer compliance leads authoring or updating
rule-packs. Companion: [COMPLIANCE_CLAIMS_MATRIX.md](COMPLIANCE_CLAIMS_MATRIX.md)

---

## The lifecycle: draft → validate → publish

```
  draft            validation             published
(editable)   →   (fit-to-publish?)   →   (immutable snapshot)
```

### 1. Draft

A draft is the working copy — rules you can edit. New and edited rules carry a
`validation_status`; until a rule is reviewed it is `DRAFT_UNVALIDATED`.

### 2. Validate

Validation reports whether the working copy is **fit to publish**, without
freezing anything:

- **Structural readiness** — any `DRAFT_UNVALIDATED` or status-less row *blocks*
  a publish and is listed, so you know exactly what to review. Framework counts
  show what the published version would contain.
- **False-positive / false-negative validation** — **not yet available.** This
  requires the completion bar (**STORY-377**, awaiting product sign-off) and the
  confusion-matrix harness (**STORY-378**, not yet built). Validation reports the
  FP/FN verdict as `bar_pending:STORY-377` and **does not** present a pass. When
  those land, this stage will run the candidate pack against the labeled corpus
  and report real rates.

This distinction is deliberate: a validation stage that returned "looks good"
without measuring FP/FN would be telling you something it cannot know.

### 3. Publish

Publishing freezes the working copy into an **immutable, hash-chained snapshot**
(INV-7). A published version:

- **cannot be edited or deleted** — enforced by a database trigger and the
  service layer;
- gets a SemVer and a content hash that every attestation produced under it
  records, so any past result stays exactly reproducible;
- is refused if any draft row would be included, or if the content is identical
  to the latest published version (no empty versions).

**Updates are new versions, never edits.** To change a published pack, edit the
working copy and publish a new version.

---

## Subscribing, deprecation, and rollback

A tenant **pins** a published version. That pin decides which rules evaluate the
tenant's evidence.

- **Deprecation and rollback are re-pinning, never deletion.** Moving a tenant
  off a version leaves that version — and every attestation produced under it —
  intact and reproducible. **Published packs are never deleted.**
- A tenant with no pin uses the platform's latest published version.
- Pinning to a version that was never published is refused: a pin must reference
  a snapshot that exists, or its attestations could not be reproduced.
- Every pin change is recorded in the audit trail (`RULE_PACK_CHANGE`), because
  changing a tenant's version changes which rules judge its evidence.

---

## Authoring interface

The API path exists (`POST /api/v1/rules/versions` to publish; pinning via the
lifecycle service). A dedicated authoring **UI** is deferred pending screen
review — this guide covers the model and the API in the meantime.
