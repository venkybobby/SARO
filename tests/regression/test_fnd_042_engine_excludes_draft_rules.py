"""FND-042 — the scoring engine must exclude DRAFT/RETIRED rule rows (CHUB-011 AC-1/AC-5).

Security-auditor blocker: engine.py loaded _eu_rules / _gov_rules with no
validation_status filter, so _lookup_obligations served DRAFT_UNVALIDATED / RETIRED
obligation text as authoritative remediation guidance in AppliedRuleOut and the TRACE
timeline — even though the Compliance Hub matrix hid those same rows. A drafted
article's obligation text must never reach an attestation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from database import Base  # noqa: E402
from models import EUAIActRule, GovernanceRule  # noqa: E402
from engine import SARoEngine  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


@pytest.mark.regression
def test_engine_excludes_draft_and_retired_obligations():
    db = _Session()
    try:
        db.add_all(
            [
                EUAIActRule(
                    article_number="Article 99",
                    title="valid",
                    obligations_providers="VALIDATED_OBLIGATION",
                    validation_status="SME_VALIDATED",
                ),
                EUAIActRule(
                    article_number="Article 13",
                    title="draft",
                    obligations_providers="DRAFT_LEAK_OBLIGATION",
                    validation_status="DRAFT_UNVALIDATED",
                ),
                GovernanceRule(
                    framework_name="US EO 14110",
                    rule_id="EO-1",
                    obligations="RETIRED_LEAK_OBLIGATION",
                    validation_status="RETIRED",
                ),
            ]
        )
        db.commit()

        eng = SARoEngine(db)

        eu_articles = {r.get("article_number") for r in eng._eu_rules}
        assert "Article 99" in eu_articles
        assert "Article 13" not in eu_articles  # draft excluded from load

        # The draft article resolves to no obligation text; the validated one does.
        assert eng._lookup_obligations("EU AI Act", "Article 13") is None
        assert (
            eng._lookup_obligations("EU AI Act", "Article 99") == "VALIDATED_OBLIGATION"
        )

        # Retired governance obligations never load.
        gov_texts = {r.get("obligations") for r in eng._gov_rules}
        assert "RETIRED_LEAK_OBLIGATION" not in gov_texts
    finally:
        db.close()
