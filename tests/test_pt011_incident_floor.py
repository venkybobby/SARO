"""PT-011: incident similarity floor suppression + corpus staleness/source visibility."""
from unittest.mock import MagicMock

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer

from engine import SARoEngine
from schemas import IncidentCorpusStatsOut

pytestmark = pytest.mark.unit


def _engine_with_one_incident():
    db = MagicMock()
    db.query.return_value.all.return_value = []
    engine = SARoEngine(db)
    engine._incidents = [{
        "incident_id": "INC-1", "title": "model leaked PII ssn credit card",
        "description": "privacy breach", "category": "privacy", "harm_type": None,
        "affected_sector": None, "date": None, "url": None, "is_fixed": False, "created_at": None,
    }]
    corpus = ["model leaked PII ssn credit card privacy breach"]
    engine._tfidf_vectorizer = TfidfVectorizer()
    engine._tfidf_vectorizer.fit(corpus)
    engine._incident_matrix = engine._tfidf_vectorizer.transform(corpus)
    return engine


def test_below_floor_suppressed_by_default():
    engine = _engine_with_one_incident()
    # A weakly-overlapping query lands below the 0.15 floor → suppressed.
    results = engine._find_similar_incidents("privacy", top_k=1)
    below = engine._find_similar_incidents("privacy", top_k=1, include_below_floor=True)
    # Whatever the score, default results never contain a below-floor match...
    assert all(r.similarity_score >= engine.SIMILARITY_THRESHOLD for r in results)
    # ...but the debug view may surface them, each carrying the active floor.
    for r in below:
        assert r.minimum_similarity_threshold == engine.SIMILARITY_THRESHOLD


def test_strong_match_survives_floor():
    engine = _engine_with_one_incident()
    results = engine._find_similar_incidents("model leaked PII ssn credit card privacy breach", top_k=1)
    assert results and results[0].similarity_score >= engine.SIMILARITY_THRESHOLD


def test_each_match_reports_score_and_floor():
    engine = _engine_with_one_incident()
    for r in engine._find_similar_incidents("model leaked PII ssn credit card", top_k=1, include_below_floor=True):
        assert r.similarity_score is not None
        assert r.minimum_similarity_threshold == engine.SIMILARITY_THRESHOLD


def test_corpus_stats_schema_has_source_and_staleness():
    out = IncidentCorpusStatsOut(
        total_incidents=0, count_by_category={}, count_by_harm_type={},
        date_range_earliest=None, date_range_latest=None, pct_fixed=0.0,
        last_corpus_update=None, count_by_source={"AIID": 5}, corpus_stale=True,
        staleness_message="empty",
    )
    assert out.count_by_source == {"AIID": 5}
    assert out.corpus_stale is True
