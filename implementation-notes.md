# CVE remediation: starlette / setuptools-vendored wheel & jaraco.context
Stage: standard

## Lifecycle
- [x] discover   (root-caused all 3 findings via actual Docker builds, not guesswork —
      see Decision Log)
- [x] shape      (skipped — user directed: "scope + fix the CVEs now")
- [ ] preview    (skipped — backend/dependency only, no UI)
- [x] plan       (see below)
- [x] build
- [x] verify     (see below)
- [ ] sell — n/a

## Decision Log

**Q: Are wheel/jaraco.context real SARO dependencies?**
A: No. Confirmed via `docker build --target builder` + `find` inside the built image:
both live at `/usr/local/lib/python3.11/site-packages/setuptools/_vendor/` — vendored
copies bundled inside `setuptools==79.0.1` itself (base image default), never imported
by SARO code, not reachable via requirements.txt at all.
Consequence: fix by bumping `setuptools` in the Dockerfile builder stage, not
requirements.txt. Verified `pip install setuptools>=80` (resolves 83.0.0) vendors
wheel-0.46.3 (fixes CVE-2026-24049, needs >=0.46.2) and jaraco_context-6.1.0 (fixes
CVE-2026-23949, needs >=6.1.0). Zero app-code risk — internal to setuptools' own build
tooling.

**Q: Can starlette be bumped without touching fastapi?**
A: No. `fastapi==0.129.0` requires `starlette<1.0.0,>=0.40.0` (checked METADATA), and
0.52.1 is starlette's last 0.x release (`git ls-remote --tags` — no 0.53+ exists). Both
CVE fixes (CVE-2026-48818 in 1.1.0, CVE-2026-54283 in 1.3.1) only exist in the 1.x line.
Checked fastapi's own METADATA across versions: the `<1.0.0` ceiling on starlette is
dropped starting at fastapi 0.135.0. So fixing starlette requires bumping fastapi too.

**Q: Is a fastapi/starlette major bump safe given FND-069?**
A: Unverified until tested — this is the real risk. FND-069 (commits 2f10180, 564dacf)
found that different Starlette versions nest vs. flatten `include_router`-registered
routes in `app.routes`, which broke route-count assertions in CI when fastapi/starlette
were unpinned. `tests/regression/test_fnd_069_route_enumeration_nesting.py` and the
route-count sanity check in the real-app tests are the tripwire for this regression.
Plan: bump to latest fastapi (0.141.1) + starlette (1.3.1), run that regression test
+ the full suite before touching anything else. If it fails, do NOT force it — stop,
report, and fall back to a waiver (matching the existing ecdsa precedent in
security/scan-waivers.md) rather than shipping a broken route table.

## Plan

1. Dockerfile: add explicit `setuptools` upgrade to the existing
   `pip install --upgrade pip` line in the builder stage.
2. requirements.txt: bump `fastapi==0.129.0` -> `0.141.1`, `starlette==0.52.1` -> `1.3.1`.
3. Build the real Docker image, verify vendored wheel/jaraco.context versions.
4. Install the bumped fastapi/starlette in a clean venv matching Python 3.11; run
   `pytest tests/regression/test_fnd_069_route_enumeration_nesting.py` and the
   real-app route-count test FIRST, before the full suite (fast fail on the known
   risk).
5. If that passes: run `pytest tests/ -q` (full suite), `ruff check .`, `mypy .`.
6. Independent security-auditor review on the diff before merge.
7. Push to chore/phase1-cleanup-repo-hygiene, confirm Trivy + pip-audit go green
   in CI, merge.

## Deviations

1. **starlette NOT bumped — waived instead.** Plan said "bump fastapi/starlette,
   test, and only fall back to a waiver if the regression test fails." The
   regression test failed (see Decision Log) — `main.app` route count collapsed
   to 2 with fastapi==0.141.1/starlette==1.3.1, even through the version-
   independent recursive helper. Conservative option taken: revert to the
   validated FND-069 pins (fastapi==0.129.0/starlette==0.52.1), add a waiver
   documenting the blocked fix path and an expiry (2026-09-15) for re-triage.
   Aggressive option not taken: force the bump and patch `iter_api_routes()` to
   handle the new nesting shape blind, without understanding it — too large and
   too risky to do inside a CVE-remediation task; needs its own investigation.

2. **Discovered mid-task: Trivy had zero waiver enforcement.** `security/
   scan-waivers.md`'s own docstring says it's "the single source of
   suppressions," but `scripts/check_scan_waivers.py --pip-args` only fed
   pip-audit — Trivy's step in security-scans.yml had no ignore mechanism
   wired up at all, so the starlette waiver would have silenced pip-audit
   while Trivy kept gate-failing on the same accepted risk. Extended the
   script (prefix-routed: PYSEC-*/GHSA-* -> pip-audit, CVE-* -> Trivy
   ignorefile) and wired `--trivyignore` into the workflow. Added
   tests/test_check_scan_waivers.py (3 tests) since the script had zero
   coverage before this.

