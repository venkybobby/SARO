"""STORY-338 — Offline LLM-as-judge labeling harness (QA lab only).

The harness pre-labels / verifies validation samples with an LLM-as-judge and
then **requires a human adjudication** before any label enters the corpus. Every
labeled item carries full provenance (source, LLM suggestion, human decision,
labeler, timestamp). For synthetic items (T1) with a known injected defect, the
suggestion is compared to the known label and the delta is recorded.

Isolation (STORY-336): this lives in the ``qa_lab`` package, outside the product
path, and must never be imported by product/runtime code. The actual provider
call (``default_anthropic_suggester``) is the sole sanctioned external-model use
and runs only here, offline, on **PII-redacted** sample fragments.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

# A judge suggester: given a PII-redacted sample fragment and a domain, return a
# (label, rationale) suggestion. Injectable so the harness is testable offline.
Suggester = Callable[[str, str], "tuple[str, str]"]

# Best-effort PII redaction applied before anything leaves this process to a
# judge. This is an offline QA-lab control over T1 synthetic and T3
# *already-anonymized* samples — it deliberately does NOT attempt names,
# addresses, or DOB (those need an NER pass, out of scope). Residual coverage is
# documented in the story; broaden the patterns here as new classes are needed.
_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email
    re.compile(r"\b\d{3}[ .-]?\d{2}[ .-]?\d{4}\b"),  # US SSN (space/dot/hyphen)
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),  # IPv4
    re.compile(r"\b(?:\+?\d[\d ().-]{7,}\d)\b"),  # phone-ish
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),  # card-ish
)


def redact_pii(text: str) -> str:
    """Redact obvious PII so no raw identifier is sent to the judge.

    Best-effort only (regex, no NER) — see ``_PII_PATTERNS``. The validation
    corpus is built from synthetic and already-anonymized samples; this is a
    defence-in-depth backstop, not a guarantee of complete de-identification.
    """
    out = text
    for pattern in _PII_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


class AdjudicationRequired(RuntimeError):
    """Raised when a corpus commit is attempted with un-adjudicated items."""


@dataclass(frozen=True)
class LabelSuggestion:
    """What the LLM judge proposed — and the redacted text it actually saw."""

    label: str
    rationale: str
    redacted_sample: str


@dataclass(frozen=True)
class Adjudication:
    """The human's decision. The judge never has the final say."""

    decision: str
    labeler: str
    timestamp: str
    agrees_with_llm: bool


@dataclass
class LabeledItem:
    item_id: str
    source: str  # e.g. "synthetic-T1" | "anonymized-T3"
    sample: str
    llm_suggestion: LabelSuggestion
    adjudication: Adjudication | None = None
    known_label: str | None = None  # set for synthetic-T1 items

    @property
    def in_corpus_ready(self) -> bool:
        return self.adjudication is not None

    @property
    def delta(self) -> dict[str, object] | None:
        """For a synthetic item: did the judge match the known injected label?"""
        if self.known_label is None:
            return None
        return {
            "known": self.known_label,
            "suggested": self.llm_suggestion.label,
            "match": self.known_label == self.llm_suggestion.label,
        }

    def to_record(self) -> dict[str, object]:
        """Flat provenance record for the validation corpus (JSONL-friendly)."""
        adj = self.adjudication
        return {
            "item_id": self.item_id,
            "source": self.source,
            "adjudicated": adj is not None,
            "llm_suggestion": {
                "label": self.llm_suggestion.label,
                "rationale": self.llm_suggestion.rationale,
            },
            "human_decision": adj.decision if adj else None,
            "labeler": adj.labeler if adj else None,
            "timestamp": adj.timestamp if adj else None,
            "agrees_with_llm": adj.agrees_with_llm if adj else None,
            "delta": self.delta,
        }


