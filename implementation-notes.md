# Tune: allow test files through the lifecycle gate
Stage: trivial

Single-file change to .claude/hooks/lifecycle-gate.sh: add test paths to the
always-allowed list so a failing/regression test can be written before the
Decision Log exists (TDD red step; /finding red-first flow). Threshold stays at
3 (unchanged) per the tuning decision. No interface, data-model, or user-facing
change — gates stand down.

Globs (anchored to filename/dir boundaries so source lookalikes don't slip
through): */tests/*, tests/*, */test_*.py, test_*.py, *_test.py, *.test.*,
*.spec.*  — verified allowing 8 real test paths (incl. Windows backslash) while
still blocking engine.py, routers/scan.py, latest_config.py, contest_helper.py.

## Lifecycle
- [x] build   (glob added, isolated-repo matrix green)
