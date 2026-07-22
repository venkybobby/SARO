#!/usr/bin/env bash
# Activate the tracked git hooks in .githooks/ for this clone.
# Run once after cloning:  bash scripts/install-git-hooks.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "core.hooksPath -> .githooks (pre-push gate active for pushes to main)"
