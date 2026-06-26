"""Unit tests for the patch-only dependency sweeper (scripts/dependency_sweeper.py).

Covers the pure logic only — no network. The CLI's fetch_versions is exercised in
the workflow, not here.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "dependency_sweeper", ROOT / "scripts" / "dependency_sweeper.py"
)
assert _spec is not None and _spec.loader is not None
ds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ds)


@pytest.mark.parametrize("line,expected", [
    ("gunicorn==22.0.0", ("gunicorn", "22.0.0")),
    ("python-jose[cryptography]==3.3.0", ("python-jose[cryptography]", "3.3.0")),
    ("  PyYAML==6.0.1  ", ("PyYAML", "6.0.1")),
    ("fastapi>=0.111.0", None),
    ("uvicorn[standard]>=0.29.0", None),
    ("# a comment", None),
    ("", None),
    ("scipy~=1.13.0", None),
])
def test_parse_exact_pin(line, expected):
    assert ds.parse_exact_pin(line) == expected


def test_package_name_strips_extras():
    assert ds.package_name("python-jose[cryptography]") == "python-jose"
    assert ds.package_name("gunicorn") == "gunicorn"


def test_latest_patch_picks_highest_same_minor():
    available = ["22.0.0", "22.0.1", "22.0.5", "22.1.0", "23.0.0"]
    assert ds.latest_patch("22.0.0", available) == "22.0.5"


def test_latest_patch_ignores_minor_and_major_bumps():
    # Only 22.0.x is eligible; 22.1.0 and 23.0.0 must be excluded.
    assert ds.latest_patch("22.0.4", ["22.1.0", "23.0.0", "22.0.4"]) is None


def test_latest_patch_ignores_prereleases():
    assert ds.latest_patch("1.2.0", ["1.2.1rc1", "1.2.1.dev0", "1.2.0"]) is None
    assert ds.latest_patch("1.2.0", ["1.2.1rc1", "1.2.2", "1.2.0"]) == "1.2.2"


def test_latest_patch_none_when_already_latest():
    assert ds.latest_patch("22.0.5", ["22.0.0", "22.0.5"]) is None


def test_compute_updates_only_touches_exact_pins():
    text = (
        "fastapi>=0.111.0\n"
        "gunicorn==22.0.0\n"
        "# comment\n"
        "PyYAML>=6.0\n"
    )
    lookup = {"gunicorn": ["22.0.0", "22.0.3"]}.get
    new_text, updates = ds.compute_updates(text, lambda n: lookup(n) or [])
    assert updates == [{"package": "gunicorn", "from": "22.0.0", "to": "22.0.3"}]
    assert "gunicorn==22.0.3" in new_text
    assert "fastapi>=0.111.0" in new_text  # untouched
    assert "PyYAML>=6.0" in new_text       # untouched
    assert new_text.endswith("\n")


def test_compute_updates_noop_when_nothing_newer():
    text = "gunicorn==22.0.0\n"
    new_text, updates = ds.compute_updates(text, lambda n: ["22.0.0"])
    assert updates == []
    assert new_text == text


def test_latest_patch_invalid_current_version():
    assert ds.latest_patch("not-a-version", ["1.0.0"]) is None


def test_latest_patch_skips_unparseable_available():
    assert ds.latest_patch("1.2.0", ["garbage", "1.2.2"]) == "1.2.2"


# --- CLI (main) ---------------------------------------------------------------

def _req(tmp_path, text):
    p = tmp_path / "requirements.txt"
    p.write_text(text)
    return p


def test_main_json_output(monkeypatch, tmp_path, capsys):
    req = _req(tmp_path, "gunicorn==22.0.0\nfastapi>=0.111.0\n")
    monkeypatch.setattr(ds, "fetch_versions",
                        lambda n: ["22.0.0", "22.0.3"] if n == "gunicorn" else [])
    assert ds.main(["--requirements", str(req), "--json"]) == 0
    assert "22.0.3" in capsys.readouterr().out


def test_main_apply_writes_file(monkeypatch, tmp_path):
    req = _req(tmp_path, "gunicorn==22.0.0\n")
    monkeypatch.setattr(ds, "fetch_versions", lambda n: ["22.0.0", "22.0.3"])
    assert ds.main(["--requirements", str(req), "--apply"]) == 0
    assert "gunicorn==22.0.3" in req.read_text()


def test_main_no_updates(monkeypatch, tmp_path, capsys):
    req = _req(tmp_path, "gunicorn==22.0.0\n")
    monkeypatch.setattr(ds, "fetch_versions", lambda n: ["22.0.0"])
    assert ds.main(["--requirements", str(req)]) == 0
    assert "No patch updates" in capsys.readouterr().out


def test_main_missing_file_returns_error():
    assert ds.main(["--requirements", "/no/such/requirements.txt"]) == 1