class LabelingHarness:
    """Collects judge suggestions, enforces human adjudication, emits the corpus."""

    def __init__(self, *, suggester: Suggester) -> None:
        self._suggester = suggester
        self._items: dict[str, LabeledItem] = {}

    def suggest(
        self,
        item_id: str,
        sample: str,
        *,
        source: str,
        domain: str,
        known_label: str | None = None,
    ) -> LabeledItem:
        """Get a judge suggestion for one sample (PII-redacted before egress)."""
        if item_id in self._items:
            raise ValueError(f"duplicate item_id {item_id!r}")
        redacted = redact_pii(sample)
        label, rationale = self._suggester(redacted, domain)
        item = LabeledItem(
            item_id=item_id,
            source=source,
            sample=sample,
            llm_suggestion=LabelSuggestion(label, rationale, redacted),
            known_label=known_label,
        )
        self._items[item_id] = item
        return item

    def adjudicate(
        self,
        item_id: str,
        *,
        decision: str,
        labeler: str,
        timestamp: str | None = None,
    ) -> LabeledItem:
        """Record the human decision that gates corpus entry."""
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"unknown item_id {item_id!r}")
        if not labeler:
            raise ValueError("a labeler identity is required for adjudication")
        stamp = timestamp or datetime.now(tz=timezone.utc).isoformat()
        item.adjudication = Adjudication(
            decision=decision,
            labeler=labeler,
            timestamp=stamp,
            agrees_with_llm=(decision == item.llm_suggestion.label),
        )
        return item

    @property
    def corpus(self) -> list[LabeledItem]:
        """Items cleared for the validation corpus (human-adjudicated only)."""
        return [i for i in self._items.values() if i.in_corpus_ready]

    def pending(self) -> list[LabeledItem]:
        return [i for i in self._items.values() if not i.in_corpus_ready]

    def commit_to_corpus(self) -> list[LabeledItem]:
        """Return the adjudicated corpus, refusing if any item is un-adjudicated.

        This is the hard gate: an LLM-suggested label cannot enter the corpus
        without recorded human adjudication.
        """
        pending = self.pending()
        if pending:
            ids = ", ".join(sorted(i.item_id for i in pending))
            raise AdjudicationRequired(
                "cannot commit to the validation corpus — these items lack human "
                f"adjudication: {ids}. The judge never has the final say."
            )
        return self.corpus


# --- the sole sanctioned external-model use (offline, off by default) --------


@dataclass
class _AnthropicSuggester:
    """Default judge backed by Anthropic. Used **only** in the QA lab, offline.

    Requires ``ANTHROPIC_API_KEY``; with no key set it raises rather than making
    a silent network call. The import is lazy so the package has no hard SDK
    dependency. Per SARO-102 only the PII-redacted fragment + domain are sent.
    """

    model: str = field(
        default_factory=lambda: os.environ.get(
            "SARO_LLM_JUDGE_MODEL", "claude-sonnet-4-20250514"
        )
    )

    def __call__(self, redacted_sample: str, domain: str) -> tuple[str, str]:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — the offline judge makes no silent "
                "external call. Set it explicitly to run the lab judge."
            )
        import anthropic  # lazy: qa_lab is exempt from STORY-336, product code is not

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"You are labeling a sample for the '{domain}' domain. Reply with a "
            f"single label word, then a short rationale.\nSAMPLE: {redacted_sample}"
        )
        msg = client.messages.create(
            model=self.model,
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        # Defensive: the response may be empty or lead with a non-text block.
        blocks = getattr(msg, "content", None) or []
        text = next(
            (getattr(b, "text", "") for b in blocks if getattr(b, "text", "")), ""
        ).strip()
        if not text:
            raise RuntimeError("judge returned no text content to label with")
        label, _, rationale = text.partition("\n")
        return label.strip().lower(), rationale.strip()


def default_anthropic_suggester() -> Suggester:
    """Construct the offline Anthropic-backed judge suggester."""
    return _AnthropicSuggester()
