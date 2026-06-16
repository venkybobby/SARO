"""Uniform interface for STORY-309 output checks.

A check is a pure callable ``(CheckContext) -> CheckFinding``. Keeping a uniform
interface lets checks be added/removed and tier-selected later (STORY-304)
without touching the orchestrator. Each finding carries the check's proposed
likelihood/impact (scored by STORY-310), a fact/assessment split (STORY-312) and
any framework citations (verified via STORY-317).
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field


class CheckContext(BaseModel):
    """Everything a check may inspect about one audited output."""

    output_id: str
    system_id: str | None = None
    output_text: str = ""
    prompt: str | None = None
    retrieved_context: str | None = None
    # The authorized purpose from the registry (STORY-301), for prohibited-use.
    registry_purpose: str | None = None


class CheckFinding(BaseModel):
    """One check's structured result."""

    check: str
    status: str  # "pass" | "concern"
    detail: str
    likelihood: int = Field(ge=1, le=5, default=1)
    impact: int = Field(ge=1, le=5, default=1)
    remediation: str | None = None
    framework_mapping: list[dict] = Field(default_factory=list)
    facts: str = ""
    assessment: str = ""
    scope_change_flag: bool = False

    @property
    def is_concern(self) -> bool:
        return self.status == "concern"


Check = Callable[[CheckContext], CheckFinding]


# Registered in execution order. Imported lazily to avoid a heavy import chain
# (the leakage check reuses engine PII patterns) at package import time.
def _load_checks() -> list[Check]:
    from grc.checks.bias import bias_check
    from grc.checks.groundedness import groundedness_check
    from grc.checks.leakage import leakage_check
    from grc.checks.prohibited_use import prohibited_use_check
    from grc.checks.regulatory_claim import regulatory_claim_check

    return [
        groundedness_check,
        leakage_check,
        bias_check,
        prohibited_use_check,
        regulatory_claim_check,
    ]


ALL_CHECKS: list[Check] = []


def run_all_checks(ctx: CheckContext) -> list[CheckFinding]:
    """Run the full Phase-1 check set over one output (STORY-308 calls this).

    The dependency-relaxation note in STORY-308 says: run the full check set on
    every output regardless of tier; tier routing slots in at Phase 2.
    """
    global ALL_CHECKS
    if not ALL_CHECKS:
        ALL_CHECKS = _load_checks()
    return [check(ctx) for check in ALL_CHECKS]
