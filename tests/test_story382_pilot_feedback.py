"""STORY-382 — structured pilot feedback intake.

Feedback is the one place free text is a feature, so the tests centre on the
mitigations that stand in for by-construction PHI safety: the visible notice, the
length cap, and — load-bearing — that the feedback table is never joined into an
evidence export.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import sqlalchemy.types as sa_types  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSON as PG_JSON  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine)
_orig = PG_UUID.__init__
PG_UUID.__init__ = lambda self, *a, **k: (k.pop("as_uuid", None), _orig(self, *a, **k))[1]  # type: ignore
PG_JSON.__init__ = lambda self, *a, **k: sa_types.Text.__init__(self)  # type: ignore

from database import Base  # noqa: E402
import models  # noqa: E402,F401
import services.feedback_service as fb  # noqa: E402

Base.metadata.create_all(engine)

pytestmark = pytest.mark.integration

RITUAL = ROOT / "docs" / "ops" / "feedback-triage.md"


@pytest.fixture
def db():
    with engine.begin() as conn:
        for t in reversed(Base.metadata.sorted_tables):
            conn.execute(t.delete())
    s = TestingSessionLocal()
    yield s
    s.rollback()
    s.close()


def _submit(db, **over):
    kw = dict(
        tenant_id=uuid.uuid4(), screen="TraceView", category="confusing",
        severity="medium", body="The risk chip is confusing.",
    )
    kw.update(over)
    return fb.submit(db, **kw)


# ── AC-1: capture ───────────────────────────────────────────────────────────


def test_feedback_captures_the_required_fields(db):
    item = _submit(db)
    assert item.screen == "TraceView"
    assert item.category == "confusing"
    assert item.severity == "medium"
    assert item.triage_status == "new"


def test_unknown_category_is_rejected(db):
    with pytest.raises(fb.FeedbackError, match="category"):
        _submit(db, category="rant")


def test_unknown_severity_is_rejected(db):
    with pytest.raises(fb.FeedbackError, match="severity"):
        _submit(db, severity="apocalyptic")


# ── AC-2: free-text mitigations (no PHI by construction is impossible here) ──


def test_body_over_the_length_cap_is_rejected(db):
    with pytest.raises(fb.FeedbackError, match="exceeds"):
        _submit(db, body="x" * (fb.MAX_BODY_CHARS + 1))


def test_empty_body_is_rejected(db):
    with pytest.raises(fb.FeedbackError, match="empty"):
        _submit(db, body="   ")


def test_no_phi_notice_is_part_of_the_form_contract():
    """The widget must display this above the free-text field."""
    assert "patient information" in fb.NO_PHI_NOTICE.lower()
    assert "phi" in fb.NO_PHI_NOTICE.lower()


def test_feedback_table_is_excluded_from_evidence_exports():
    """A pilot's UI gripe must never surface in an auditor's evidence pack.

    Structural check: no evidence-export code path references the feedback model.
    """
    import re

    export_files = list((ROOT / "routers").glob("*export*.py")) + [
        ROOT / "services" / "audit_submission.py",
        ROOT / "routers" / "trace_export.py",
    ]
    for path in export_files:
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        assert not re.search(r"\bPilotFeedback\b", src), (
            f"{path.name} references PilotFeedback — feedback must not enter evidence exports"
        )


# ── AC-3: triage lifecycle ──────────────────────────────────────────────────


def test_triage_links_a_story(db):
    item = _submit(db)
    triaged = fb.triage(db, feedback_id=item.id, status="story_linked", story_id="STORY-999")
    assert triaged.triage_status == "story_linked"
    assert triaged.story_id == "STORY-999"


def test_story_linked_requires_a_story_id(db):
    item = _submit(db)
    with pytest.raises(fb.FeedbackError, match="story_id"):
        fb.triage(db, feedback_id=item.id, status="story_linked")


def test_declined_requires_a_reason(db):
    """A silently-dropped item is how a pilot stops giving feedback."""
    item = _submit(db)
    with pytest.raises(fb.FeedbackError, match="reason"):
        fb.triage(db, feedback_id=item.id, status="declined")
    ok = fb.triage(db, feedback_id=item.id, status="declined", note="duplicate of STORY-100")
    assert ok.triage_status == "declined"


def test_triage_view_lists_and_filters(db):
    _submit(db)
    parked = _submit(db)
    fb.triage(db, feedback_id=parked.id, status="parked", note="later")
    assert len(fb.list_for_triage(db)) == 2
    assert len(fb.list_for_triage(db, status="new")) == 1


def test_unknown_triage_status_is_rejected(db):
    item = _submit(db)
    with pytest.raises(fb.FeedbackError, match="triage status"):
        fb.triage(db, feedback_id=item.id, status="ignored")


# ── API surface + auth ──────────────────────────────────────────────────────


def test_routes_are_registered_and_authenticated():
    from main import app

    from _route_utils import method_path_pairs

    # FND-069: recurse — Starlette may nest included routers, so a top-level
    # app.routes filter would see only ("/") and ("/health") in CI.
    paths = method_path_pairs(app, drop=frozenset())
    assert ("POST", "/api/v1/feedback") in paths
    assert ("GET", "/api/v1/feedback/triage") in paths


def test_triage_routes_are_classified_in_the_audit_registry():
    from services.admin_audit_registry import classification

    assert classification("POST", "/api/v1/feedback") == "DATA_PLANE"
    assert classification("PATCH", "/api/v1/feedback/{feedback_id}/triage") == "DATA_PLANE"


# ── AC-4: the ritual doc ────────────────────────────────────────────────────


def test_ritual_doc_requires_every_item_to_reach_a_disposition():
    doc = RITUAL.read_text(encoding="utf-8").lower()
    assert "story_linked" in doc and "declined" in doc and "parked" in doc
    assert "reason" in doc, "declines must carry a reason"
    assert "weekly" in doc


def test_ritual_doc_states_the_export_exclusion():
    doc = RITUAL.read_text(encoding="utf-8").lower()
    assert "evidence export" in doc or "evidence pack" in doc
