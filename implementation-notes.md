# Make main CI green — layered failures (mypy + test-isolation + anything deeper)
Stage: standard

main has been red since before the Epic 14-19 pack merged (9b7a9e7); failures
were stacked, each masking the next. Layer 1 (story-index shallow-clone, ruff
F401, gitleaks test-data) fixed in 317b306. This task clears Layer 2 and any
further layers until CI is actually green.

## Lifecycle
- [x] discover  (CI log forensics done — root causes below)
- [x] shape     (fix set is specified, not exploratory)
- [ ] preview   (skipped — no user-facing surface)
- [x] plan
- [x] build     (mypy: `mypy .` green on 398 files; FND-069 root cause found —
                 NOT test pollution but Starlette version-dependent route
                 nesting; fixed with a recursive enumerator + regression test)
- [x] verify    (skipped change-debrief.html — this is CI-hygiene/type/test
                 remediation with no user-facing surface. Verification is the
                 green gate set: mypy 398 ok, ruff ok, ledger-consistency 9 ok,
                 4 repaired tests + FND-069 regression 58 ok, targeted product
                 tests 53+18 ok, prior full suite 2249 ok. The authoritative
                 check is the CI run on the pushed commit, watched to green.)
- [ ] sell      (n/a)

## Layer 3 (CI on 2f10180 unmasked three more)
- _route_utils.py:49 mypy: `route.methods` is Optional → `(route.methods or set())`.
  (Missed locally because the new file was added AFTER my `mypy .` run — re-run
  mypy AFTER adding files, always.)
- ci.yml "Unit & Integration Tests" job checks out SHALLOW → the story-index
  evidence UNIT test (test_story_index_evidence_gate) fails on git history, same
  root cause as the gate. Add fetch-depth: 0 there too.
- DECISIVE: my recursive helper returns only 2 routes on the REAL app in CI
  (test_helper_works_on_the_real_app: assert 2 > 50 failed). So CI's Starlette
  nests in a shape my recursion does NOT traverse — the helper cannot fix CI by
  itself. Root fix = kill the drift: PIN fastapi==0.129.0 + starlette==0.52.1
  (the validated-local versions that flatten). Helper + regression stay as
  defensive robustness; the PIN is what makes CI == local and green.

## Layer 4 (CI on 564dacf — 2/3 workflows green; Fly.io remained)
- deploy.yml (SARO CI/CD — Fly.io) `test` job ALSO checks out shallow and runs
  the full pytest incl. test_story_index_evidence_gate → same shallow-clone
  failure, THIRD workflow. fetch-depth: 0. That is now all three workflows
  that run this test (quality-gates ✓, ci ✓, deploy ✓).

## Build Log
- FALSE HYPOTHESIS (recorded so it isn't re-tried): the 4 route-registration
  CI failures looked like test-isolation pollution of the shared `main.app`.
  A routewatch plugin over the full local suite logged ZERO route drops →
  main.app never collapses locally. Real cause: FND-069 — Starlette nests
  included routers under some versions; the tests filtered app.routes at the
  top level. Not order-dependent, not pollution, not a product bug.

## Decision Log
- Q: validation_bar.py:40 union-attr on `bool(raw) and raw.get(...)` → mypy
  doesn't narrow via bool(); use `raw is not None and raw.get(...)`.
- Q: test_story358:49 `Envelope(**base)` with base=dict[str,object] → annotate
  `base: dict[str, Any]` so the splat is accepted (test helper, mixed values).
- Q: canary_evaluation.py:89 float(Any|None) → `_fail` always sys.exit(1);
  type it `-> NoReturn` so mypy narrows `score` after the None guard. Correct
  semantically, not just a silencer.
- Q: generate_feedback_summary.py / check_feedback_traceability.py import
  `SessionLocal` which database.py does NOT export → this is a latent runtime
  bug (ImportError, currently swallowed by `except`, so the scripts silently
  never read the feedback DB). Fix with the real API the working cli.py uses:
  `from database import _get_session_factory; db = _get_session_factory()()`.
- Q: cli.py:950/953 `summary[...].items()` on inferred `object` → annotate
  `summary: dict[str, Any]`.
- Q: 4 route-registration tests fail only in the full CI suite, pass in
  isolation → suspected shared-`main.app` test pollution. Reproduce with a full
  local `pytest tests/` in CI order, find the polluter, fix isolation, add a
  regression test (findings discipline). ← investigated in BUILD.

## Deviations
None yet.
