"""STORY-401 — Policy-Trigger Schema tests.

AC coverage (see specs/stories/STORY-401.md):
- AC-1 fields present on model + schema (unit + integration)
- AC-2 block requires latency_budget_ms AND on_timeout (unit)
- AC-3 sample requires sample_rate in [0,1] (unit)
- AC-4 mirror rejects budget/timeout/rate (unit)
- AC-5 valid config per mode round-trips (integration)
- AC-6 safe default = mirror, null budget/timeout/rate (integration)
- AC-7 policy_version increments by 1 on a trigger-config change only (integration)
- AC-8 cross-tenant read/write denied (integration)
- AC-9 Pydantic parity with the model-layer validation (unit)

Invariant guard: schema/config only — no network / external-model call introduced.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy.types as sa_types

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base  # noqa: E402
from models import Policy, Tenant  # noqa: E402
from schemas import MAX_LATENCY_BUDGET_MS, PolicyCreate, PolicyUpdate  # noqa: E402
from services import policy_service  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    for tid, slug in ((TENANT_A, "ta-401"), (TENANT_B, "tb-401")):
        if session.query(Tenant).filter(Tenant.id == tid).first() is None:
            session.add(Tenant(id=tid, name=f"T-{slug}", slug=slug))
    session.commit()
    try:
        yield session
    finally:
        session.query(Policy).delete()
        session.commit()
        session.close()


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3 / AC-4 / AC-9 — Pydantic validation (pure, no DB)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_block_valid_config_accepted() -> None:
    p = PolicyCreate(
        name="p", trigger_mode="block", latency_budget_ms=200, on_timeout="closed"
    )
    assert p.trigger_mode == "block"
    assert p.latency_budget_ms == 200
    assert p.on_timeout == "closed"


@pytest.mark.unit
def test_mirror_valid_config_accepted() -> None:
    p = PolicyCreate(name="p", trigger_mode="mirror")
    assert p.trigger_mode == "mirror"
    assert (
        p.latency_budget_ms is None and p.on_timeout is None and p.sample_rate is None
    )


@pytest.mark.unit
def test_sample_valid_config_accepted() -> None:
    p = PolicyCreate(name="p", trigger_mode="sample", sample_rate=0.25)
    assert p.sample_rate == 0.25


@pytest.mark.unit
@pytest.mark.parametrize(
    "kwargs",
    [
        {"trigger_mode": "block"},  # no budget, no timeout
        {"trigger_mode": "block", "latency_budget_ms": 100},  # no timeout
        {"trigger_mode": "block", "on_timeout": "open"},  # no budget
    ],
)
def test_block_missing_budget_or_timeout_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        PolicyCreate(name="p", **kwargs)


@pytest.mark.unit
@pytest.mark.parametrize("rate", [None, -0.1, 1.5])
def test_sample_missing_or_out_of_range_rate_rejected(rate) -> None:
    kwargs = {} if rate is None else {"sample_rate": rate}
    with pytest.raises(ValueError):
        PolicyCreate(name="p", trigger_mode="sample", **kwargs)


@pytest.mark.unit
@pytest.mark.parametrize(
    "extra",
    [{"latency_budget_ms": 100}, {"on_timeout": "open"}, {"sample_rate": 0.5}],
)
def test_mirror_with_any_extra_rejected(extra) -> None:
    with pytest.raises(ValueError):
        PolicyCreate(name="p", trigger_mode="mirror", **extra)


@pytest.mark.unit
@pytest.mark.parametrize("rate", [0.0, 1.0])
def test_sample_rate_boundaries_valid(rate) -> None:
    assert (
        PolicyCreate(name="p", trigger_mode="sample", sample_rate=rate).sample_rate
        == rate
    )


@pytest.mark.unit
def test_block_nonpositive_budget_rejected() -> None:
    with pytest.raises(ValueError):
        PolicyCreate(
            name="p", trigger_mode="block", latency_budget_ms=0, on_timeout="open"
        )


@pytest.mark.unit
@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_rejected(name) -> None:
    with pytest.raises(ValueError):
        PolicyCreate(name=name, trigger_mode="mirror")


@pytest.mark.unit
def test_bad_trigger_mode_rejected() -> None:
    with pytest.raises(ValueError):
        # Intentionally-invalid trigger_mode for the negative test.
        PolicyCreate(name="p", trigger_mode="explode")  # type: ignore[arg-type]


@pytest.mark.unit
def test_create_and_validator_share_one_function() -> None:
    """AC-9: PolicyCreate and the service both route through validate_trigger_config.

    PolicyUpdate intentionally does NOT validate combos at the schema layer — a
    partial payload lacks the row's current state, so the merged combo is validated
    in the service (test_update_invalid_merged_combo_rejected). Here we assert the
    create path and the shared function agree on a known-bad combo.
    """
    from schemas import validate_trigger_config

    with pytest.raises(ValueError):
        validate_trigger_config("block", None, None, None)
    with pytest.raises(ValueError):
        PolicyCreate(name="p", trigger_mode="block")  # same rule, via the schema


@pytest.mark.unit
@pytest.mark.parametrize("budget", [MAX_LATENCY_BUDGET_MS + 1, 10**12])
def test_block_budget_over_ceiling_rejected(budget) -> None:
    with pytest.raises(ValueError):
        PolicyCreate(
            name="p", trigger_mode="block", latency_budget_ms=budget, on_timeout="open"
        )


@pytest.mark.unit
def test_name_over_max_length_rejected() -> None:
    with pytest.raises(ValueError):
        PolicyCreate(name="x" * 501, trigger_mode="mirror")


# ---------------------------------------------------------------------------
# AC-5 — round-trip per mode (DB)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload",
    [
        PolicyCreate(
            name="blk", trigger_mode="block", latency_budget_ms=150, on_timeout="open"
        ),
        PolicyCreate(name="mir", trigger_mode="mirror"),
        PolicyCreate(name="smp", trigger_mode="sample", sample_rate=0.4),
    ],
)
def test_roundtrip_each_mode(db, payload) -> None:
    created = policy_service.create_policy(db, TENANT_A, payload)
    fetched = policy_service.get_policy(db, TENANT_A, created.id)
    assert fetched is not None
    assert fetched.tenant_id == TENANT_A
    assert fetched.trigger_mode == payload.trigger_mode
    assert fetched.latency_budget_ms == payload.latency_budget_ms
    assert fetched.on_timeout == payload.on_timeout
    assert fetched.sample_rate == payload.sample_rate
    assert fetched.policy_version == 1


# ---------------------------------------------------------------------------
# AC-6 — safe default = mirror
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_default_mode_is_mirror_with_nulls(db) -> None:
    """A policy created with only required fields backfills to mirror / nulls."""
    created = policy_service.create_policy(db, TENANT_A, PolicyCreate(name="defaulted"))
    assert created.trigger_mode == "mirror"
    assert created.latency_budget_ms is None
    assert created.on_timeout is None
    assert created.sample_rate is None


# ---------------------------------------------------------------------------
# AC-7 — policy_version increments on a trigger-config change only
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_version_increments_on_trigger_config_change(db) -> None:
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="v", trigger_mode="sample", sample_rate=0.2)
    )
    assert p.policy_version == 1
    updated = policy_service.update_policy(
        db, TENANT_A, p.id, PolicyUpdate(sample_rate=0.8)
    )
    assert updated.policy_version == 2
    again = policy_service.update_policy(
        db, TENANT_A, p.id, PolicyUpdate(trigger_mode="mirror", sample_rate=None)
    )
    assert again.policy_version == 3


@pytest.mark.integration
def test_version_unchanged_on_non_trigger_change(db) -> None:
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="v2", trigger_mode="mirror")
    )
    updated = policy_service.update_policy(
        db, TENANT_A, p.id, PolicyUpdate(name="renamed")
    )
    assert updated.name == "renamed"
    assert updated.policy_version == 1


@pytest.mark.integration
def test_version_unchanged_on_same_value_trigger_write(db) -> None:
    """AC-7: re-stating a trigger field with its current value does not bump the version."""
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="same", trigger_mode="sample", sample_rate=0.3)
    )
    updated = policy_service.update_policy(
        db, TENANT_A, p.id, PolicyUpdate(trigger_mode="sample", sample_rate=0.3)
    )
    assert updated.policy_version == 1


@pytest.mark.integration
def test_mode_only_restate_uses_existing_fields(db) -> None:
    """AC-9 (service): restating trigger_mode on an already-valid policy is accepted
    because the merged combo (mode + existing rate) is what gets validated — the bug
    the removed PolicyUpdate schema validator would have caused."""
    p = policy_service.create_policy(
        db,
        TENANT_A,
        PolicyCreate(name="restate", trigger_mode="sample", sample_rate=0.5),
    )
    ok = policy_service.update_policy(
        db, TENANT_A, p.id, PolicyUpdate(trigger_mode="sample", name="renamed")
    )
    assert (
        ok.trigger_mode == "sample" and ok.sample_rate == 0.5 and ok.name == "renamed"
    )


@pytest.mark.integration
def test_block_to_sample_with_rate_accepted(db) -> None:
    """A mode switch that supplies the newly-required field is accepted (and bumps version)."""
    p = policy_service.create_policy(
        db,
        TENANT_A,
        PolicyCreate(
            name="b2s", trigger_mode="block", latency_budget_ms=100, on_timeout="open"
        ),
    )
    ok = policy_service.update_policy(
        db,
        TENANT_A,
        p.id,
        PolicyUpdate(
            trigger_mode="sample",
            latency_budget_ms=None,
            on_timeout=None,
            sample_rate=0.6,
        ),
    )
    assert ok.trigger_mode == "sample" and ok.sample_rate == 0.6
    assert ok.policy_version == 2


@pytest.mark.integration
def test_update_invalid_merged_combo_rejected(db) -> None:
    """AC-9 (service): an update whose merged combo is invalid is rejected by the service."""
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="merge", trigger_mode="mirror")
    )
    # mirror → block but no budget/timeout supplied: merged combo invalid.
    with pytest.raises(ValueError):
        policy_service.update_policy(
            db, TENANT_A, p.id, PolicyUpdate(trigger_mode="block")
        )


@pytest.mark.integration
def test_explicit_null_name_rejected(db) -> None:
    """Security: an explicit null name in a partial update is rejected, not a DB error."""
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="keep", trigger_mode="mirror")
    )
    with pytest.raises(ValueError):
        policy_service.update_policy(db, TENANT_A, p.id, PolicyUpdate(name=None))


@pytest.mark.integration
def test_switch_block_to_mirror_must_clear_budget(db) -> None:
    """Edge: block→mirror without clearing budget/timeout is rejected (no silent misconfig)."""
    p = policy_service.create_policy(
        db,
        TENANT_A,
        PolicyCreate(
            name="sw", trigger_mode="block", latency_budget_ms=100, on_timeout="closed"
        ),
    )
    with pytest.raises(ValueError):
        policy_service.update_policy(
            db, TENANT_A, p.id, PolicyUpdate(trigger_mode="mirror")
        )
    ok = policy_service.update_policy(
        db,
        TENANT_A,
        p.id,
        PolicyUpdate(trigger_mode="mirror", latency_budget_ms=None, on_timeout=None),
    )
    assert ok.trigger_mode == "mirror" and ok.latency_budget_ms is None


# ---------------------------------------------------------------------------
# AC-8 — tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cross_tenant_read_denied(db) -> None:
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="secret", trigger_mode="mirror")
    )
    # Tenant B cannot see tenant A's policy.
    assert policy_service.get_policy(db, TENANT_B, p.id) is None
    assert all(x.id != p.id for x in policy_service.list_policies(db, TENANT_B))
    # Tenant A still can.
    assert policy_service.get_policy(db, TENANT_A, p.id) is not None


@pytest.mark.integration
def test_cross_tenant_write_denied(db) -> None:
    p = policy_service.create_policy(
        db, TENANT_A, PolicyCreate(name="owned-by-a", trigger_mode="mirror")
    )
    with pytest.raises(policy_service.PolicyNotFoundError):
        policy_service.update_policy(db, TENANT_B, p.id, PolicyUpdate(name="hijack"))
    # Unchanged for the real owner.
    owned = policy_service.get_policy(db, TENANT_A, p.id)
    assert owned is not None
    assert owned.name == "owned-by-a"


# ---------------------------------------------------------------------------
# Invariant guard — no network / external-model imports in new modules
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_network_or_model_calls_in_policy_service() -> None:
    import inspect

    src = inspect.getsource(policy_service)
    for needle in ("requests", "httpx", "urllib", "anthropic", "openai", "socket"):
        assert needle not in src, (
            f"policy_service must not reference {needle} (Epic 14 invariant)"
        )
