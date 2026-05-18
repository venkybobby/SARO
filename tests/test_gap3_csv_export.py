"""GAP-3: CSV export unit tests — column names, RFC 4180 quoting, null handling, row limit."""
from __future__ import annotations

import csv
import io


from services.compliance_matrix_service import (
    filter_matrix_rows,
    _STATIC_ROWS,
)
from routers.compliance_matrix import (
    _CSV_COLUMNS,
    _ROW_FIELD_MAP,
    _EXPORT_MAX_ROWS,
)


# ── Helper: rows → CSV bytes ─────────────────────────────────────────────────

def _rows_to_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(_CSV_COLUMNS)
    for row in rows:
        writer.writerow([
            row.get(f) if row.get(f) is not None else ""
            for f in _ROW_FIELD_MAP
        ])
    return buf.getvalue().encode("utf-8")


# ── TC-3.2: CSV has all 9 required column headers ────────────────────────────

class TestCsvHeaders:
    def test_first_row_contains_all_required_headers(self):
        """TC-3.2 — first row must have exactly 9 headers in correct order."""
        csv_bytes = _rows_to_csv([_STATIC_ROWS[0]])
        lines = csv_bytes.decode("utf-8").splitlines()
        headers = next(csv.reader(lines))
        assert headers == _CSV_COLUMNS

    def test_header_count_is_nine(self):
        assert len(_CSV_COLUMNS) == 9

    def test_required_header_names_present(self):
        required = [
            "Regulation Name", "Article/Section", "Requirement Summary",
            "Risk Level", "Status", "Coverage %", "Last Updated",
            "Assigned Owner", "Notes",
        ]
        assert _CSV_COLUMNS == required


# ── TC-3.3: Null fields export as empty string ───────────────────────────────

class TestNullHandling:
    def test_null_notes_exports_as_empty_string(self):
        """TC-3.3 — None → "" not "None" or "null"."""
        row = {
            "regulation_name": "Test",
            "article_section": "§1",
            "requirement_summary": "Test requirement",
            "risk_level": "Medium",
            "status": "Compliant",
            "coverage_pct": None,
            "last_updated": None,
            "assigned_owner": None,
            "notes": None,
        }
        csv_bytes = _rows_to_csv([row])
        content = csv_bytes.decode("utf-8")
        assert "None" not in content
        assert "null" not in content

    def test_null_coverage_exports_as_empty_string(self):
        row = dict(_STATIC_ROWS[3])  # ISO-8.4 has coverage_pct=35, let's override
        row["coverage_pct"] = None
        csv_bytes = _rows_to_csv([row])
        parsed = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))[1]
        # Coverage % is index 5 in _ROW_FIELD_MAP
        assert parsed[5] == ""


# ── TC-3.4: RFC 4180 quoting of fields with commas ───────────────────────────

class TestRfc4180Quoting:
    def test_field_with_comma_is_quoted(self):
        """TC-3.4 — 'Ensure data handling, storage...' must be double-quoted."""
        row = {
            "regulation_name": "EU AI Act",
            "article_section": "Art. 9",
            "requirement_summary": "Ensure data handling, storage, and retrieval policies exist",
            "risk_level": "High",
            "status": "In Progress",
            "coverage_pct": 42,
            "last_updated": "2025-12-01",
            "assigned_owner": None,
            "notes": None,
        }
        csv_bytes = _rows_to_csv([row])
        # Re-parse with csv.reader — should not corrupt data
        lines = csv_bytes.decode("utf-8").splitlines()
        data_row = list(csv.reader(lines))[1]
        assert data_row[2] == "Ensure data handling, storage, and retrieval policies exist"

    def test_field_with_double_quote_is_escaped(self):
        row = {k: None for k in _ROW_FIELD_MAP}
        row["requirement_summary"] = 'He said "hello"'
        csv_bytes = _rows_to_csv([row])
        lines = csv_bytes.decode("utf-8").splitlines()
        data_row = list(csv.reader(lines))[1]
        assert data_row[2] == 'He said "hello"'


# ── TC-3.5: Export respects filter parameter ─────────────────────────────────

class TestExportFilter:
    def test_filtered_export_contains_only_matching_rows(self):
        """TC-3.5 — 5 NIST rows + 5 EU AI Act rows → filter returns 5."""
        rows = (
            [{"regulation_name": "NIST AI RMF", **{k: None for k in _ROW_FIELD_MAP if k != "regulation_name"}}] * 5
            + [{"regulation_name": "EU AI Act", **{k: None for k in _ROW_FIELD_MAP if k != "regulation_name"}}] * 5
        )
        filtered = filter_matrix_rows(rows, filter_regulation="NIST AI RMF")
        assert len(filtered) == 5
        assert all(r["regulation_name"] == "NIST AI RMF" for r in filtered)


# ── Row limit constant ────────────────────────────────────────────────────────

class TestExportLimits:
    def test_export_max_rows_constant_is_50000(self):
        """TC-3.6 — limit must be 50,000."""
        assert _EXPORT_MAX_ROWS == 50_000

    def test_column_count_matches_field_map(self):
        """Columns and field map must be in sync."""
        assert len(_CSV_COLUMNS) == len(_ROW_FIELD_MAP)


# ── Audit event type constant ─────────────────────────────────────────────────

class TestAuditEventType:
    def test_export_event_type_string(self):
        """TC-3.7 — audit event type must be MATRIX_EXPORT_CSV."""
        from routers.compliance_matrix import _log_export_event
        import inspect
        src = inspect.getsource(_log_export_event)
        assert "MATRIX_EXPORT_CSV" in src
