"""STORY-105: the dead Streamlit frontend and its deploy wiring are gone.

Pins that no Streamlit source survives under frontend/ and that no deploy config
still references the removed Streamlit Dockerfile/healthcheck/requirements, so the
dead UI cannot creep back into a build.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent


@pytest.mark.unit
def test_streamlit_sources_removed():
    for gone in (
        "frontend/app.py",
        "frontend/styles.py",
        "frontend/requirements.txt",
        "frontend/tabs",
        "Dockerfile.frontend",
    ):
        assert not (_ROOT / gone).exists(), f"dead Streamlit artifact still present: {gone}"


@pytest.mark.unit
def test_no_streamlit_import_under_frontend():
    src_dir = _ROOT / "frontend"
    offenders = [
        str(p.relative_to(_ROOT))
        for p in src_dir.rglob("*.py")
        if "import streamlit" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"streamlit still imported under frontend/: {offenders}"


@pytest.mark.unit
def test_deploy_config_no_longer_references_streamlit():
    railway = (_ROOT / "railway.toml").read_text(encoding="utf-8")
    assert "_stcore" not in railway, "railway.toml still has the Streamlit healthcheck"
    assert "Dockerfile.frontend" not in railway, "railway.toml still references Dockerfile.frontend"
    assert "[services.frontend" not in railway, "railway.toml still defines a frontend service"

    compose = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "Dockerfile.frontend" not in compose, "docker-compose still builds Dockerfile.frontend"

    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "frontend/requirements.txt" not in ci, "CI still installs Streamlit requirements"
