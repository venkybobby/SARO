# FND-087 — demo runner + screencast pipeline crash/corrupt on cp1252 consoles (Windows)

Stage: trivial

Single-defect encoding fix (FND-038 class — the "sibling-script encoding
sweep" follow-up that fix left open). `scripts/demo_azure_vertex_e2e.py`
prints ✔/▲/→; on Windows a piped child process encodes stdout as cp1252 →
UnicodeEncodeError, exit 1 — so `test_committed_screencast_is_in_sync_with_
the_demo` fails on every Windows machine while CI (Linux/UTF-8) stays green.
Found by the stop-hook full-suite run in the FND-074 session, 2026-07-24;
reproduced on pristine origin/main (bbf05bc). Sibling defects in the same
pipeline: `build_demo_screencast.py` subprocess-captures with locale decoding
and `write_text()`s the SVG/HTML artifacts in the locale codec (would emit
cp1252 artifacts if regenerated on Windows); the sync test decodes the
subprocess and `read_text()`s the committed artifacts with the locale codec.

## Steps (= build stage for a trivial finding)

- [x] FND-087 assigned (highest existing: FND-086)
- [x] Red-first pin: tests/regression/test_fnd_087_demo_script_utf8_console.py
      forces PYTHONIOENCODING=cp1252 (reproduces the Windows failure on any OS;
      failed pre-fix, passes post-fix)
- [x] Fix: demo runner reconfigures stdout/stderr to UTF-8 in main();
      screencast builder + sync test pass encoding="utf-8" at every
      subprocess/read_text/write_text seam; corpus paths rendered .as_posix()
      (second determinism break found while fixing: OS path separators)
- [x] findings.md row + manifest entry status pinned (same commit, FM-4)
- [x] Committed artifacts byte-unchanged (docs/demo/ clean in git status after
      a fresh render comparison; sync test green on Windows)

## Deviations
None.
