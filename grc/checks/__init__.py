"""STORY-309 — Automated output checks.

Five independent checks, each with a uniform interface, run on every audited
output. Each emits a :class:`CheckFinding` (pass / concern + detail) that the
orchestrator (STORY-308) scores and dispositions.
"""

from __future__ import annotations

from grc.checks.base import (
    ALL_CHECKS,
    CheckContext,
    CheckFinding,
    run_all_checks,
)

__all__ = ["ALL_CHECKS", "CheckContext", "CheckFinding", "run_all_checks"]
