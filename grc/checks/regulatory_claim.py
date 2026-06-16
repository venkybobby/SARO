"""STORY-309 check 5 — Regulatory-claim accuracy (built in-house).

Routes any compliance / legal / medical / financial claim through STORY-317
citation verification. A framework clause that does not resolve is flagged
UNVERIFIED; a bare compliance assertion with no citation is also flagged (it
cannot be substantiated). This is the check that defends against the
fabricated-citation failure mode.
"""

from __future__ import annotations

import re

from grc.checks.base import CheckContext, CheckFinding
from grc.citation import UNVERIFIED, verify_citation

CHECK_NAME = "regulatory_claim_accuracy"

# Signals that the output is making a compliance/legal/medical/financial claim.
_CLAIM_SIGNALS = re.compile(
    r"\b(compliant|compliance|certified|certif\w+|regulation|regulatory|"
    r"lawful|legal|guarantee\w*|FDA|HIPAA|approved by|diagnos\w+|"
    r"investment advice|guaranteed returns?|tax[- ]deductible)\b",
    re.IGNORECASE,
)

# Framework citation patterns → (framework, normalized identifier).
_CITATION_PATTERNS = [
    (
        re.compile(r"EU\s*AI\s*Act\s*Art(?:icle|\.)?\s*\.?\s*(\d+)", re.IGNORECASE),
        lambda m: ("EU_AI_ACT", f"Art.{m.group(1)}"),
    ),
    (
        re.compile(
            r"\bISO(?:/IEC)?\s*42001\b.*?(?:Clause|Cl\.?)\s*(\d+)", re.IGNORECASE
        ),
        lambda m: ("ISO_42001", f"Cl.{m.group(1)}"),
    ),
    (
        re.compile(
            r"\bNIST\b.*?\b(GOVERN|MAP|MEASURE|MANAGE)(?:-(\d+\.\d+))?", re.IGNORECASE
        ),
        lambda m: (
            "NIST_AI_RMF",
            m.group(1).upper() + (f"-{m.group(2)}" if m.group(2) else ""),
        ),
    ),
]


def _extract_citations(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for pat, build in _CITATION_PATTERNS:
        for m in pat.finditer(text):
            found.append(build(m))
    return found


def regulatory_claim_check(ctx: CheckContext) -> CheckFinding:
    text = ctx.output_text or ""
    makes_claim = bool(_CLAIM_SIGNALS.search(text))
    citations = _extract_citations(text)

    if not makes_claim and not citations:
        return CheckFinding(
            check=CHECK_NAME,
            status="pass",
            detail="No compliance/legal/medical/financial claim detected.",
            facts="No regulatory claim signals or citations found.",
            assessment="Nothing to verify.",
        )

    # Route every cited clause through STORY-317.
    mappings: list[dict] = []
    unverified: list[str] = []
    for framework, identifier in citations:
        result = verify_citation(framework, identifier)
        mappings.append(
            {"framework": framework, "identifier": identifier, "status": result.status}
        )
        if result.status == UNVERIFIED:
            unverified.append(f"{framework} {identifier}")

    # A claim with no citation cannot be substantiated → route as UNVERIFIED.
    claim_without_citation = makes_claim and not citations
    if claim_without_citation:
        mappings.append(
            {"framework": "UNSPECIFIED", "identifier": None, "status": UNVERIFIED}
        )

    if unverified or claim_without_citation:
        if claim_without_citation:
            detail = (
                "Compliance/legal claim made without a verifiable framework citation."
            )
            facts = "Claim asserted; no resolvable citation present."
        else:
            detail = f"Unverifiable citation(s): {', '.join(unverified)}."
            facts = f"Citations that did not resolve: {unverified}."
        return CheckFinding(
            check=CHECK_NAME,
            status="concern",
            detail=detail,
            likelihood=4,
            impact=4,
            remediation="Cite a clause that resolves in the framework crosswalk, or soften the claim to evidence-only language.",
            facts=facts,
            assessment="Regulatory claim is not substantiated by a verified citation.",
            framework_mapping=mappings,
        )

    return CheckFinding(
        check=CHECK_NAME,
        status="pass",
        detail="All cited framework clauses resolve to verified entries.",
        facts=f"Verified citations: {[m['identifier'] for m in mappings]}.",
        assessment="Regulatory citations are verifiable.",
        framework_mapping=mappings,
    )
