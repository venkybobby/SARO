"""STORY-338 — Offline LLM-as-judge labeling harness (QA lab only).

LLM-as-judge is allowed for *building ground truth* — but only offline, isolated
from the product path, and never as the final say. A human adjudicates before any
label enters the validation corpus, and every item carries full provenance. This
is the one sanctioned external-model use, exempted under STORY-336.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grc.guards.external_model import (
    LAB_PACKAGE,
    default_product_roots,
    scan_paths,
)
from qa_lab.labeling import (
    AdjudicationRequired,
    LabeledItem,
    LabelingHarness,
    redact_pii,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]


def _stub_suggester(received: list[str]):
    """A fake judge: records what it was given, suggests a fixed label."""

    def suggest(redacted_sample: str, domain: str) -> tuple[str, str]:
        received.append(redacted_sample)
        return ("toxic", f"matched {domain} pattern")

    return suggest


# --- AC: the lab is unreachable from product code (verified by STORY-336) ----


def test_product_path_does_not_import_qa_lab() -> None:
    violations = scan_paths(
        default_product_roots(REPO_ROOT), repo_root=REPO_ROOT, allowlist=frozenset()
    )
    lab_imports = [v for v in violations if v.kind == "lab_import"]
    assert lab_imports == [], f"product code must not import the QA lab: {lab_imports}"


def test_qa_lab_is_outside_the_336_product_scope() -> None:
    # The lab package is not part of the scanned product path — its sanctioned
    # external-model use cannot trip the STORY-336 guard.
    scoped = {p.name for p in default_product_roots(REPO_ROOT)}
    assert LAB_PACKAGE not in scoped
    assert LAB_PACKAGE == "qa_lab"


# --- AC: no LLM label enters the corpus without recorded human adjudication ---


def test_unadjudicated_item_cannot_enter_corpus() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    h.suggest("itm-1", "you are worthless", source="anonymized-T3", domain="toxicity")
    with pytest.raises(AdjudicationRequired):
        h.commit_to_corpus()
    assert h.corpus == []


def test_adjudicated_item_enters_corpus_with_full_provenance() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    h.suggest("itm-1", "you are worthless", source="anonymized-T3", domain="toxicity")
    h.adjudicate(
        "itm-1", decision="toxic", labeler="sam.patel", timestamp="2026-06-16T10:00:00Z"
    )
    corpus = h.commit_to_corpus()
    assert len(corpus) == 1
    item = corpus[0]
    assert isinstance(item, LabeledItem)
    rec = item.to_record()
    # Full provenance: source, LLM suggestion, human decision, labeler, timestamp.
    assert rec["source"] == "anonymized-T3"
    assert rec["llm_suggestion"]["label"] == "toxic"
    assert rec["human_decision"] == "toxic"
    assert rec["labeler"] == "sam.patel"
    assert rec["timestamp"] == "2026-06-16T10:00:00Z"


def test_human_can_override_the_llm_suggestion() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    h.suggest("itm-1", "have a nice day", source="anonymized-T3", domain="toxicity")
    h.adjudicate(
        "itm-1",
        decision="benign",
        labeler="taylor.kim",
        timestamp="2026-06-16T11:00:00Z",
    )
    item = h.commit_to_corpus()[0]
    assert item.adjudication is not None
    assert item.adjudication.agrees_with_llm is False
    assert item.to_record()["human_decision"] == "benign"


# --- AC: synthetic T1 — suggestion compared to known label, delta recorded ----


def test_synthetic_defect_delta_recorded() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    item = h.suggest(
        "syn-1",
        "you are worthless",
        source="synthetic-T1",
        domain="toxicity",
        known_label="toxic",
    )
    delta = item.delta
    assert delta is not None
    assert delta["known"] == "toxic"
    assert delta["suggested"] == "toxic"
    assert delta["match"] is True


def test_synthetic_defect_delta_records_a_miss() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    item = h.suggest(
        "syn-2",
        "benign text",
        source="synthetic-T1",
        domain="toxicity",
        known_label="benign",
    )  # stub always suggests "toxic" → mismatch
    assert item.delta is not None
    assert item.delta["match"] is False


# --- AC: PII is redacted before egress to the judge --------------------------


def test_pii_redacted_before_suggester_sees_sample() -> None:
    received: list[str] = []
    h = LabelingHarness(suggester=_stub_suggester(received))
    h.suggest(
        "itm-1",
        "contact me at jane@example.com or 123-45-6789",
        source="anonymized-T3",
        domain="pii",
    )
    assert received, "suggester should have been called"
    sent = received[0]
    assert "jane@example.com" not in sent
    assert "123-45-6789" not in sent


def test_redact_pii_helper() -> None:
    out = redact_pii("SSN 123-45-6789 email a@b.com")
    assert "123-45-6789" not in out
    assert "a@b.com" not in out


@pytest.mark.parametrize(
    "raw",
    ["123 45 6789", "123.45.6789", "192.168.1.42"],  # delimiter SSNs + IPv4
)
def test_redact_pii_covers_delimited_ssn_and_ipv4(raw: str) -> None:
    assert raw not in redact_pii(f"value {raw} here")


def test_pending_record_is_marked_unadjudicated() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    item = h.suggest("itm-1", "text", source="anonymized-T3", domain="toxicity")
    rec = item.to_record()
    assert rec["adjudicated"] is False
    assert rec["human_decision"] is None


# --- flow test: suggestion -> adjudication -> corpus entry with provenance ----


def test_end_to_end_flow() -> None:
    h = LabelingHarness(suggester=_stub_suggester([]))
    h.suggest("a", "you are worthless", source="anonymized-T3", domain="toxicity")
    h.suggest("b", "lovely weather", source="anonymized-T3", domain="toxicity")
    h.adjudicate("a", decision="toxic", labeler="sam", timestamp="2026-06-16T12:00:00Z")
    h.adjudicate(
        "b", decision="benign", labeler="sam", timestamp="2026-06-16T12:01:00Z"
    )
    corpus = h.commit_to_corpus()
    assert {i.item_id for i in corpus} == {"a", "b"}
    assert all(i.adjudication is not None for i in corpus)
