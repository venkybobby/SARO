# Pre-push gate for main (guard against pushing on red)
Stage: trivial

Server-side branch protection is plan-gated (private repo on GitHub Free →
403 on both classic protection and rulesets). Chosen mitigation: a tracked
client-side pre-push hook that runs the fast local gates and blocks a push to
main if they fail. Dev tooling only; no product/interface change.

## Lifecycle
- [x] trivial — skip to BUILD

## Decision Log
- Q: which gates, kept fast enough for pre-push (~1-2 min)? → ruff + mypy +
  story-index + `pytest -m unit`. Catches the locally-detectable failures that
  accumulated this session (ruff F401, mypy). Full suite (10 min) is too slow
  for a push gate; CI still runs it.
- Q: only on main? → yes — read stdin refs, run gates only when a pushed
  remote ref is refs/heads/main; other branches push freely.
- Q: how installed (hooks aren't tracked by default)? → tracked in `.githooks/`,
  activated per-clone with `git config core.hooksPath .githooks`; set for this
  clone now + documented + a one-line install script.
- Q: enforcement honesty? → per-developer, bypassable with `--no-verify`. Not
  a substitute for server-side protection (needs Pro); documented as such.

## Deviations
None.
