"""STORY-309 check 1 — Groundedness / hallucination.

Flags factual claims in the output that are not supported by the retrieved
context. The design allows an optional LLM-as-judge pass (the same disclosed,
off-by-default Anthropic pattern used elsewhere in SARO — see the external-model
disclosure in COMPLIANCE_CLAIMS_MATRIX). With no provider key configured the
check is a deterministic, keyword/overlap heuristic and makes zero external
calls — the default.
"""

from __future__ import annotations

import re

from grc.checks.base import CheckContext, CheckFinding

CHECK_NAME = "groundedness"

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


def _content_words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOPWORDS}


def _sentence_supported(sentence: str, context_words: set[str]) -> bool:
    words = _content_words(sentence)
    if not words:
        return True
    overlap = len(words & context_words) / len(words)
    return overlap >= 0.5


def groundedness_check(ctx: CheckContext) -> CheckFinding:
    output = (ctx.output_text or "").strip()
    context = (ctx.retrieved_context or "").strip()

    if not output:
        return CheckFinding(
            check=CHECK_NAME,
            status="pass",
            detail="No output text to ground.",
            facts="Output is empty.",
            assessment="Nothing to verify.",
        )

    context_words = _content_words(context)
    unsupported: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(output):
        s = sentence.strip()
        if not s:
            continue
        # Only scrutinize sentences that assert a concrete claim.
        if _CLAIM_MARKERS.search(s) and not _sentence_supported(s, context_words):
            unsupported.append(s)

    if unsupported:
        return CheckFinding(
            check=CHECK_NAME,
            status="concern",
            detail=f"{len(unsupported)} claim(s) not supported by retrieved context.",
            likelihood=4,
            impact=4,
            remediation="Add a grounding citation from retrieved context, or remove the unsupported claim.",
            facts="Unsupported claim(s): " + " | ".join(unsupported[:3]),
            assessment="Claims are not corroborated by the supplied context (possible hallucination).",
            framework_mapping=[
                {
                    "framework": "NIST_AI_RMF",
                    "identifier": "MEASURE",
                    "status": "VERIFIED",
                }
            ],
        )

    return CheckFinding(
        check=CHECK_NAME,
        status="pass",
        detail="All concrete claims are supported by retrieved context.",
        facts="Claims overlap with retrieved context.",
        assessment="No unsupported factual claims detected.",
    )
