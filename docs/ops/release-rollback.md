# Release & Rollback Procedure

**Story:** STORY-375 · **Owner:** Venky · Companion:
[../../CHANGELOG.md](../../CHANGELOG.md) · [runbooks.md](runbooks.md) A1

---

## 1. Versioning

SemVer, single source in [`_version.py`](../../_version.py). Everything that
reports a version reads from there — the FastAPI app, `/health`,
`GET /api/v1/version`, and the UI footer. **Never re-hardcode a version**; a
duplicated string drifts, and a drifted version on a status page tells a
customer's change-management process something false.

- **MAJOR** — a breaking API or contract change (a customer must act).
- **MINOR** — new capability, backward compatible.
- **PATCH** — fixes, no contract change.

## 2. Cutting a release

1. Bump `_version.py`.
2. Move the `## [Unreleased]` entries under a new `## [x.y.z] — <date>` heading
   in `CHANGELOG.md`, curating them into user-facing language.
3. Open a PR labelled `release:` (or titled `release: …`). The **changelog gate**
   (`scripts/check_changelog_entry.py`, enforced in `release.yml`) fails the PR
   if it adds no curated entry.
4. Merge, then tag the merge commit: `git tag v<x.y.z> && git push origin v<x.y.z>`.
5. The tag triggers `release.yml`: it verifies the tag matches `_version.py` and
   that CHANGELOG has a section for it, runs the **conformance suite** and the
   **full test suite**, then deploy (`deploy.yml`) and the **post-deploy canary**
   (`canary.yml`) confirm the release end to end.

A tag whose version does not match `_version.py`, or that has no CHANGELOG
section, fails before deploying — the version cannot be ambiguous at release.

## 3. Rollback

Fly keeps prior releases, so rollback is redeploying a known-good image — not a
code revert under pressure.

```bash
fly releases -a saro-backend           # find the last-known-good version
fly deploy --image <prior-image> -a saro-backend   # or: fly releases rollback
curl -s https://saro-backend.fly.dev/health | jq   # confirm status + schema_ok
curl -s https://saro-backend.fly.dev/api/v1/version # confirm the version rolled back
```

### The migration caveat — read before rolling back

A rollback rolls back **code, not schema**. If the release you are rolling back
from applied a migration, the database is now ahead of the older image.

- **Additive migration** (new nullable column/table): the older code ignores it.
  Safe to roll back.
- **Destructive or contract-changing migration** (dropped/renamed column, a
  backfill the new code depends on): rolling back the code alone can leave the
  old code reading a schema it does not expect. **Do not roll back blindly** —
  either roll the schema back too (from a backup, per
  [dr-backup.md](dr-backup.md)) or fix forward.

`/health` returning `schema_mismatch` after a rollback is the signal that code
and schema disagree (runbooks.md A3).

## 4. Rehearsal — [HUMAN — OPEN]

The rollback must be **rehearsed once on a scratch deploy** before it is relied
on — a procedure that has never been run is a hypothesis. This needs Fly access
and a scratch app, so it is an operator action:

- [ ] Deploy a throwaway version to a scratch Fly app.
- [ ] Roll it back to the prior release using §3.
- [ ] Confirm `/health` and `/api/v1/version` report the rolled-back version.
- [ ] Record the timing here and any surprises.

Until this box is ticked, §3 is documented but unproven.
