"""FND-036: bad merge left main non-importable (auth.py + routers/scan.py).

Merging the CHUB / TRACE / Epic-14 PRs spliced two copies of
``auth.require_role_or_persona`` together (unclosed ``raise``), duplicated the
``dependencies=`` kwarg and a ``from auth import`` line on ``GET /api/v1/audits`` in
routers/scan.py, and dropped the ``status`` field from the FND-033 manifest entry — so
``import auth`` raised SyntaxError and the whole backend failed to start.

This pins the structural repair: the two corrupted modules parse and import, and the
duplicated definitions are gone. (The audits-read authz set itself is pinned separately
by test_fnd_025_audits_compliance_lead_access.py.)
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

pytestmark = pytest.mark.regression

_ROOT = pathlib.Path(__file__).parents[2]


@pytest.mark.parametrize("module", ["auth", "routers.scan"])
def test_corrupted_modules_parse_and_import(module: str) -> None:
    rel = module.replace(".", "/") + ".py"
    source = (_ROOT / rel).read_text(encoding="utf-8")
    ast.parse(source)  # raises SyntaxError if the bad merge reappears
    importlib.import_module(module)  # must import without error


def test_require_role_or_persona_defined_exactly_once() -> None:
    """The bad merge duplicated this function def. Exactly one must exist."""
    tree = ast.parse((_ROOT / "auth.py").read_text(encoding="utf-8"))
    defs = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "require_role_or_persona"
    ]
    assert len(defs) == 1, (
        f"expected one require_role_or_persona def, found {len(defs)}"
    )


def test_audits_route_has_single_dependencies_kwarg() -> None:
    """The bad merge gave GET /api/v1/audits two `dependencies=` kwargs (a SyntaxError)."""
    source = (_ROOT / "routers" / "scan.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            kwarg_names = [k.arg for k in node.keywords if k.arg]
            assert kwarg_names.count("dependencies") <= 1, (
                "duplicate dependencies= kwarg (bad merge)"
            )
