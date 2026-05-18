"""GAP-1: Compliance matrix sort and filter unit + integration tests."""
from __future__ import annotations


from services.compliance_matrix_service import (
    RISK_ORDINAL,
    filter_matrix_rows,
    sort_matrix_rows,
)

# ── Sample fixture rows ───────────────────────────────────────────────────────

_SAMPLE_ROWS = [
    {"regulation_name": "EU AI Act",  "risk_level": "Critical", "last_updated": "2025-12-01"},
    {"regulation_name": "NIST AI RMF","risk_level": "High",     "last_updated": "2026-01-15"},
    {"regulation_name": "ISO 42001",  "risk_level": "Medium",   "last_updated": "2026-02-10"},
    {"regulation_name": "AIGP Framework","risk_level": "Low",   "last_updated": None},
    {"regulation_name": "EU AI Act",  "risk_level": "High",     "last_updated": "2025-11-15"},
    {"regulation_name": "ISO 42001",  "risk_level": "N/A",      "last_updated": "2026-01-10"},
]


# ── TC-1.1: Risk level ordinal sort ──────────────────────────────────────────

class TestRiskLevelSort:
    def test_ascending_order_low_to_critical(self):
        """TC-1.1 ascending — Low … Critical, N/A last."""
        rows = [
            {"risk_level": "High"},
            {"risk_level": "Critical"},
            {"risk_level": "Low"},
            {"risk_level": "Medium"},
            {"risk_level": "N/A"},
        ]
        result = sort_matrix_rows(rows, "risk_level", "asc")
        levels = [r["risk_level"] for r in result]
        assert levels == ["Low", "Medium", "High", "Critical", "N/A"]

    def test_descending_order_critical_to_low(self):
        """TC-1.1 descending — Critical … Low, N/A last."""
        rows = [
            {"risk_level": "High"},
            {"risk_level": "Critical"},
            {"risk_level": "Low"},
            {"risk_level": "Medium"},
            {"risk_level": "N/A"},
        ]
        result = sort_matrix_rows(rows, "risk_level", "desc")
        levels = [r["risk_level"] for r in result]
        assert levels == ["Critical", "High", "Medium", "Low", "N/A"]

    def test_null_risk_level_always_last_ascending(self):
        rows = [{"risk_level": "High"}, {"risk_level": None}, {"risk_level": "Low"}]
        result = sort_matrix_rows(rows, "risk_level", "asc")
        assert result[-1]["risk_level"] is None

    def test_null_risk_level_always_last_descending(self):
        rows = [{"risk_level": "High"}, {"risk_level": None}, {"risk_level": "Low"}]
        result = sort_matrix_rows(rows, "risk_level", "desc")
        assert result[-1]["risk_level"] is None


# ── TC-1.2: Regulation name sort is case-insensitive ─────────────────────────

class TestRegulationNameSort:
    def test_case_insensitive_ascending(self):
        """TC-1.2 — 'eu ai act' < 'iso 42001' < 'nist rmf' (case-folded)."""
        rows = [
            {"regulation_name": "nist rmf"},
            {"regulation_name": "EU AI Act"},
            {"regulation_name": "iso 42001"},
        ]
        result = sort_matrix_rows(rows, "regulation_name", "asc")
        names = [r["regulation_name"].lower() for r in result]
        assert names == sorted(names)

    def test_case_insensitive_descending(self):
        rows = [
            {"regulation_name": "nist rmf"},
            {"regulation_name": "EU AI Act"},
            {"regulation_name": "iso 42001"},
        ]
        result = sort_matrix_rows(rows, "regulation_name", "desc")
        names = [r["regulation_name"].lower() for r in result]
        assert names == sorted(names, reverse=True)


# ── TC-1.3: Last updated sort places null dates last ─────────────────────────

