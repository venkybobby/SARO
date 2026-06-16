"""STORY-308 — Audit orchestrator service.

Runs the output-audit protocol over one output and emits a contract-shaped
result (STORY-328). It is the spine the checks, scoring and gate hang off:

    provenance check (306)  →  automated checks (309)  →  scoring & disposition (310)
        →  assemble + validate against the JSON contract (328)

Provenance runs first and short-circuits to ``EVIDENCE_GAP`` (no ``PASS`` is ever
emitted on incomplete provenance). Per STORY-308's dependency-relaxation note,
the full Phase-1 check set runs on every output regardless of tier (tier routing,
STORY-304, slots in at Phase 2 without changing this interface).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from grc.checks import CheckContext, CheckFinding, run_all_checks
from grc.contract import SCHEMA_VERSION, validate_audit_result
from grc.policy import GRCPolicy, get_active_policy
from grc.provenance import enforce_can_pass, evaluate_provenance
from grc.scoring import (
    CONDITIONAL,
    EVIDENCE_GAP,
    FAIL,
    PASS,
    score_risk,
    validate_disposition,
)


def _evidence_field(evidence: Any, field: str) -> Any:
    if evidence is None:
        return None
    if isinstance(evidence, dict):
        return evidence.get(field)
    return getattr(evidence, field, None)


def _evidence_block(evidence: Any) -> dict[str, Any]:
    eid = _evidence_field(evidence, "id")
    ids = [str(eid)] if eid is not None else []
    return {"status": "LINKED", "evidence_ids": ids}


def _disposition_for(status: str, band: str) -> str:
    """Map a check result + risk band to a disposition.

    pass → PASS; a concern in a HIGH/CRITICAL band is a FAIL, otherwise a
    CONDITIONAL (it can ship with remediation).
    """
    if status == "pass":
        return PASS
    return FAIL if band in ("HIGH", "CRITICAL") else CONDITIONAL


def _finding_from_check(
    cf: CheckFinding, evidence: Any, policy: GRCPolicy
) -> dict[str, Any]:
    risk = score_risk(cf.likelihood, cf.impact, policy)
    disposition = _disposition_for(cf.status, risk.band)
    remediation = cf.remediation
    if disposition == PASS:
        # Hard guard (STORY-306/312): a PASS requires complete provenance.
        enforce_can_pass(evidence)
    else:
        remediation = remediation or cf.detail
    validate_disposition(disposition, remediation)
    return {
        "id": f"{cf.check}",
        "check": cf.check,
        "disposition": disposition,
        "risk": risk.model_dump(),
        "evidence": _evidence_block(evidence),
        "remediation": remediation,
        "framework_mapping": cf.framework_mapping,
        "facts": cf.facts or cf.detail,
        "assessment": cf.assessment or cf.detail,
        "scope_change_flag": cf.scope_change_flag,
    }


def _evidence_gap_finding(missing: list[str]) -> dict[str, Any]:
    return {
        "id": "provenance",
        "check": "provenance_completeness",
        "disposition": EVIDENCE_GAP,
        "risk": {"likelihood": 3, "impact": 3, "score": 9, "band": "MODERATE"},
        "evidence": {"status": "MISSING", "evidence_ids": []},
        "remediation": (
            "Capture complete provenance (missing: "
            + ", ".join(missing)
            + ") before this output can be audited."
        ),
        "framework_mapping": [
            {"framework": "NIST_AI_RMF", "identifier": "GOVERN", "status": "VERIFIED"}
        ],
        "facts": f"Provenance missing required fields: {', '.join(missing)}.",
        "assessment": "Audit cannot proceed to PASS without complete provenance.",
        "scope_change_flag": False,
    }


def gate_recommendation(findings: list[dict[str, Any]], policy: GRCPolicy) -> str:
    """Contract-valid gate recommendation.

    Authoritative gate logic (≥N High FAILs, governance gaps) lands in
    STORY-326; this satisfies the contract's Critical-FAIL⇒NO_GO rule and a safe
    default in the interim. The lifecycle gate engine supersedes this.
    """
    fails = [f for f in findings if f["disposition"] == FAIL]
    if any(f["risk"]["band"] == "CRITICAL" for f in fails):
        return "NO_GO"
    high_fails = sum(1 for f in fails if f["risk"]["band"] == "HIGH")
    if high_fails >= policy.gate_high_fail_threshold:
        return "NO_GO"
    if any(f["disposition"] in (FAIL, CONDITIONAL, EVIDENCE_GAP) for f in findings):
        return "GO_WITH_CONDITIONS"
    return "GO"


def run_audit(
    output_id: str,
    evidence: Any,
    *,
    system_id: str | None = None,
    registry_purpose: str | None = None,
    output_text: str | None = None,
    generated_at: datetime | None = None,
    policy: GRCPolicy | None = None,
) -> dict[str, Any]:
    """Audit one output and return a contract-validated result dict.

    ``evidence`` is the provenance record (ORM row, mapping, or EvidenceCapture).
    ``output_text`` defaults to the captured decision.
    """
    pol = policy or get_active_policy()
    stamped = (generated_at or datetime.now(tz=timezone.utc)).isoformat()
    sys_id = system_id or str(_evidence_field(evidence, "system_id") or "unknown")

    prov = evaluate_provenance(evidence)
    if not prov.complete:
        findings = [_evidence_gap_finding(prov.missing)]
    else:
        ctx = CheckContext(
            output_id=output_id,
            system_id=sys_id,
            output_text=output_text
            if output_text is not None
            else (_evidence_field(evidence, "decision") or ""),
            prompt=_evidence_field(evidence, "prompt"),
            retrieved_context=_evidence_field(evidence, "retrieved_context"),
            registry_purpose=registry_purpose,
        )
        findings = [
            _finding_from_check(cf, evidence, pol) for cf in run_all_checks(ctx)
        ]

    result = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": pol.version,
        "audited_output_id": output_id,
        "system_id": sys_id,
        "generated_at": stamped,
        "findings": findings,
        "gate_recommendation": gate_recommendation(findings, pol),
    }
    return validate_audit_result(result)


def run_audit_by_id(db, *, tenant_id: uuid.UUID, output_id: str) -> dict[str, Any]:
    """DB-backed entry point: load the latest evidence for ``output_id`` and audit it."""
    from grc.evidence import GRCEvidenceRecord
    from grc.registry import get_entry

    record = (
        db.query(GRCEvidenceRecord)
        .filter(
            GRCEvidenceRecord.tenant_id == tenant_id,
            GRCEvidenceRecord.output_id == output_id,
        )
        .order_by(GRCEvidenceRecord.seq.desc())
        .first()
    )
    purpose = None
    sys_id = _evidence_field(record, "system_id")
    if sys_id:
        try:
            entry = get_entry(db, tenant_id=tenant_id, entry_id=uuid.UUID(str(sys_id)))
            purpose = entry.purpose if entry else None
        except (ValueError, TypeError):
            purpose = None
    return run_audit(
        output_id,
        record,
        system_id=str(sys_id) if sys_id else None,
        registry_purpose=purpose,
    )
