"""
Reports API — data endpoints consumed by the Streamlit Reports tab.

GET /api/v1/reports/summary          — aggregate stats across all tenant audits
GET /api/v1/reports/{audit_id}       — full report for one audit
GET /api/v1/reports/{audit_id}/mit   — MIT coverage detail
GET /api/v1/reports/{audit_id}/delta — fixed-delta detail
GET /api/v1/reports/{audit_id}/rules — applied rules list
GET /api/v1/reports/{audit_id}/incidents — similar incidents
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from engine import (
    COMPLIANCE_MATRIX_VERSION,
    SARO_ENGINE_VERSION,
    SARoEngine,
    _COMPLIANCE_TRIGGERS,
    _RISK_SIGNALS,
)
from models import AIIncident, Audit, Iso42001Document, NISTControl, ScanReport, User
from services.evf_validation_status_service import get_all_framework_statuses
from schemas import (
    AppliedRuleOut,
    AuditReportOut,
    EngineIntegrityOut,
    FixedDeltaOut,
    IncidentCorpusStatsOut,
    Iso42001DocumentOut,
    MITCoverageOut,
    NistCoverageReportOut,
    NistSubcategoryOut,
    SimilarIncidentOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _get_report_or_404(
    audit_id: uuid.UUID, tenant_id: uuid.UUID, db: Session
) -> dict[str, Any]:
    """Fetch and return the stored report JSON, raising 404 if missing."""
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    if not audit.report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet generated"
        )
    return audit.report.report_json


@router.get(
    "/summary",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Aggregate reporting statistics for the current tenant",
)
def reports_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """
    Returns aggregate metrics across all completed audits for the tenant:
      - total audits, completed, failed
      - average MIT coverage score
      - average risk score
      - fixed-delta distribution
      - top triggered domains
    """
    rows = (
        db.query(Audit, ScanReport)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .filter(
            Audit.tenant_id == current_user.tenant_id,
            Audit.status == "completed",
        )
        .all()
    )

    total = len(rows)
    if total == 0:
        return {
            "total_audits": 0,
            "completed": 0,
            "failed": 0,
            "avg_mit_coverage": None,
            "avg_risk_score": None,
            "avg_fixed_delta": None,
        }

    mit_scores = [r.mit_coverage_score for _, r in rows if r and r.mit_coverage_score is not None]
    risk_scores = [r.overall_risk_score for _, r in rows if r and r.overall_risk_score is not None]
    deltas = [r.fixed_delta for _, r in rows if r and r.fixed_delta is not None]

    # Collect all applied rules across audits
    all_frameworks: list[str] = []
    all_domains: list[str] = []
    for _, r in rows:
        if r and r.report_json:
            for rule in r.report_json.get("applied_rules", []):
                all_frameworks.append(rule.get("framework", ""))
            for gate in r.report_json.get("gates", []):
                if gate.get("gate_id") == 3:
                    for domain, cnt in gate.get("details", {}).get("domain_counts", {}).items():
                        if cnt > 0:
                            all_domains.append(domain)

    # Top-5 frameworks
    from collections import Counter

    top_frameworks = dict(Counter(all_frameworks).most_common(5))
    top_domains = dict(Counter(all_domains).most_common(5))

    # Count failed audits
    failed_count = (
        db.query(func.count(Audit.id))
        .filter(Audit.tenant_id == current_user.tenant_id, Audit.status == "failed")
        .scalar()
        or 0
    )

    # FR-EVF-11: stamp live validation status on every summary response so
    # dashboards and reports always display the correct EVF tier label.
    evf_statuses = get_all_framework_statuses(db)

    return {
        "total_audits": total,
        "completed": total,
        "failed": failed_count,
        "avg_mit_coverage": round(sum(mit_scores) / len(mit_scores), 4) if mit_scores else None,
        "avg_risk_score": round(sum(risk_scores) / len(risk_scores), 4) if risk_scores else None,
        "avg_fixed_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
        "top_triggered_frameworks": top_frameworks,
        "top_triggered_domains": top_domains,
        # EVF validation labels — Tier 1/2/3 per framework (FR-EVF-11, FR-EVF-16)
        "evf_validation_status": {
            s["framework"]: {
                "tier":  s["tier"],
                "label": s["label"],
                "qco_reference": s["qco_reference"],
                "expires_in_days": s["expires_in_days"],
            }
            for s in evf_statuses
        },
    }


@router.get(
    "/{audit_id}",
    response_model=AuditReportOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
)
def get_full_report(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditReportOut:
    data = _get_report_or_404(audit_id, current_user.tenant_id, db)
    # FR-EVF-11: embed live EVF validation labels so every exported report
    # carries the correct Tier 1/2/3 stamp at the time of generation.
    evf_statuses = get_all_framework_statuses(db)
    data["evf_validation_status"] = {
        s["framework"]: {
            "tier":  s["tier"],
            "label": s["label"],
            "qco_reference": s["qco_reference"],
            "expires_in_days": s["expires_in_days"],
        }
        for s in evf_statuses
    }
    return AuditReportOut.model_validate(data)


@router.get(
    "/{audit_id}/mit",
    response_model=MITCoverageOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="MIT Risk Coverage detail for one audit",
)
def get_mit_coverage(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MITCoverageOut:
    data = _get_report_or_404(audit_id, current_user.tenant_id, db)
    return MITCoverageOut.model_validate(data["mit_coverage"])


@router.get(
    "/{audit_id}/delta",
    response_model=FixedDeltaOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Fixed vs Not-Fixed delta for one audit",
)
def get_fixed_delta(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FixedDeltaOut:
    data = _get_report_or_404(audit_id, current_user.tenant_id, db)
    return FixedDeltaOut.model_validate(data["fixed_delta"])


@router.get(
    "/{audit_id}/rules",
    response_model=list[AppliedRuleOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Applied compliance rules for one audit",
)
def get_applied_rules(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AppliedRuleOut]:
    data = _get_report_or_404(audit_id, current_user.tenant_id, db)
    return [AppliedRuleOut.model_validate(r) for r in data.get("applied_rules", [])]


@router.get(
    "/{audit_id}/incidents",
    response_model=list[SimilarIncidentOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Similar historical incidents for one audit",
)
def get_similar_incidents(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SimilarIncidentOut]:
    data = _get_report_or_404(audit_id, current_user.tenant_id, db)
    return [SimilarIncidentOut.model_validate(i) for i in data.get("similar_incidents", [])]


# ─────────────────────────────────────────────────────────────────────────────
# SARO-004: NIST AI RMF coverage report
# ─────────────────────────────────────────────────────────────────────────────

# PT-007: version of the curated coverage map. Bump on any curated-status change.
NIST_COVERAGE_MAP_VERSION = "v1.0"


def _engine_mapped_subcategories() -> set[str]:
    """PT-007: the subcategories SARO *actually* generates automated evidence for,
    derived mechanically from _COMPLIANCE_TRIGGERS (not asserted in a static table).

    A subcategory is 'mapped' iff at least one active compliance trigger carries its
    nist_subcategory_id. Counted once per subcategory even if multiple triggers map to it.
    """
    return {
        t["nist_subcategory_id"].strip()
        for triggers in _COMPLIANCE_TRIGGERS.values()
        for t in triggers
        if t.get("nist_subcategory_id")
    }


# Curated baseline status for all 68 NIST AI RMF 1.0 subcategory IDs. The "mapped"
# rows are kept in lock-step with _engine_mapped_subcategories() (pinned by
# tests/test_pt007_nist_coverage.py); "partial"/"requires_human_assessment" follow
# the rubric in docs/nist-coverage-rubric.md.
_NIST_COVERAGE_MAP: dict[str, str] = {
    # GOVERN function
    "GOVERN 1.1": "partial", "GOVERN 1.2": "requires_human_assessment",
    "GOVERN 1.3": "requires_human_assessment", "GOVERN 1.4": "requires_human_assessment",
    "GOVERN 1.5": "requires_human_assessment", "GOVERN 1.6": "mapped",
    "GOVERN 1.7": "requires_human_assessment",
    "GOVERN 2.1": "requires_human_assessment", "GOVERN 2.2": "requires_human_assessment",
    "GOVERN 3.1": "requires_human_assessment", "GOVERN 3.2": "requires_human_assessment",
    "GOVERN 4.1": "requires_human_assessment", "GOVERN 4.2": "mapped",
    "GOVERN 5.1": "requires_human_assessment", "GOVERN 5.2": "requires_human_assessment",
    "GOVERN 6.1": "requires_human_assessment", "GOVERN 6.2": "partial",
    # MAP function
    "MAP 1.1": "mapped", "MAP 1.2": "requires_human_assessment",
    "MAP 1.3": "requires_human_assessment", "MAP 1.4": "requires_human_assessment",
    "MAP 1.5": "mapped", "MAP 1.6": "mapped",
    "MAP 2.1": "mapped", "MAP 2.2": "requires_human_assessment",
    "MAP 2.3": "mapped", "MAP 3.1": "requires_human_assessment",
    "MAP 3.2": "requires_human_assessment", "MAP 3.3": "requires_human_assessment",
    "MAP 3.4": "requires_human_assessment", "MAP 3.5": "requires_human_assessment",
    "MAP 4.1": "requires_human_assessment", "MAP 4.2": "requires_human_assessment",
    "MAP 5.1": "partial", "MAP 5.2": "requires_human_assessment",
    # MEASURE function
    "MEASURE 1.1": "requires_human_assessment", "MEASURE 1.2": "requires_human_assessment",
    "MEASURE 1.3": "requires_human_assessment",
    "MEASURE 2.1": "mapped", "MEASURE 2.2": "requires_human_assessment",
    "MEASURE 2.3": "requires_human_assessment", "MEASURE 2.4": "requires_human_assessment",
    "MEASURE 2.5": "mapped", "MEASURE 2.6": "mapped",
    "MEASURE 2.7": "requires_human_assessment", "MEASURE 2.8": "requires_human_assessment",
    "MEASURE 2.9": "requires_human_assessment", "MEASURE 2.10": "requires_human_assessment",
    "MEASURE 2.11": "partial", "MEASURE 2.12": "requires_human_assessment",
    "MEASURE 2.13": "requires_human_assessment", "MEASURE 3.1": "requires_human_assessment",
    "MEASURE 3.2": "requires_human_assessment", "MEASURE 3.3": "requires_human_assessment",
    "MEASURE 4.1": "requires_human_assessment", "MEASURE 4.2": "requires_human_assessment",
    # MANAGE function
    "MANAGE 1.1": "requires_human_assessment", "MANAGE 1.2": "requires_human_assessment",
    "MANAGE 1.3": "mapped", "MANAGE 1.4": "requires_human_assessment",
    "MANAGE 2.1": "requires_human_assessment", "MANAGE 2.2": "requires_human_assessment",
    "MANAGE 2.3": "requires_human_assessment", "MANAGE 2.4": "requires_human_assessment",
    "MANAGE 3.1": "requires_human_assessment", "MANAGE 3.2": "requires_human_assessment",
    "MANAGE 4.1": "mapped", "MANAGE 4.2": "requires_human_assessment",
}


@router.get(
    "/nist-coverage",
    response_model=NistCoverageReportOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="NIST AI RMF subcategory coverage report (SARO-004)",
)
def get_nist_coverage(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NistCoverageReportOut:
    """
    Returns coverage status for all 72 NIST AI RMF 1.0 subcategory outcomes.

    Status values:
      mapped                   — SARO generates automated evidence for this subcategory
      partial                  — limited automated evidence; human review recommended
      not_covered              — no DB record found for this subcategory
      requires_human_assessment — no automated text-analysis signal possible
    """
    # Load DB records for version and description enrichment
    nist_rows: dict[str, NISTControl] = {}
    try:
        for row in db.query(NISTControl).all():
            if row.subcategory_id:
                nist_rows[row.subcategory_id.strip()] = row
    except Exception:
        pass

    # PT-007: "mapped" is derived mechanically from the engine's triggers, not asserted.
    derived_mapped = _engine_mapped_subcategories()

    subcategories: list[NistSubcategoryOut] = []
    for sub_id, curated_status in _NIST_COVERAGE_MAP.items():
        row = nist_rows.get(sub_id)
        function_name = sub_id.split(" ")[0] if " " in sub_id else sub_id
        version = (row.version or "AI RMF 1.0") if row else "AI RMF 1.0"
        status = "mapped" if sub_id in derived_mapped else curated_status
        subcategories.append(NistSubcategoryOut(
            subcategory_id=sub_id,
            function_name=function_name,
            description=row.description if row else None,
            status=status,
            version=version,
        ))

    counts = Counter(s.status for s in subcategories)
    mapped_count = counts.get("mapped", 0)
    total = len(subcategories)
    return NistCoverageReportOut(
        engine_version=SARO_ENGINE_VERSION,
        coverage_map_version=NIST_COVERAGE_MAP_VERSION,
        automated_summary=f"{mapped_count} of {total} subcategories automated, map {NIST_COVERAGE_MAP_VERSION}",
        total_subcategories=total,
        mapped_count=mapped_count,
        partial_count=counts.get("partial", 0),
        not_covered_count=counts.get("not_covered", 0),
        requires_human_assessment_count=counts.get("requires_human_assessment", 0),
        subcategories=subcategories,
        generated_at=datetime.now(tz=timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SARO-005: ISO 42001 Annex A document generator
# ─────────────────────────────────────────────────────────────────────────────

_ISO_ANNEX_TEMPLATE = """\
# ISO 42001 Annex A — AI Management System Technical Documentation
## Generated by SARO v{engine_version}
**Audit ID:** {audit_id}
**Dataset:** {dataset_name}
**Generated:** {generated_at}
**Status:** [AUTO] Evidence auto-populated from SARO audit results.