class TestLastUpdatedSort:
    def test_null_dates_last_ascending(self):
        """TC-1.3 ascending — dated rows first, null last."""
        rows = [
            {"last_updated": "2024-01-01"},
            {"last_updated": None},
            {"last_updated": "2023-06-15"},
        ]
        result = sort_matrix_rows(rows, "last_updated", "asc")
        assert result[0]["last_updated"] == "2023-06-15"
        assert result[1]["last_updated"] == "2024-01-01"
        assert result[2]["last_updated"] is None

    def test_null_dates_last_descending(self):
        """TC-1.3 descending — newest first, null last."""
        rows = [
            {"last_updated": "2024-01-01"},
            {"last_updated": None},
            {"last_updated": "2023-06-15"},
        ]
        result = sort_matrix_rows(rows, "last_updated", "desc")
        assert result[0]["last_updated"] == "2024-01-01"
        assert result[-1]["last_updated"] is None

    def test_sort_by_timestamp_not_display_string(self):
        """Sort must use date value, not string representation."""
        rows = [
            {"last_updated": "2026-01-01"},
            {"last_updated": "2025-12-31"},
            {"last_updated": "2025-02-01"},
        ]
        result = sort_matrix_rows(rows, "last_updated", "asc")
        dates = [r["last_updated"] for r in result]
        assert dates == sorted(dates)


# ── FR-1.5: Sort state preserved when filter applied ─────────────────────────

class TestSortWithFilter:
    def test_filter_then_sort_consistent(self):
        """TC-1.6 — filtered rows are in risk-sorted order."""
        rows = [
            {"regulation_name": "EU AI Act", "risk_level": "High",     "last_updated": None},
            {"regulation_name": "NIST AI RMF","risk_level": "Critical","last_updated": None},
            {"regulation_name": "EU AI Act", "risk_level": "Medium",   "last_updated": None},
            {"regulation_name": "ISO 42001",  "risk_level": "Low",     "last_updated": None},
        ]
        filtered = filter_matrix_rows(rows, filter_regulation="EU AI Act")
        sorted_rows = sort_matrix_rows(filtered, "risk_level", "asc")
        levels = [r["risk_level"] for r in sorted_rows]
        assert levels == ["Medium", "High"]

    def test_filter_only_returns_matching_rows(self):
        rows = [
            {"regulation_name": "EU AI Act", "risk_level": "High"},
            {"regulation_name": "NIST AI RMF","risk_level": "Medium"},
        ]
        result = filter_matrix_rows(rows, filter_regulation="EU AI Act")
        assert all(r["regulation_name"] == "EU AI Act" for r in result)
        assert len(result) == 1

    def test_filter_case_insensitive(self):
        rows = [{"regulation_name": "EU AI Act"}, {"regulation_name": "NIST AI RMF"}]
        result = filter_matrix_rows(rows, filter_regulation="eu ai act")
        assert len(result) == 1

    def test_no_sort_key_returns_original_order(self):
        rows = [{"risk_level": "High"}, {"risk_level": "Low"}, {"risk_level": "Critical"}]
        result = sort_matrix_rows(rows, None, "asc")
        assert [r["risk_level"] for r in result] == ["High", "Low", "Critical"]


# ── FR-1.6: Invalid sort_by raises ValueError equivalent ─────────────────────

class TestSortValidation:
    def test_invalid_sort_column_not_applied(self):
        """sort_matrix_rows with invalid column returns original order."""
        rows = [{"risk_level": "High"}, {"risk_level": "Low"}]
        result = sort_matrix_rows(rows, "invalid_column", "asc")
        assert result == rows

    def test_risk_ordinal_values_correct(self):
        assert RISK_ORDINAL["Critical"] > RISK_ORDINAL["High"]
        assert RISK_ORDINAL["High"] > RISK_ORDINAL["Medium"]
        assert RISK_ORDINAL["Medium"] > RISK_ORDINAL["Low"]
        assert RISK_ORDINAL["Low"] > RISK_ORDINAL["N/A"]
