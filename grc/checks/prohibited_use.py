"""STORY-309 check 4 — Prohibited / out-of-scope use.

Checks the output against the system's authorized ``purpose`` from the registry
(STORY-301). An output that plainly serves a use outside the authorized purpose
is flagged. The heuristic: if a purpose is declared and the output shares none of
its content terms, the output is out-of-scope.
"""

from __future__ import annotations

import re

from grc.checks.base import CheckContext, CheckFinding

CHECK_NAME = "prohibited_use"

_WORD = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = frozenset(
    "the a an of to in on for and or is are be with that this it as by from your you "
    "please can will would should could about into out".split()
)
# Substantive output worth scope-checking (avoid flagging trivial replies).
_MIN_OUTPUT_WORDS = 5


def _content_words(text: str) -> set[str]:
    return {
        w.lower()
        for w in _WORD.findall(text)
        if w.lower() not in _STOPWORDS and len(w) > 2
    }


def prohibited_use_check(ctx: CheckContext) -> CheckFinding:
    purpose = (ctx.registry_purpose or "").strip()
    output = (ctx.output_text or "").strip()

    if not purpose:
        return CheckFinding(
            check=CHECK_NAME,
            status="pass",
            detail="No authorized purpose on record; scope check not applicable.",
            facts="registry_purpose not provided.",
            assessment="Cannot assess scope without a declared purpose.",
        )

    purpose_words = _content_words(purpose)
    output_words = _content_words(output)
    if len(output_words) < _MIN_OUTPUT_WORDS:
        return CheckFinding(
            check=CHECK_NAME,
            status="pass",
            detail="Output too short to assess scope.",
            facts="Output below minimum length for scope assessment.",
            assessment="Insufficient content to flag out-of-scope use.",
        )

    if purpose_words and purpose_words.isdisjoint(output_words):
        return CheckFinding(
            check=CHECK_NAME,
            status="concern",
            detail="Output shares no terms with the system's authorized purpose.",
            likelihood=3,
            impact=4,
            remediation="Confirm the output is within the authorized purpose; restrict the system or update the registered purpose.",
            facts=f"Authorized purpose: {purpose!r}; output shares no content terms with it.",
            assessment="Output appears to serve a use outside the authorized purpose.",
            framework_mapping=[
                {"framework": "ISO_42001", "identifier": "A.6", "status": "VERIFIED"}
            ],
        )

    return CheckFinding(
        check=CHECK_NAME,
        status="pass",
        detail="Output is consistent with the authorized purpose.",
        facts="Output overlaps with the authorized purpose terms.",
        assessment="No out-of-scope-use signal.",
    )
