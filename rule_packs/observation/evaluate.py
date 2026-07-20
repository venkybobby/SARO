"""Observation rule-pack evaluator (PREREQ-RP).

Pure and deterministic: ``(record, pack) -> findings``. No I/O, no DB, no model
calls (INV-1). Determinism is not incidental — STORY-378's confusion-matrix
harness and every attestation depend on the same input producing the same
findings, byte for byte, on every run.

Evaluated over :class:`adapters.contract.NormalizedInvocationRecord` only, so
the evaluator is adapter-agnostic by construction: Bedrock, Azure, and Vertex
records are indistinguishable here, which is what makes "supports Azure/Vertex"
a property of the adapters rather than of every rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from adapters.contract import FieldAvailability, NormalizedInvocationRecord
from rule_packs.observation.loader import ObservationPack, ObservationRule


@dataclass(frozen=True)
class Finding:
    """One rule firing on one record. Evidence-shaped, never a verdict.

    ``detail`` holds identifiers and field NAMES only — never a value that could
    be message content (INV-2). Tool names are metadata and may appear.
    """

    rule_id: str
    pack_ref: str
    pack_hash: str
    severity: str
    title: str
    remediation: str
    request_id: str
    detail: dict[str, Any]

    def to_evidence(self) -> dict[str, Any]:
        """Serializable form for attestation payloads."""
        return {
            "rule_id": self.rule_id,
            "rule_pack": self.pack_ref,
            "rule_pack_hash": self.pack_hash,
            "severity": self.severity,
            "title": self.title,
            "remediation_guidance": self.remediation,
            "request_id": self.request_id,
            "detail": self.detail,
        }


def _finding(
    rule: ObservationRule,
    pack: ObservationPack,
    record: NormalizedInvocationRecord,
    detail: dict[str, Any],
    severity: Optional[str] = None,
) -> Finding:
    return Finding(
        rule_id=rule.rule_id,
        pack_ref=pack.pack_ref,
        pack_hash=pack.content_hash,
        severity=severity or rule.severity,
        title=rule.title,
        remediation=rule.remediation,
        request_id=record.request_id,
        detail=detail,
    )


# ── Individual checks ────────────────────────────────────────────────────────


def _check_required_fields(rule, pack, record) -> list[Finding]:
    """Fire per rule (not per field) listing every absent field.

    Severity is downgraded to ``unavailable_severity`` only when EVERY absent
    field is structurally unavailable for this provider. If even one field is
    merely missing from this record, the rule keeps its normal severity — a real
    data-quality gap must not be masked by a provider limitation sitting beside it.
    """
    absent: list[str] = []
    availabilities: list[FieldAvailability] = []
    for name in rule.required_fields:
        if getattr(record, name, None) is None:
            absent.append(name)
            availabilities.append(record.availability(name))
    if not absent:
        return []

    severity = rule.severity
    if (
        rule.unavailable_severity
        and availabilities
        and all(a is FieldAvailability.UNAVAILABLE for a in availabilities)
    ):
        severity = rule.unavailable_severity

    return [
        _finding(
            rule,
            pack,
            record,
            {
                "absent_fields": absent,
                "availability": {n: record.availability(n).value for n in absent},
            },
            severity=severity,
        )
    ]


def _check_truncation(rule, pack, record) -> list[Finding]:
    if not record.truncated:
        return []
    return [_finding(rule, pack, record, {"stop_reason": record.stop_reason})]


def _check_error_present(rule, pack, record) -> list[Finding]:
    if not record.error_code:
        return []
    return [_finding(rule, pack, record, {"error_code": record.error_code})]


def _check_tool_not_in_allowlist(rule, pack, record) -> list[Finding]:
    # No declared policy → cannot judge scope; TOOL-POLICY-ABSENT-1 covers it.
    if not pack.allowed_tools:
        return []
    allowed = set(pack.allowed_tools)
    violations = sorted(t for t in record.invoked_tools if t not in allowed)
    if not violations:
        return []
    return [
        _finding(
            rule,
            pack,
            record,
            {"invoked_out_of_scope": violations, "allowed_tools": sorted(allowed)},
        )
    ]


def _check_tool_offered_not_allowed(rule, pack, record) -> list[Finding]:
    if not pack.allowed_tools:
        return []
    allowed = set(pack.allowed_tools)
    invoked = set(record.invoked_tools)
    # Offered-but-not-invoked only: an invoked violation is the stronger finding
    # and is already reported by TOOL-SCOPE-VIOLATION-1. Reporting both would
    # double-count the same tool in the confusion matrix (STORY-378).
    offered = sorted(
        t for t in record.offered_tools if t not in allowed and t not in invoked
    )
    if not offered:
        return []
    return [
        _finding(
            rule, pack, record, {"offered_out_of_scope": offered, "allowed_tools": sorted(allowed)}
        )
    ]


def _check_tool_policy_absent(rule, pack, record) -> list[Finding]:
    if pack.allowed_tools:
        return []
    used = sorted(set(record.invoked_tools) | set(record.offered_tools))
    if not used:
        return []  # no tools in play — absence of policy is not yet a gap
    return [_finding(rule, pack, record, {"tools_seen": used})]


_CHECKS = {
    "required_fields": _check_required_fields,
    "truncation_is_incomplete": _check_truncation,
    "error_present": _check_error_present,
    "tool_not_in_allowlist": _check_tool_not_in_allowlist,
    "tool_offered_not_allowed": _check_tool_offered_not_allowed,
    "tool_policy_absent": _check_tool_policy_absent,
}


# ── Public API ───────────────────────────────────────────────────────────────


def evaluate_record(
    record: NormalizedInvocationRecord, pack: ObservationPack
) -> list[Finding]:
    """Evaluate one record against one pack. Deterministic, pack-rule order."""
    findings: list[Finding] = []
    for rule in pack.rules:
        check = _CHECKS.get(rule.check)
        if check is None:  # pragma: no cover — loader rejects unknown checks
            raise ValueError(f"unknown check {rule.check!r} in {pack.pack_ref}")
        findings.extend(check(rule, pack, record))
    return findings


def evaluate_records(
    records: list[NormalizedInvocationRecord], packs: list[ObservationPack]
) -> list[Finding]:
    """Evaluate many records against many packs — record order, then pack order."""
    out: list[Finding] = []
    for record in records:
        for pack in packs:
            out.extend(evaluate_record(record, pack))
    return out