---
> *This report is audit evidence generated by SARO v{engine_version}. It does not constitute
> regulatory certification, legal advice, or compliance approval. Human review and sign-off by
> qualified personnel is required before any regulatory submission.*

---

## A.6 — AI System Lifecycle Safety
[AUTO] Risk findings from Gate 3 AI System Safety domain:
{safety_findings}

## A.7 — Data Management
[AUTO] PII/data findings from Gate 3 Privacy & Security domain:
{privacy_findings}

## A.8 — Socioeconomic Impact
[AUTO] Socioeconomic signals detected:
{socioeconomic_findings}

## A.9.3 — Fairness
[AUTO] Gate 2 fairness analysis result: **{fairness_status}**
{fairness_details}

## A.10 — Responsible Use
[AUTO] Malicious use signals detected:
{malicious_findings}

## Risk Findings Summary
[AUTO] Overall risk score: **{overall_risk_score}**
[AUTO] MIT coverage score: **{mit_coverage}**
[AUTO] Confidence score: **{confidence_score}**

## Applied Compliance Rules
[AUTO] The following framework controls were triggered:
{applied_rules}

## Remediation Status
[AUTO] Open remediations: **{open_remediations}**
[AUTO] Remediated items: **{remediated_count}**

## Annex VIII — Technical Documentation Fields
[HUMAN REVIEW REQUIRED] System description and intended purpose
[HUMAN REVIEW REQUIRED] Training data provenance and data governance statement
[HUMAN REVIEW REQUIRED] Performance metrics and evaluation results
[HUMAN REVIEW REQUIRED] Post-market monitoring plan
[HUMAN REVIEW REQUIRED] Certification authority sign-off