3. **Discovered mid-task: no .dockerignore existed.** `COPY . /app` in
   Dockerfile stage 2 was shipping the whole repo into the production image —
   confirmed 4 separate node_modules trees (frontend/, demo-capture/ ~63MB
   Playwright, scripts/, docs/evf/) landing in the shipped container. This is
   what Trivy's node-pkg findings (brace-expansion, js-yaml) were actually
   scanning. Verified via `grep` that main.py doesn't serve/import any of
   those paths (frontend is a separate Fly.io app per docs/ARCHITECTURE.md).
   Added .dockerignore. Conservative scope: excluded confirmed-safe items
   (node_modules anywhere, .git, caches, env files) rather than excluding
   whole directories (frontend/, docs/, scripts/) I hadn't fully verified
   were runtime-safe to drop.

4. **setuptools fix needed two attempts.** First attempt installed the
   `setuptools>=80` upgrade into the builder stage's own site-packages
   (no --prefix=/install), so it never reached the final image via
   `COPY --from=builder /install /usr/local` — verified broken via `docker
   run ... pip show setuptools` (still 79.0.1). Second attempt tried
   `--prefix=/install` for setuptools too, which cross-stage-merged a new
   setuptools over the base image's existing one via COPY, leaving old and
   new `_vendor/` dist-info directories coexisting and `pip show` still
   reporting 79.0.1 — a raw file copy doesn't do what a real `pip install
   --upgrade` does. Final fix: run the upgrade directly in stage 2 after
   `COPY --from=builder`, so it's a real upgrade against the image's actual
   installed state. Verified clean via `docker run ... find` (single set of
   vendored dist-info dirs, `pip show setuptools` reports 83.0.0).

## Verification

- `docker build -f Dockerfile .` — clean build, no cache reuse (`--no-cache`)
- `docker run saro-backend:scan ... find` — confirms setuptools 83.0.0, single
  set of vendored wheel-0.46.3/jaraco_context-6.1.0 dist-info, zero node_modules
- Local Trivy scan (`aquasec/trivy:latest image ... --ignorefile .trivyignore`)
  against the corrected image — exit code 0, zero findings (Python + Node.js)
- `pip-audit -r requirements.txt --skip-editable $(check_scan_waivers.py
  --pip-args)` — "No known vulnerabilities found, 8 ignored"
- `pytest tests/ -q` — 2423 passed, 26 skipped, 0 failed (fastapi/starlette
  reverted to the validated FND-069 pins, so this is the known-good baseline)
- `pytest tests/regression/test_fnd_069_route_enumeration_nesting.py` — 4/4
  passed against the reverted pins (confirms revert didn't regress anything)
- `pytest tests/test_check_scan_waivers.py` — 3/3 passed (new coverage)
- `pytest tests/test_pt005_doc_register.py` — 6/6 passed
- `ruff check` + `mypy` on all touched files — clean
- `docker run saro-backend:scan python -c "import main; ..."` — 210 top-level
  routes (consistent with the FND-069 >50 threshold; app imports cleanly)

## Security-auditor review

Independent review (fresh context, diff-only) found 5/6 areas correct as-is,
one blocking gap: the starlette waiver rows explained why the fastapi/starlette
bump is blocked, but not why running with the CVE exposure is acceptable right
now — unlike the existing ecdsa waiver, which states its acceptable-exposure
reasoning explicitly. Reviewer independently verified via grep (no StaticFiles
mount, no form/multipart-handling endpoints) that both CVEs are actually
unreachable in SARO's current attack surface, and asked for that written into
the waiver file rather than left to a future re-derivation.

Fix applied: added the exposure-check sentence (StaticFiles/UploadFile/form/
multipart grep, zero matches, re-verify at renewal) to all 7 starlette waiver
rows. Independently re-verified the grep myself before writing it in — same
zero-match result.

Applying that fix surfaced a real, unrelated bug the reviewer had flagged as a
"minor fragility": `ROW_RE` in check_scan_waivers.py splits table rows on `|`
with no escaping, and my first draft of the exposure text used a literal `|`
inside an inline `grep "A\|B\|C"` regex example — which silently broke that
row's parsing (dropped from 8 active waivers to 7, `--pip-args` silently
stopped emitting `--ignore-vuln PYSEC-2026-161`). Caught by re-running
`check_scan_waivers.py` and the test suite after the edit, not by inspection.
Fixed by rephrasing the exposure text to avoid literal pipe characters.
Confirms the reviewer's fail-closed assessment was right (a broken row drops
the waiver, so the scanner re-gates rather than silently over-suppressing),
but also that it's a real gap worth a follow-up (flagged, not fixed here —
already-scoped-large task; a real fix means teaching the parser about
backtick-code-span escaping or moving reasons out of the pipe-delimited
table).
