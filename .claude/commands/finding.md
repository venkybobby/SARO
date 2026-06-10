---
description: Log a new finding and pin it with a regression test
argument-hint: <short description of the bug/finding>
---

Process a new finding: "$ARGUMENTS"

1. Assign the next FND-### ID (read quality/findings.md for the highest existing).
2. Root-cause it (5-whys, briefly). Add a row to quality/findings.md.
3. Write `tests/regression/test_fnd_###_<slug>.py` that REPRODUCES the failure —
   run it and show it failing (red) before any fix.
4. Implement the minimal fix. Show the regression test passing (green).
5. Add the manifest entry in tests/regression/manifest.yaml with status `pinned`.
6. Run `pytest tests/regression -q` (full) plus gates 1–4 from /story.
7. End with FILES CHANGED / NOT TOUCHED / CONCERNS.
