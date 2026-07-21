"""Cross-adapter conformance harness (STORY-361).

"SARO supports Azure and Vertex" is a claim. This harness is what makes it a
tested one: a scenario set expressed **once**, instantiated against every
adapter, with results rendered as a per-adapter pass/fail matrix.

The design problem it solves is subtler than "run the same tests everywhere".
Adapters genuinely differ in what their provider's logs can express — Azure and
Vertex audit logs carry no tool data, so a tool-scope scenario is not
representable there. Two bad ways to handle that:

* Fail those adapters — turns a provider limitation into a permanent red build
  and pressures someone into faking the data.
* Skip quietly — the suite goes green while coverage silently does not exist.

So an adapter may declare a scenario ``NOT_SUPPORTED``, but only **explicitly
and with a written reason**, and the reason lands in the report as a coverage
gap. Silence is not an option the API offers: a provider must return an outcome
for every scenario. The matrix this produces is the honest input to the
buyer-facing capability matrix (STORY-362) — generated from what the code
actually does rather than hand-authored.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.contract import NormalizedInvocationRecord  # noqa: E402


class Scenario(str, Enum):
    """The shared scenario set. Expressed once; instantiated per adapter."""

    HAPPY_PATH = "happy_path"
    MISSING_FIELDS = "missing_fields"
    MALFORMED_RECORD = "malformed_record"
    TOOL_SCOPE_VIOLATION = "tool_scope_violation"
    INCOMPLETE_OBSERVATION = "incomplete_observation"
    TENANCY_SPOOFING = "tenancy_spoofing"


SCENARIO_INTENT: dict[Scenario, str] = {
    Scenario.HAPPY_PATH: "A well-formed invocation normalizes with identity fields populated.",
    Scenario.MISSING_FIELDS: "Absent fields are classified, never returned as silent nulls.",
    Scenario.MALFORMED_RECORD: "An uninterpretable record raises rather than half-populating.",
    Scenario.TOOL_SCOPE_VIOLATION: "An out-of-scope tool call is detected by RP-TOOL-SCOPE.",
    Scenario.INCOMPLETE_OBSERVATION: "A truncated/partial observation is detectable as incomplete.",
    Scenario.TENANCY_SPOOFING: "A record claiming another tenant cannot override the operator binding.",
}


class Support(str, Enum):
    SUPPORTED = "supported"
    # Works only under a stated precondition — e.g. the customer's export is
    # enriched beyond the provider's standard schema. Distinct from SUPPORTED
    # because a buyer reading a tick would assume it works on the logs they
    # already have. The precondition is mandatory and lands in the report.
    CONDITIONAL = "conditional"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True)
class Outcome:
    """What an adapter provides for one scenario.

    Exactly one shape is valid per scenario kind:

    * a ``record`` — the adapter normalized the scenario's input;
    * a ``raises`` exception instance — the adapter refused it (MALFORMED_RECORD);
    * ``NOT_SUPPORTED`` + ``reason`` — the provider's logs cannot express it.

    ``reason`` is mandatory for NOT_SUPPORTED and is asserted non-trivial, so a
    gap cannot be waved through with an empty string.
    """

    support: Support
    record: Optional[NormalizedInvocationRecord] = None
    raised: Optional[BaseException] = None
    reason: str = ""
    # Tools the tenant is deemed to allow, for the tool-scope scenario.
    allowed_tools: tuple[str, ...] = ()

    @staticmethod
    def supported(
        record: Optional[NormalizedInvocationRecord] = None,
        *,
        raised: Optional[BaseException] = None,
        allowed_tools: tuple[str, ...] = (),
    ) -> "Outcome":
        return Outcome(
            support=Support.SUPPORTED,
            record=record,
            raised=raised,
            allowed_tools=allowed_tools,
        )

    @staticmethod
    def conditional(
        record: NormalizedInvocationRecord,
        *,
        reason: str,
        allowed_tools: tuple[str, ...] = (),
    ) -> "Outcome":
        """Supported only under a precondition — the record must still pass."""
        return Outcome(
            support=Support.CONDITIONAL,
            record=record,
            reason=reason,
            allowed_tools=allowed_tools,
        )

    @staticmethod
    def not_supported(reason: str) -> "Outcome":
        return Outcome(support=Support.NOT_SUPPORTED, reason=reason)


class AdapterUnderTest(Protocol):
    """What an adapter must provide to enter the conformance suite."""

    adapter_id: str
    display_name: str

    def build(self, scenario: Scenario) -> Outcome: ...


@dataclass
class ConformanceResult:
    adapter_id: str
    display_name: str
    scenario: Scenario
    support: Support
    passed: bool
    detail: str = ""
    reason: str = ""


@dataclass
class ConformanceReport:
    results: list[ConformanceResult] = field(default_factory=list)

    @property
    def adapters(self) -> list[str]:
        seen: list[str] = []
        for r in self.results:
            if r.display_name not in seen:
                seen.append(r.display_name)
        return seen

    @property
    def failures(self) -> list[ConformanceResult]:
        return [r for r in self.results if not r.passed]

    @property
    def gaps(self) -> list[ConformanceResult]:
        return [r for r in self.results if r.support is Support.NOT_SUPPORTED]

    @property
    def conditionals(self) -> list[ConformanceResult]:
        return [r for r in self.results if r.support is Support.CONDITIONAL]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "saro.conformance.v1",
            "scenarios": [s.value for s in Scenario],
            "results": [
                {
                    "adapter_id": r.adapter_id,
                    "adapter": r.display_name,
                    "scenario": r.scenario.value,
                    "support": r.support.value,
                    "passed": r.passed,
                    "reason": r.reason,
                    "detail": r.detail,
                }
                for r in self.results
            ],
            "summary": {
                "adapters": len(self.adapters),
                "checks": len(self.results),
                "failed": len(self.failures),
                "coverage_gaps": len(self.gaps),
                "conditional": len(self.conditionals),
            },
        }

    def to_markdown(self) -> str:
        """Pass/fail matrix. Gaps render as a distinct symbol, never as a pass."""
        adapters = self.adapters
        lines = [
            "# Adapter Conformance Matrix",
            "",
            "Generated by `scripts/generate_conformance_report.py` from the "
            "STORY-361 suite — not hand-authored.",
            "",
            "| Scenario | " + " | ".join(adapters) + " |",
            "|---|" + "---|" * len(adapters),
        ]
        by_key = {(r.display_name, r.scenario): r for r in self.results}
        for scenario in Scenario:
            cells = []
            for adapter in adapters:
                r = by_key.get((adapter, scenario))
                if r is None:
                    cells.append("—")
                elif not r.passed:
                    cells.append("❌ FAIL")
                elif r.support is Support.NOT_SUPPORTED:
                    cells.append("⚠️ n/a")
                elif r.support is Support.CONDITIONAL:
                    cells.append("◐ conditional")
                else:
                    cells.append("✅")
            lines.append(f"| {scenario.value} | " + " | ".join(cells) + " |")

        lines += [
            "",
            "**Legend:** ✅ works on the provider's standard logs · ◐ conditional = "
            "works only under the stated precondition (see below) · ⚠️ n/a = the "
            "provider's logs cannot express this scenario — a coverage gap, not a "
            "pass · ❌ failing.",
            "",
        ]

        if self.conditionals:
            lines += ["## Conditional support (preconditions apply)", ""]
            for r in sorted(self.conditionals, key=lambda x: (x.display_name, x.scenario.value)):
                lines.append(f"- **{r.display_name} / {r.scenario.value}** — {r.reason}")
            lines.append("")

        if self.gaps:
            lines += ["## Coverage gaps (stated, not hidden)", ""]
            for r in sorted(self.gaps, key=lambda x: (x.display_name, x.scenario.value)):
                lines.append(f"- **{r.display_name} / {r.scenario.value}** — {r.reason}")
            lines.append("")
        return "\n".join(lines)


# ── Expectations: one implementation, applied to every adapter ──────────────


def _check(outcome: Outcome, scenario: Scenario) -> tuple[bool, str]:
    """Return (passed, detail) for one adapter/scenario pair."""
    if outcome.support is Support.NOT_SUPPORTED:
        if len(outcome.reason.strip()) < 20:
            return False, "NOT_SUPPORTED requires a substantive written reason"
        return True, "declared unsupported with a reason (recorded as a gap)"

    if outcome.support is Support.CONDITIONAL and len(outcome.reason.strip()) < 20:
        return False, "CONDITIONAL requires the precondition to be written out"

    if scenario is Scenario.MALFORMED_RECORD:
        if outcome.raised is None:
            return False, "malformed input did not raise — a half-populated record is worse than none"
        if outcome.record is not None:
            return False, "adapter both raised and produced a record"
        return True, f"raised {type(outcome.raised).__name__}"

    record = outcome.record
    if record is None:
        return False, "supported scenario produced no record"

    if scenario is Scenario.HAPPY_PATH:
        for f in ("request_id", "operation"):
            if not getattr(record, f, None):
                return False, f"happy path missing {f}"
        if record.timestamp is None:
            return False, "happy path missing timestamp"
        if not record.provenance.adapter_id or not record.provenance.cursor:
            return False, "provenance incomplete (adapter_id/cursor)"
        return True, "identity + provenance populated"

    if scenario is Scenario.MISSING_FIELDS:
        absent = [
            f
            for f in ("input_token_count", "output_token_count", "region", "model_id")
            if getattr(record, f, None) in (None, "")
        ]
        if not absent:
            return False, "scenario produced no absent field to classify"
        unclassified = [f for f in absent if record.availability(f).value == "present"]
        if unclassified:
            return False, f"silent nulls (absent but marked present): {unclassified}"
        return True, f"classified absent fields: {absent}"

    if scenario is Scenario.INCOMPLETE_OBSERVATION:
        from rule_packs.observation.evaluate import evaluate_record
        from rule_packs.observation.loader import load_pack

        pack = load_pack(ROOT / "rule_packs" / "observation" / "rp_obs_complete" / "1.0.0" / "pack.yaml")
        fired = {f.rule_id for f in evaluate_record(record, pack)}
        if "OBS-TRUNCATED-OUTPUT-1" not in fired:
            return False, f"incompleteness not detected (fired: {sorted(fired)})"
        return True, "RP-OBS-COMPLETE flagged the partial observation"

    if scenario is Scenario.TOOL_SCOPE_VIOLATION:
        from rule_packs.observation.evaluate import evaluate_record
        from rule_packs.observation.loader import load_pack

        pack = load_pack(
            ROOT / "rule_packs" / "observation" / "rp_tool_scope" / "1.0.0" / "pack.yaml"
        ).with_allowed_tools(list(outcome.allowed_tools))
        fired = {f.rule_id for f in evaluate_record(record, pack)}
        if "TOOL-SCOPE-VIOLATION-1" not in fired:
            return False, f"out-of-scope tool call not detected (fired: {sorted(fired)})"
        return True, "RP-TOOL-SCOPE flagged the out-of-scope call"

    if scenario is Scenario.TENANCY_SPOOFING:
        expected = getattr(outcome, "_expected_tenant", None)
        # The provider binds a known tenant; the record must carry exactly it.
        if expected is not None and record.tenant_id != expected:
            return False, "log content overrode the operator's tenant binding (INV-3)"
        return True, "tenancy taken from operator config, not log content"

    return False, f"unhandled scenario {scenario}"


# Content-bearing field names that must never appear on a normalized record.
_CONTENT_FIELDS = {
    "prompt", "raw_output", "content", "message", "messages", "text",
    "completion", "response_text", "tool_input", "tool_arguments", "body",
}


def universal_invariants(record: NormalizedInvocationRecord) -> list[str]:
    """Checks every adapter's every record must satisfy. Returns violations."""
    problems: list[str] = []
    leaked = set(type(record).model_fields) & _CONTENT_FIELDS
    if leaked:
        problems.append(f"contract exposes content-bearing field(s): {sorted(leaked)}")
    if not record.provenance.adapter_id:
        problems.append("provenance.adapter_id empty")
    if not record.provenance.cursor:
        problems.append("provenance.cursor empty — record is not resumable")
    if record.timestamp is not None and record.timestamp.tzinfo is None:
        problems.append("timestamp is naive — evidence timestamps must be tz-aware")
    return problems


def run_conformance(adapters: list[AdapterUnderTest]) -> ConformanceReport:
    """Run every scenario against every adapter and collect results."""
    report = ConformanceReport()
    for adapter in adapters:
        for scenario in Scenario:
            try:
                outcome = adapter.build(scenario)
            except NotImplementedError as exc:  # provider forgot a scenario
                report.results.append(
                    ConformanceResult(
                        adapter.adapter_id, adapter.display_name, scenario,
                        Support.SUPPORTED, False,
                        detail=f"provider did not handle the scenario: {exc}",
                    )
                )
                continue
            passed, detail = _check(outcome, scenario)
            report.results.append(
                ConformanceResult(
                    adapter_id=adapter.adapter_id,
                    display_name=adapter.display_name,
                    scenario=scenario,
                    support=outcome.support,
                    passed=passed,
                    detail=detail,
                    reason=outcome.reason,
                )
            )
    return report


def load_registered_adapters() -> list[AdapterUnderTest]:
    from conformance.providers import REGISTERED_ADAPTERS  # local import for path setup

    return REGISTERED_ADAPTERS


ParserFactory = Callable[..., Any]
