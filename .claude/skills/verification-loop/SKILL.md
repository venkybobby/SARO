---
name: verification-loop
description: Triggered before committing, opening a PR, or marking any implementation task complete. Runs SARO's unified test -> lint -> typecheck -> security gate so a green local run predicts a green CI pipeline.
---

Run the consolidated verification gate before declaring work done. This is the
single entry point that mirrors the CI gates in `CLAUDE.md` (Testing
Requirements) and `docs/engineering-standards.md` (quality ratchet).

Adapted from ECC's `verification-loop` pattern, tuned to SARO's stack and
compliance posture.

## Run it

```bash
bash scripts/verify.sh            # local pre-commit gate
VERIFY_STRICT=1 bash scripts/verify.sh   # treat advisory gates as blocking
```

## Gate classes

| Gate | Class | Tool | Blocks? |
|---|---|---|---|
| Tests | REQUIRED | `pytest tests/ -q` | yes |
| Lint | REQUIRED | `ruff check .` | yes |
| Security static scan | REQUIRED | `scripts/security_scan.sh` | yes |
| Typecheck | ADVISORY | `mypy .` | only under `VERIFY_STRICT=1` |
| Dependency audit | ADVISORY | `pip-audit` | only under `VERIFY_STRICT=1` |

`mypy` and `pip-audit` are advisory locally because `mypy.ini` carries
documented pre-existing suppressions and `pip-audit` depends on network +
advisory-DB freshness. CI may still run them as hard gates.

## Order of operations (when a gate fails)

1. **pytest** red → fix the code, never weaken the test (engineering-standards
   core invariant; max 3 gate cycles then escalate).
2. **ruff** red → fix style; only add a `per-file-ignores` entry in `ruff.toml`
   with a one-line justification, never a blanket suppression.
3. **security_scan** HIGH finding → triage each; a true false-positive gets an
   inline waiver or an FND via `/finding`, never a silent deletion of the rule.

## Relationship to other gates

- The `Stop` hook already runs `pytest`; `verify.sh` is the superset you run by
  hand before commit/PR.
- For adversarial depth (tenant isolation, JWT, RLS) still delegate to the
  `security-auditor` agent — the static scan is a fast first pass, not a
  replacement.
- Compliance posture is unaffected: every gate is read-only and local.
