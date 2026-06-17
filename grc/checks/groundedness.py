"""STORY-335 — Runtime groundedness via non-LLM methods (supersedes the
STORY-309 LLM-as-judge sub-check).

Flags concrete factual claims in the output that are not supported by the
``retrieved_context``. The method is deliberately **non-LLM and inspectable**:
retrieval-overlap + citation matching. Each output claim is matched against the
individual spans (sentences) of the retrieved context; a claim is *supported*
when some span shares enough content words with it, and every *unsupported*
claim cites the nearest span it failed to match — so an auditor can see exactly
what evidence was (and wasn't) there.

This runs in the product path and makes **zero** calls to any third-party hosted
model API — the locked claim enforced by STORY-336. No self-hosted model is used
either; the check is pure string/overlap analysis, so there is no model
dependency to record. Offline LLM-as-judge labeling lives in the QA lab
(STORY-338), never here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from grc.checks.base import CheckContext, CheckFinding

CHECK_NAME = "groundedness"

# A claim is "supported" when it shares at least this fraction of its content
# words with a single context span.
SUPPORT_THRESHOLD = 0.5

_WORD = re.compile(r"[A-Za-z0-9]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Words that signal a concrete factual claim worth grounding.
_CLAIM_MARKERS = re.compile(
    r"\b(\d+%?|all|always|never|cures?|guarantees?|proven|studies show|"
    r"according to|the only|100%)\b",
    re.IGNORECASE,
)
_STOPWORDS = frozenset(
    "the a an of to in on for and or is are was were be been with that this it as by".split()
)


@dataclass(frozen=True)
class ClaimAssessment:
    """One concrete output claim and the context span it was matched against."""

    claim: str
    supported: bool
    nearest_span: str  # the context span with the highest overlap (the citation)
    overlap: float  # fraction of the claim's content words found in that span


@dataclass(frozen=True)
class GroundednessReport:
    """The per-claim citation-matching result for one output."""

    assessments: list[ClaimAssessment]

    @property
    def supported(self) -> list[ClaimAssessment]:
        return [a for a in self.assessments if a.supported]

    @property
    def unsupported(self) -> list[ClaimAssessment]:
        return [a for a in self.assessments if not a.supported]


def _content_words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOPWORDS}


def _spans(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _best_span(claim_words: set[str], spans: list[str]) -> tuple[str, float]:
    """Return the context span best matching ``claim_words`` and its overlap.

    Citation matching: a claim is grounded by the single best-matching source
    span, not by the union of the whole context (which could stitch support
    together from unrelated sentences). Ties keep the earliest span (``>``, not
    ``>=``) so the citation is deterministic. When spans exist but none overlap,
    the first non-empty span is still cited so an unsupported claim always points
    at the context it failed to match; only a genuinely empty context yields "".
    """
    best_span, best_overlap = "", 0.0
    for span in spans:
        span_words = _content_words(span)
        if not span_words:
            continue
        if not best_span:  # fallback: cite the nearest span even at zero overlap
            best_span = span
        overlap = len(claim_words & span_words) / len(claim_words)
        if overlap > best_overlap:
            best_span, best_overlap = span, overlap
    return best_span, best_overlap


def assess_groundedness(
    output: str, context: str, *, threshold: float = SUPPORT_THRESHOLD
) -> GroundednessReport:
    """Assess each concrete output claim against the retrieved-context spans."""
    spans = _spans(context or "")
    assessments: list[ClaimAssessment] = []
    for sentence in _spans(output or ""):
        # Only scrutinise sentences that assert a concrete, groundable claim.
        if not _CLAIM_MARKERS.search(sentence):
            continue
        claim_words = _content_words(sentence)
        if not claim_words:
            continue
        span, overlap = _best_span(claim_words, spans)
        assessments.append(
            ClaimAssessment(
                claim=sentence,
                supported=overlap >= threshold,
                nearest_span=span,
                overlap=overlap,
            )
        )
    return GroundednessReport(assessments=assessments)


def _cite(a: ClaimAssessment) -> str:
    span = a.nearest_span or "(no matching context span)"
    return f"{a.claim!r} (nearest context span: {span!r}, overlap {a.overlap:.0%})"


def groundedness_check(ctx: CheckContext) -> CheckFinding:
    output = (ctx.output_text or "").strip()
    if not output:
        return CheckFinding(
            check=CHECK_NAME,
            status="pass",
            detail="No output text to ground.",
            facts="Output is empty.",
            assessment="Nothing to verify.",
        )

    report = assess_groundedness(output, ctx.retrieved_context or "")
    unsupported = report.unsupported

    if unsupported:
        return CheckFinding(
            check=CHECK_NAME,
            status="concern",
            detail=f"{len(unsupported)} claim(s) not supported by retrieved context.",
            likelihood=4,
            impact=4,
            remediation=(
                "Add a grounding citation from retrieved context for each flagged "
                "claim, or remove the unsupported claim."
            ),
            facts="Unsupported claim(s): "
            + " | ".join(_cite(a) for a in unsupported[:3]),
            assessment=(
                "Claims are not corroborated by any single span of the supplied "
                "context (possible hallucination); each is shown with the nearest "
                "span it failed to match."
            ),
            framework_mapping=[
                {
                    "framework": "NIST_AI_RMF",
                    "identifier": "MEASURE",
                    "status": "VERIFIED",
                }
            ],
        )

    supported = report.supported
    facts = (
        "Each concrete claim traces to a supporting context span."
        if supported
        else "No concrete factual claims required grounding."
    )
    return CheckFinding(
        check=CHECK_NAME,
        status="pass",
        detail="All concrete claims are supported by retrieved context.",
        facts=facts,
        assessment="No unsupported factual claims detected.",
    )
