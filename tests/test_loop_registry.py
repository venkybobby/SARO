"""Validates loops/registry.yaml against loops/registry.schema.json.

The loop registry is SARO's catalogue of automated agent loops (cadence, risk,
maturity, governance). This test keeps the registry honest: every entry must
conform to the schema, ids must be unique, owners must be real team members, and
SARO's non-negotiable guardrail must hold -- no loop's maturity may exceed its
declared max_maturity, and high-risk loops touching scoring/compliance/rule-packs
stay capped at L1 (propose-only).
"""

import json
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "loops" / "registry.yaml"
SCHEMA_PATH = REPO_ROOT / "loops" / "registry.schema.json"

# Team members from CLAUDE.md.
TEAM = {"Venky", "Alex Rivera", "Jordan Lee", "Sam Patel", "Taylor Kim"}

_MATURITY_RANK = {"L1": 1, "L2": 2, "L3": 3}


@pytest.fixture(scope="module")
def registry():
    with REGISTRY_PATH.open() as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def schema():
    with SCHEMA_PATH.open() as fh:
        return json.load(fh)


def test_registry_and_schema_exist():
    assert REGISTRY_PATH.exists(), "loops/registry.yaml is missing"
    assert SCHEMA_PATH.exists(), "loops/registry.schema.json is missing"


def test_registry_conforms_to_schema(registry, schema):
    jsonschema.validate(instance=registry, schema=schema)


def test_loop_ids_unique(registry):
    ids = [loop["id"] for loop in registry["loops"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate loop ids: {sorted(dupes)}"


def test_owners_are_team_members(registry):
    assert registry["owner"] in TEAM, f"registry owner {registry['owner']!r} not on the team"
    for loop in registry["loops"]:
        assert loop["owner"] in TEAM, f"{loop['id']}: owner {loop['owner']!r} not on the team"


def test_maturity_within_declared_cap(registry):
    """A loop's current maturity must never exceed its max_maturity cap."""
    for loop in registry["loops"]:
        cap = loop.get("max_maturity")
        if cap is None:
            continue
        assert _MATURITY_RANK[loop["maturity"]] <= _MATURITY_RANK[cap], (
            f"{loop['id']}: maturity {loop['maturity']} exceeds cap {cap}"
        )


def test_judgment_loops_capped_at_l1(registry):
    """SARO guardrail: high-risk loops over scoring/compliance/rule-packs stay
    propose-only (L1). This encodes 'loop the toil, gate the judgment'."""
    judgment = {"compliance-guard", "risk-scoring-guard", "rule-pack-guard", "drift-sentinel"}
    for loop in registry["loops"]:
        if loop["id"] in judgment:
            assert loop["max_maturity"] == "L1", (
                f"{loop['id']}: judgment loop must be capped at L1, got {loop['max_maturity']}"
            )


def test_gaps_are_not_active(registry):
    """Proposed/gap loops must not be marked active until implemented."""
    for loop in registry["loops"]:
        if loop["status"] == "gap":
            assert "proposed" in loop["cadence"].lower() or "proposed" in loop["implementation"].lower(), (
                f"{loop['id']}: gap loop should mark its cadence/implementation as proposed"
            )