## NOT COVERED BY SARO — Manual Evidence Required
SARO produces output-level risk evidence only. The following ISO/IEC 42001 clauses are
**NOT COVERED BY SARO** and require manual evidence collected by the organisation; SARO
*supports* but does *not replace* this work:
- Clause 4 — Context of the organisation (AIMS scope, interested parties)
- Clause 5 — Leadership and AI policy
- Clause 6 — Planning (AI risk & impact assessment process, objectives)
- Clause 7 — Support (resources, competence, awareness, documented information control)
- Clause 8 — Operational planning beyond output evaluation
- Clause 9 — Performance evaluation (internal audit, management review)
- Clause 10 — Improvement (nonconformity, corrective action)

## Provenance
[AUTO] Engine version: {engine_version}
[AUTO] Rule-pack hash (SHA-256): {rule_pack_hash}
[AUTO] Document content hash is recorded on the immutable Iso42001Document record.

## Evidence References
[AUTO] SARO Audit ID: {audit_id}
[AUTO] TRACE record endpoint: /api/v1/traces/{audit_id}
[AUTO] Sample findings: /api/v1/traces/{audit_id}/samples
"""


def _extract_domain_findings(report_data: dict, domain: str) -> str:
    gates = report_data.get("gates", [])
    for gate in gates:
        if gate.get("gate_id") == 3:
            counts = gate.get("details", {}).get("domain_counts", {})
            cnt = counts.get(domain, 0)
            if cnt > 0:
                return f"[AUTO] {cnt} sample(s) flagged in '{domain}' domain."
    return "[AUTO] No signals detected."


@router.post(
    "/{audit_id}/iso42001-annex",
    response_model=Iso42001DocumentOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Generate ISO 42001 Annex A technical documentation (SARO-005)",
)
def generate_iso42001_annex(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    format: str = Query(default="markdown", pattern="^(markdown)$"),
) -> Iso42001DocumentOut:
    """
    Generate a structured ISO 42001 Annex A document pre-populated with audit evidence.

    Fields marked [AUTO] are populated from SARO findings.
    Fields marked [HUMAN REVIEW REQUIRED] must be completed by qualified personnel.
    Each generation creates an immutable versioned record.

    Access restricted to compliance_lead and admin personas.
    """
    # Persona access check: only compliance_lead and admin may generate
    allowed_personas = {"compliance_lead", "admin"}
    if (
        current_user.role != "super_admin"
        and current_user.persona_role not in allowed_personas
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ISO 42001 document generation requires compliance_lead or admin persona.",
        )

    report_data = _get_report_or_404(audit_id, current_user.tenant_id, db)

    # PT-006 edge: refuse to emit a thin document from an audit with no evaluated
    # gates — better a minimum-evidence error than a hollow Annex doc.
    if not report_data.get("gates"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Insufficient audit evidence to generate ISO 42001 Annex documentation — "
                "this audit has no evaluated gates. Run a complete audit first."
            ),
        )

    # Determine next version number for this audit
    existing_versions = (
        db.query(Iso42001Document)
        .filter(Iso42001Document.audit_id == audit_id)
        .count()
    )
    next_version = existing_versions + 1

    gate2 = next((g for g in report_data.get("gates", []) if g.get("gate_id") == 2), {})
    fairness_status = gate2.get("status", "unknown").upper()
    fairness_detail = gate2.get("details", {})
    fairness_details = (
        f"Parity gap: {fairness_detail.get('statistical_parity_difference', 'N/A')} "
        f"(warn >0.10, fail >0.20)"
        if fairness_detail.get("statistical_parity_difference") is not None
        else "Demographic labels not supplied — full parity analysis unavailable."
    )

    applied_rules_text = "\n".join(
        f"- {r.get('framework')} {r.get('rule_id')}: {r.get('title')}"
        for r in report_data.get("applied_rules", [])
    ) or "None triggered."

    content = _ISO_ANNEX_TEMPLATE.format(
        engine_version=SARO_ENGINE_VERSION,
        audit_id=str(audit_id),
        dataset_name=report_data.get("dataset_name") or "Unknown",
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
        safety_findings=_extract_domain_findings(report_data, "AI System Safety"),
        privacy_findings=_extract_domain_findings(report_data, "Privacy & Security"),
        socioeconomic_findings=_extract_domain_findings(report_data, "Socioeconomic & Environmental"),
        fairness_status=fairness_status,
        fairness_details=fairness_details,
        malicious_findings=_extract_domain_findings(report_data, "Malicious Use"),
        overall_risk_score=report_data.get("bayesian_scores", {}).get("overall", "N/A"),
        mit_coverage=report_data.get("mit_coverage", {}).get("score", "N/A"),
        confidence_score=report_data.get("confidence_score", "N/A"),
        applied_rules=applied_rules_text,
        open_remediations=len(report_data.get("remediations", [])),
        remediated_count=0,
        rule_pack_hash=report_data.get("rule_pack_hash") or SARoEngine._compute_rule_pack_hash(),
    )

    content_hash = hashlib.sha256(content.encode()).hexdigest()

    doc = Iso42001Document(
        audit_id=audit_id,
        generated_by_user_id=current_user.id,
        format=format,
        content=content,
        content_hash=content_hash,
        version=next_version,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info(
        "ISO 42001 Annex A document v%d generated for audit %s by %s",
        next_version, audit_id, current_user.email,
    )
    return Iso42001DocumentOut.model_validate(doc)


# ─────────────────────────────────────────────────────────────────────────────
# SARO-006: Engine integrity
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/engine/integrity",
    response_model=EngineIntegrityOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Current engine version and rule pack integrity hash (SARO-006)",
)
def get_engine_integrity(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EngineIntegrityOut:
    """
    Returns the current engine version, rule pack SHA-256 hash, and compliance
    matrix version.  An external auditor can use this to verify that the engine
    config has not changed since a specific audit was run.
    """
    import json as _json
    payload = {
        "risk_signals": {
            domain: {"keywords": sorted(sigs["keywords"]), "weight": sigs["weight"]}
            for domain, sigs in _RISK_SIGNALS.items()
        },
        "compliance_triggers": {
            domain: [{"framework": t["framework"], "rule_id": t["rule_id"]} for t in triggers]
            for domain, triggers in _COMPLIANCE_TRIGGERS.items()
        },
    }
    canonical = _json.dumps(payload, sort_keys=True, ensure_ascii=True)
    rule_pack_hash = hashlib.sha256(canonical.encode()).hexdigest()

    return EngineIntegrityOut(
        engine_version=SARO_ENGINE_VERSION,
        rule_pack_hash=rule_pack_hash,
        compliance_matrix_version=COMPLIANCE_MATRIX_VERSION,
        checked_at=datetime.now(tz=timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SARO-007: Incident corpus statistics
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/incident-corpus-stats",
    response_model=IncidentCorpusStatsOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="AI incident corpus quality statistics (SARO-007)",
)
def get_incident_corpus_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IncidentCorpusStatsOut:
    """
    Returns quality and currency statistics for the AI incident similarity corpus.

    Governance teams use this to assess whether incident similarity scores are
    statistically meaningful given the corpus size and recency.
    """
    try:
        rows = db.query(AIIncident).all()
    except Exception:
        rows = []

    total = len(rows)
    fixed_count = sum(1 for r in rows if r.is_fixed)
    pct_fixed = round(fixed_count / total, 4) if total > 0 else 0.0

    category_counts = Counter(r.category for r in rows if r.category)
    harm_type_counts = Counter(r.harm_type for r in rows if r.harm_type)
    source_counts = Counter(r.source for r in rows if r.source)

    dates = [r.date for r in rows if r.date]
    dates_sorted = sorted(dates) if dates else []

    corpus_datetimes = [r.created_at for r in rows if r.created_at]
    last_update = max(corpus_datetimes) if corpus_datetimes else None

    # PT-011: flag a stale (or empty) corpus instead of silently matching against it.
    stale = False
    staleness_message: str | None = None
    if total == 0:
        stale = True
        staleness_message = "Incident corpus is empty — similarity matches are not meaningful."
    elif last_update is not None:
        age = datetime.now(tz=timezone.utc) - last_update
        if age > timedelta(days=365):
            stale = True
            staleness_message = (
                f"Incident corpus has not been refreshed in {age.days} days (>12 months) — "
                "treat similarity matches with caution."
            )

    return IncidentCorpusStatsOut(
        total_incidents=total,
        count_by_category=dict(category_counts),
        count_by_harm_type=dict(harm_type_counts),
        count_by_source=dict(source_counts),
        date_range_earliest=dates_sorted[0] if dates_sorted else None,
        date_range_latest=dates_sorted[-1] if dates_sorted else None,
        pct_fixed=pct_fixed,
        last_corpus_update=last_update,
        minimum_similarity_threshold=SARoEngine.SIMILARITY_THRESHOLD,
        corpus_stale=stale,
        staleness_message=staleness_message,
    )
