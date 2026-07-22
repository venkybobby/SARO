#!/usr/bin/env python3
"""SARO operator CLI (STORY-410) — ingest orchestration + demo-tenant reset.

Orchestration only: every pipeline step below already exists and is proven by
the STORY-407 E2E test (tests/test_story407_demo_corpus_builder.py). This file
wraps discover -> replay_backfill -> engine audit -> reconcile_backfill_gaps in
a first-class operator command, and adds a demo-tenant-scoped reset so
rehearsals can return to a clean state deterministically.

    python cli.py ingest --adapter bedrock --source {s3://bucket[/prefix] | ./path} \\
                          --tenant <tenant_id> --window <ISO8601>..<ISO8601> [--dry-run] [--json]
    python cli.py demo reset --tenant <tenant_id> --yes

Guard cleanliness (FR-5): this module imports only adapters/services/engine/models
code already covered by the STORY-336 no-external-model guard — no provider SDKs,
no bodies passed into coverage code paths.
"""

from __future__ import annotations

import json as _json
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import click

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.bedrock import (  # noqa: E402
    BedrockAdapterConfig,
    LocalLogStore,
    S3LogStore,
    discover_object_keys,
    iter_backfill_records,
    replay_backfill,
)
from adapters.bedrock.replay import _default_submit  # noqa: E402

# Demo-tenant structural guard (STORY-410 Decision Log Q2): no `is_demo` column
# exists on Tenant. This matches scripts/seed_demo_tenant.py's slug convention.
# There is no flag or override that bypasses this allowlist — `saro demo reset`
# refuses outright for any tenant whose slug is not in it (AC-4.1).
DEMO_TENANT_SLUGS = frozenset({"saro-demo"})

# Defaults matching the STORY-407 demo corpus (scripts/demo_manifest.yaml). A
# real client source (STORY-408) will carry its own account/region in per-tenant
# config; these are overridable flags so the demo path needs no extra options.
_DEFAULT_ACCOUNT_ID = "999888777666"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_ADAPTER = "bedrock"
_DEFAULT_CADENCE_SECONDS = 3600


class CliError(click.ClickException):
    """A CLI-level failure with a clear, operator-facing message."""


# ── shared helpers ──────────────────────────────────────────────────────────


def _parse_window(window: str) -> tuple[datetime, datetime]:
    start_s, sep, end_s = window.partition("..")
    if not sep or not start_s or not end_s:
        raise click.BadParameter(
            "must be ISO8601start..ISO8601end (e.g. 2026-07-06T00:00:00Z..2026-07-08T00:00:00Z)",
            param_hint="--window",
        )
    try:
        start = datetime.fromisoformat(start_s.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--window") from exc
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return start, end


def _parse_uuid(value: str, param_hint: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint=param_hint) from exc


def _make_store(source: str):
    if source.startswith("s3://"):
        rest = source[len("s3://") :]
        bucket, _, prefix = rest.partition("/")
        if not bucket:
            raise click.BadParameter(
                "s3:// source must include a bucket", param_hint="--source"
            )
        return S3LogStore(bucket, prefix_root=prefix)
    path = Path(source)
    if not path.exists():
        raise CliError(f"source path does not exist: {source!r}")
    return LocalLogStore(path)


def _resolve_tenant_store(db, tenant_id: uuid.UUID):
    """STORY-408 AC-5.1: resolve a tenant's cross-account log source config
    into a ready-to-use S3LogStore. Refuses (CliError, no store) if no config
    exists or it is disabled — `--source` is the explicit override path.

    Returns (store, account_id, region, allowed_s3_buckets, label).
    """
    from models import TenantLogSourceConfig
    from services.tenant_log_source_config import validate_source_config

    row = (
        db.query(TenantLogSourceConfig)
        .filter(TenantLogSourceConfig.tenant_id == tenant_id)
        .first()
    )
    if row is None:
        raise CliError(
            f"no log source config for tenant {tenant_id}; pass --source explicitly "
            "or configure a TenantLogSourceConfig row"
        )
    if not row.enabled:
        raise CliError(
            f"log source config for tenant {tenant_id} is disabled (enabled=False)"
        )

    config = validate_source_config(
        role_arn=row.role_arn,
        external_id=row.external_id,
        bucket=row.bucket,
        prefix=row.prefix,
        region=row.region,
        kms_key_arn=row.kms_key_arn,
    )
    store = S3LogStore.for_tenant(config)
    label = f"tenant-config:s3://{config.bucket}/{config.prefix}"
    return store, config.account_id, config.region, frozenset({config.bucket}), label


def _resolve_operator_user_id(db, tenant_id: uuid.UUID) -> uuid.UUID:
    from models import User

    user = db.query(User).filter(User.tenant_id == tenant_id).first()
    if user is None:
        raise CliError(
            f"no user found for tenant {tenant_id}; pass --user explicitly to attribute this ingest"
        )
    return user.id


def _session_factory():
    from database import _get_session_factory

    return _get_session_factory()


# ── ingest summary shape (FR-2) ─────────────────────────────────────────────


@dataclass
class IngestFinding:
    request_id: str
    timestamp: Optional[str]
    category: str


@dataclass
class IngestSummary:
    source: str
    tenant_id: str
    window_start: str
    window_end: str
    dry_run: bool = False
    objects_discovered: int = 0
    records_parsed: int = 0
    audits_submitted: int = 0
    audits_skipped_duplicate: int = 0
    malformed: int = 0
    audit_errors: int = 0
    findings: list[IngestFinding] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    coverage_attested: Optional[bool] = None
    elapsed_seconds: float = 0.0
    failed_key: Optional[str] = None
    error: Optional[str] = None
    partial: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "tenant_id": self.tenant_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "dry_run": self.dry_run,
            "objects_discovered": self.objects_discovered,
            "records_parsed": self.records_parsed,
            "audits_submitted": self.audits_submitted,
            "audits_skipped_duplicate": self.audits_skipped_duplicate,
            "malformed": self.malformed,
            "audit_errors": self.audit_errors,
            "findings_by_category": self._findings_by_category(),
            "gaps": self.gaps,
            "coverage_attested": self.coverage_attested,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "failed_key": self.failed_key,
            "error": self.error,
            "partial": self.partial,
        }

    def _findings_by_category(self) -> dict[str, list[dict[str, Optional[str]]]]:
        by_cat: dict[str, list[dict[str, Optional[str]]]] = {}
        for f in self.findings:
            by_cat.setdefault(f.category, []).append(
                {"request_id": f.request_id, "timestamp": f.timestamp}
            )
        return by_cat

    def render_text(self) -> str:
        lines = [
            f"source:              {self.source}",
            f"tenant:              {self.tenant_id}",
            f"window:              {self.window_start} .. {self.window_end}",
            f"dry_run:             {self.dry_run}",
            f"objects discovered:  {self.objects_discovered}",
            f"records parsed:      {self.records_parsed}",
        ]
        if not self.dry_run:
            lines += [
                f"audits submitted:    {self.audits_submitted}",
                f"audits deduped:      {self.audits_skipped_duplicate}",
                f"malformed records:   {self.malformed}",
                f"audit errors:        {self.audit_errors}",
                f"findings ({sum(len(v) for v in self._findings_by_category().values())}):",
            ]
            for category, items in sorted(self._findings_by_category().items()):
                lines.append(f"  {category}:")
                for item in items:
                    lines.append(
                        f"    - requestId={item['request_id']} at={item['timestamp']}"
                    )
            lines.append(f"gaps ({len(self.gaps)}):")
            for g in self.gaps:
                lines.append(
                    f"  - {g['gap_start']} .. {g['gap_end']} ({g['system_id']})"
                )
            lines.append(f"coverage_attested:   {self.coverage_attested}")
        lines.append(f"elapsed:             {self.elapsed_seconds:.3f}s")
        if self.failed_key:
            lines.append(f"FAILED at key:       {self.failed_key}")
            lines.append(f"error:               {self.error}")
        return "\n".join(lines)


def _run_ingest(
    *,
    source: str,
    tenant_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
    dry_run: bool,
    account_id: str,
    region: str,
    adapter_id: str,
    cadence_seconds: int,
    user_id: Optional[uuid.UUID],
    vertical: str,
    store: Any = None,
    allowed_s3_buckets: "frozenset[str]" = frozenset(),
) -> IngestSummary:
    from models import AuditTrace
    from services.observation_coverage_service import (
        coverage_report,
        record_checkpoint,
        reconcile_backfill_gaps,
    )

    t0 = time.monotonic()
    summary = IngestSummary(
        source=source,
        tenant_id=str(tenant_id),
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        dry_run=dry_run,
    )

    # STORY-408: a pre-built store (e.g. S3LogStore.for_tenant(...)) is used
    # as-is; --source (local/demo path) still goes through _make_store.
    if store is None:
        store = _make_store(source)
    try:
        keys = discover_object_keys(
            store,
            account_id=account_id,
            region=region,
            window_start=window_start,
            window_end=window_end,
        )
    except Exception as exc:  # noqa: BLE001 — surfaced as a clear CLI failure, not a raw traceback
        raise CliError(f"failed to discover objects under {source!r}: {exc}") from exc
    summary.objects_discovered = len(keys)

    # AC-1.3: iterate per object key so a hard read failure (unreadable source)
    # identifies the exact failing key and preserves everything ingested before it
    # (partial-batch behavior), rather than aborting the whole discovered set.
    records: list[tuple[str, dict[str, Any]]] = []
    ingested_keys = 0
    for key in keys:
        try:
            key_records = list(iter_backfill_records(store, [key]))
        except Exception as exc:  # noqa: BLE001 — surfaced as a clear CLI failure below
            summary.failed_key = key
            summary.error = str(exc)
            summary.partial = True
            break
        records.extend(key_records)
        ingested_keys += 1
    summary.records_parsed = len(records)

    if dry_run:
        summary.elapsed_seconds = time.monotonic() - t0
        if summary.failed_key:
            raise CliError(
                f"failed to read object {summary.failed_key!r}: {summary.error} "
                f"({ingested_keys}/{len(keys)} objects read before failure)"
            )
        return summary

    Session = _session_factory()
    db = Session()
    try:
        if user_id is None:
            user_id = _resolve_operator_user_id(db, tenant_id)

        config = BedrockAdapterConfig(
            tenant_id=tenant_id,
            user_id=user_id,
            vertical=vertical,
            adapter_id=adapter_id,
            allowed_s3_buckets=allowed_s3_buckets,
        )

        seen_systems: set[tuple[str, str]] = set()

        def _tracking_checkpoint(db_, **kwargs):
            seen_systems.add((kwargs["system_id"], kwargs["adapter_id"]))
            return record_checkpoint(db_, **kwargs)

        audit_index: dict[uuid.UUID, tuple[str, Optional[str]]] = {}

        def _tracking_submit(db_, submission, config_, envelope):
            audit_id = _default_submit(db_, submission, config_, envelope)
            audit_index[audit_id] = (
                envelope.request_id,
                envelope.timestamp.isoformat() if envelope.timestamp else None,
            )
            return audit_id

        result = replay_backfill(
            db,
            records,
            config,
            checkpoint=_tracking_checkpoint,
            submit=_tracking_submit,
        )
        summary.audits_submitted = result.audits_submitted
        summary.audits_skipped_duplicate = result.audits_skipped_duplicate
        summary.malformed = result.malformed
        summary.audit_errors = result.audit_errors

        if audit_index:
            traces = (
                db.query(AuditTrace)
                .filter(
                    AuditTrace.audit_id.in_(audit_index.keys()),
                    AuditTrace.check_type == "risk_domain",
                    AuditTrace.result == "flagged",
                )
                .all()
            )
            for t in traces:
                info = audit_index.get(t.audit_id)
                if info is None:
                    continue
                request_id, timestamp = info
                summary.findings.append(
                    IngestFinding(
                        request_id=request_id,
                        timestamp=timestamp,
                        category=t.check_name,
                    )
                )

        gaps: list[dict[str, Any]] = []
        attested_flags: list[bool] = []
        for system_id, adp_id in sorted(seen_systems):
            for gap in reconcile_backfill_gaps(
                db,
                tenant_id=tenant_id,
                system_id=system_id,
                adapter_id=adp_id,
                window_start=window_start,
                window_end=window_end,
                cadence_seconds=cadence_seconds,
            ):
                gaps.append(
                    {
                        "system_id": system_id,
                        "adapter_id": adp_id,
                        "gap_start": gap.gap_start.isoformat(),
                        "gap_end": gap.gap_end.isoformat() if gap.gap_end else None,
                    }
                )
            report = coverage_report(db, tenant_id, system_id, window_start, window_end)
            attested_flags.append(bool(report["coverage_attested"]))
        summary.gaps = gaps
        # coverage_attested means "at least one observation was recorded for every
        # ingested system in this window" (services/observation_coverage_service.py
        # coverage_report) — it is independent of whether gaps were found; a window
        # can be fully attested AND contain a disclosed gap (that is the point).
        summary.coverage_attested = all(attested_flags) if attested_flags else None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    summary.elapsed_seconds = time.monotonic() - t0

    if summary.failed_key:
        raise CliError(
            f"failed to read object {summary.failed_key!r}: {summary.error} "
            f"({ingested_keys}/{len(keys)} objects ingested before failure; "
            f"{summary.audits_submitted} audits submitted from objects read so far)"
        )
    if summary.audit_errors:
        raise CliError(
            f"{summary.audit_errors} record(s) failed engine audit during ingest — "
            "see logs for detail; objects ingested before the failure are reported above"
        )
    return summary


# ── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version="1.0.0", prog_name="saro")
def cli() -> None:
    """SARO operator CLI — backfill ingest + demo-tenant reset (STORY-410)."""


@cli.command()
@click.option(
    "--adapter", default=_DEFAULT_ADAPTER, show_default=True, help="Adapter name."
)
@click.option(
    "--source",
    default=None,
    help="s3://bucket[/prefix] or a local directory path. Omit to resolve the "
    "tenant's configured cross-account log source (STORY-408).",
)
@click.option("--tenant", required=True, help="Tenant UUID to ingest into.")
@click.option("--window", required=True, help="ISO8601start..ISO8601end")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Discover + parse only; write nothing.",
)
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON."
)
@click.option(
    "--account-id",
    default=None,
    help=f"Overrides the tenant config's derived account id (--source mode default: {_DEFAULT_ACCOUNT_ID}).",
)
@click.option(
    "--region",
    default=None,
    help=f"Overrides the tenant config's region (--source mode default: {_DEFAULT_REGION}).",
)
@click.option(
    "--cadence-seconds", default=_DEFAULT_CADENCE_SECONDS, show_default=True, type=int
)
@click.option("--vertical", default="general", show_default=True)
@click.option(
    "--user", "user", default=None, help="Operator user UUID to attribute audits to."
)
def ingest(
    adapter: str,
    source: Optional[str],
    tenant: str,
    window: str,
    dry_run: bool,
    as_json: bool,
    account_id: Optional[str],
    region: Optional[str],
    cadence_seconds: int,
    vertical: str,
    user: Optional[str],
) -> None:
    """Run the full backfill pipeline: discover -> replay -> audit -> reconcile."""
    if adapter != "bedrock":
        raise click.BadParameter(
            f"unsupported adapter {adapter!r} (only 'bedrock' today)",
            param_hint="--adapter",
        )
    tenant_id = _parse_uuid(tenant, "--tenant")
    user_id = _parse_uuid(user, "--user") if user else None
    window_start, window_end = _parse_window(window)

    store: Any = None
    allowed_s3_buckets: "frozenset[str]" = frozenset()
    effective_account_id = account_id
    effective_region = region
    label = source

    try:
        if source is None:
            # STORY-408 AC-5.1: resolve the tenant's cross-account source config.
            Session = _session_factory()
            db = Session()
            try:
                (
                    store,
                    resolved_account_id,
                    resolved_region,
                    allowed_s3_buckets,
                    label,
                ) = _resolve_tenant_store(db, tenant_id)
            finally:
                db.close()
            effective_account_id = account_id or resolved_account_id
            effective_region = region or resolved_region
        else:
            effective_account_id = account_id or _DEFAULT_ACCOUNT_ID
            effective_region = region or _DEFAULT_REGION
        assert label is not None  # set above on both branches

        summary = _run_ingest(
            source=label,
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            dry_run=dry_run,
            account_id=effective_account_id,
            region=effective_region,
            adapter_id=adapter,
            cadence_seconds=cadence_seconds,
            user_id=user_id,
            vertical=vertical,
            store=store,
            allowed_s3_buckets=allowed_s3_buckets,
        )
    except CliError as exc:
        # Partial-batch behavior (AC-1.3): still surface what was ingested before exiting non-zero.
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc

    if as_json:
        click.echo(_json.dumps(summary.to_dict(), indent=2))
    else:
        click.echo(summary.render_text())


@cli.group()
def demo() -> None:
    """Demo-tenant operations."""


@demo.command("reset")
@click.option(
    "--tenant", required=True, help="Tenant UUID to reset. Must be a demo tenant."
)
@click.option("--yes", is_flag=True, default=False, help="Actually perform the delete.")
def demo_reset(tenant: str, yes: bool) -> None:
    """Delete findings, dispositions, checkpoints, and gaps for a demo tenant only.

    AC-4.1: refuses structurally unless the tenant's slug is in DEMO_TENANT_SLUGS.
    There is no flag combination that resets a non-demo tenant.
    """
    from models import (
        Audit,
        AuditEvent,
        Disposition,
        Notification,
        ObservationCheckpoint,
        ObservationGap,
        Tenant,
    )

    tenant_id = _parse_uuid(tenant, "--tenant")

    # Audit cascades to ScanReport/AuditMetadata/AuditTrace via DB-level ON DELETE
    # CASCADE (models.py) — bulk .delete() bypasses ORM-level cascade, so this relies
    # on the FK constraint itself. AuditEvent/Notification are deleted explicitly:
    # they are not children of Audit (e.g. disposition actions write AuditEvent rows
    # independently), so AC-4.4's "reset -> re-ingest reproduces a first-run ingest"
    # would otherwise leave a stale self-audit/notification trail behind after reset.
    tenant_scoped_models = (
        Audit,
        Disposition,
        ObservationCheckpoint,
        ObservationGap,
        AuditEvent,
        Notification,
    )

    Session = _session_factory()
    db = Session()
    try:
        t = db.get(Tenant, tenant_id)
        if t is None:
            raise CliError(f"tenant not found: {tenant_id}")
        if t.slug not in DEMO_TENANT_SLUGS:
            raise CliError(
                f"refusing to reset tenant {tenant_id} (slug={t.slug!r}): "
                f"not in the demo-tenant allowlist {sorted(DEMO_TENANT_SLUGS)}"
            )

        counts = {
            model.__tablename__: db.query(model)
            .filter(model.tenant_id == tenant_id)
            .count()
            for model in tenant_scoped_models
        }

        if not yes:
            click.echo(f"Would delete for tenant {tenant_id} (slug={t.slug}):")
            for k, v in counts.items():
                click.echo(f"  {k}: {v}")
            click.echo("Pass --yes to actually delete.")
            return

        for model in tenant_scoped_models:
            db.query(model).filter(model.tenant_id == tenant_id).delete(
                synchronize_session=False
            )
        db.commit()

        click.echo(f"Reset tenant {tenant_id} (slug={t.slug}):")
        for k, v in counts.items():
            click.echo(f"  deleted {v} {k}")
    except CliError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@cli.group()
def tenant() -> None:
    """Tenant provisioning (STORY-373)."""


@tenant.command("provision")
@click.option("--name", required=True, help="Display name, e.g. 'SummitCare Health'.")
@click.option("--slug", required=True, help="URL-safe identifier, e.g. 'summitcare'.")
@click.option("--admin-email", required=True, help="Email for the tenant's first admin.")
@click.option(
    "--baa-confirmed",
    is_flag=True,
    default=False,
    help="Confirm an executed BAA is in place (INV-6). Provisioning refuses without it.",
)
@click.option("--vertical", default="general", show_default=True)
@click.option(
    "--actor", default=None, help="Operator identity for the audit trail. Defaults to $USER."
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine-readable output.")
def tenant_provision(
    name: str,
    slug: str,
    admin_email: str,
    baa_confirmed: bool,
    vertical: str,
    actor: Optional[str],
    as_json: bool,
) -> None:
    """Provision a tenant, its admin user, and an adapter placeholder.

    Idempotent: re-running against an existing slug writes nothing and reports
    what is already there. It deliberately does NOT reconcile drift — an
    operator re-running to check state must not have configuration changed
    under them (see FND-058).
    """
    import os

    from services.tenant_provisioning import (
        BAAGateNotConfirmed,
        ProvisioningError,
        provision_tenant,
        verify_isolation,
    )

    actor = actor or os.environ.get("USER") or os.environ.get("USERNAME") or "operator"
    db = _session_factory()()
    try:
        result = provision_tenant(
            db,
            name=name,
            slug=slug,
            admin_email=admin_email,
            baa_confirmed=baa_confirmed,
            actor=actor,
            vertical=vertical,
        )
        isolation = verify_isolation(db, result.tenant_id) if result.created else None
    except BAAGateNotConfirmed as exc:
        db.rollback()
        raise CliError(str(exc)) from exc
    except ProvisioningError as exc:
        db.rollback()
        raise CliError(str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if as_json:
        payload = result.summary()
        if isolation:
            payload["isolation"] = isolation
        # The generated password is deliberately absent from JSON output — it
        # would land in shell history, CI logs, and anything piping this.
        click.echo(_json.dumps(payload, indent=2, sort_keys=True))
        return

    if not result.created:
        click.echo(f"Tenant {slug!r} already exists ({result.tenant_id}) — nothing written.")
        for note in result.notes:
            click.echo(f"  note: {note}")
        return

    click.echo(f"Provisioned tenant {slug!r} ({result.tenant_id})")
    click.echo(f"  admin: {result.admin_email} ({result.admin_user_id})")
    click.echo("")
    click.echo("  One-time password (not stored, not logged, shown once):")
    click.echo(f"    {result.generated_password}")
    click.echo("")
    for note in result.notes:
        click.echo(f"  note: {note}")

    if isolation:
        state = "PASS" if isolation["isolated"] else "FAIL"
        click.echo(f"  isolation check: {state} — {isolation['detail']}")
        if not isolation["meaningful"]:
            click.echo(
                "  note: no other tenants exist yet, so this check cannot yet "
                "demonstrate isolation — re-run it once a second tenant exists."
            )
        if not isolation["isolated"]:
            raise CliError("post-provision isolation check FAILED — investigate before use")


@tenant.command("verify-isolation")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID to check.")
@click.option("--json", "as_json", is_flag=True, default=False)
def tenant_verify_isolation(tenant_id: str, as_json: bool) -> None:
    """Re-run the post-provision isolation check for a tenant."""
    from services.tenant_provisioning import verify_isolation

    parsed = _parse_uuid(tenant_id, "--tenant")
    db = _session_factory()()
    try:
        result = verify_isolation(db, parsed)
    finally:
        db.close()

    if as_json:
        click.echo(_json.dumps(result, indent=2, sort_keys=True))
    else:
        click.echo(f"isolation: {'PASS' if result['isolated'] else 'FAIL'} — {result['detail']}")
        if not result["meaningful"]:
            click.echo("note: no other tenants exist — this check cannot yet prove isolation.")
    if not result["isolated"]:
        raise CliError("isolation check FAILED")


@cli.group()
def meter() -> None:
    """Usage metering — exact recount + export (STORY-374)."""


@meter.command("verify")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID.")
@click.option("--period", default=None, help="YYYY-MM (default: current period).")
@click.option("--json", "as_json", is_flag=True, default=False)
def meter_verify(tenant_id: str, period: Optional[str], as_json: bool) -> None:
    """Recount every metered value against its authoritative table (0% exact).

    Metering underlies invoicing, so a meter that is merely close is a bug, not
    an acceptable variance — this requires an exact match and exits non-zero if
    any meter disagrees with its source table.
    """
    import services.metering_service as metering

    parsed = _parse_uuid(tenant_id, "--tenant")
    db = _session_factory()()
    try:
        result = metering.verify_exact(db, parsed, period)
    finally:
        db.close()

    if as_json:
        click.echo(_json.dumps(result, indent=2, sort_keys=True))
    else:
        for chk in result["checks"]:
            state = "OK" if chk["exact"] else f"DRIFT {chk['delta']:+d}"
            click.echo(f"  {chk['meter_key']}: metered={chk['metered']} "
                       f"authoritative={chk['authoritative']} [{state}]")
        if result["unverifiable_meters"]:
            click.echo(f"  unverifiable (no single authoritative table): "
                       f"{result['unverifiable_meters']}")
    if not result["exact"]:
        raise CliError("meter verification FAILED — a meter does not match its source table")


@meter.command("export")
@click.option("--tenant", "tenant_id", required=True, help="Tenant UUID.")
@click.option("--period", required=True, help="YYYY-MM.")
@click.option(
    "--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", show_default=True
)
@click.option("--out", type=click.Path(), default=None, help="Write to a file instead of stdout.")
def meter_export(tenant_id: str, period: str, fmt: str, out: Optional[str]) -> None:
    """Export a tenant's monthly usage as CSV or JSON.

    Export ONLY — SARO has no payment-processor integration. Turning usage into
    an invoice happens in the biller of record; this is the evidence-grade
    source it draws from.
    """
    import services.metering_service as metering

    parsed = _parse_uuid(tenant_id, "--tenant")
    db = _session_factory()()
    try:
        content = (
            metering.export_csv(db, parsed, period)
            if fmt == "csv"
            else metering.export_json(db, parsed, period)
        )
    finally:
        db.close()

    if out:
        Path(out).write_text(content, encoding="utf-8")
        click.echo(f"wrote {out}")
    else:
        click.echo(content, nl=False)


@cli.command("feedback-triage")
@click.option("--status", "status_filter", default=None, help="Filter by triage status.")
@click.option("--json", "as_json", is_flag=True, default=False)
def feedback_triage(status_filter: Optional[str], as_json: bool) -> None:
    """Internal pilot-feedback triage list (STORY-382).

    Supports the weekly triage ritual (docs/ops/feedback-triage.md): every item
    reaches a story id, declined-with-reason, or parked.
    """
    import services.feedback_service as fb

    db = _session_factory()()
    try:
        items = fb.list_for_triage(db, status=status_filter)
        rows = [
            {
                "id": str(i.id),
                "screen": i.screen,
                "category": i.category,
                "severity": i.severity,
                "triage_status": i.triage_status,
                "story_id": i.story_id,
            }
            for i in items
        ]
    finally:
        db.close()

    if as_json:
        click.echo(_json.dumps(rows, indent=2, sort_keys=True))
    else:
        untriaged = sum(1 for r in rows if r["triage_status"] == "new")
        click.echo(f"{len(rows)} feedback item(s), {untriaged} untriaged:")
        for r in rows:
            link = f" -> {r['story_id']}" if r["story_id"] else ""
            click.echo(f"  [{r['triage_status']}] {r['severity']}/{r['category']} "
                       f"({r['screen']}){link}")


@cli.command("analytics-summary")
@click.option("--json", "as_json", is_flag=True, default=False)
def analytics_summary(as_json: bool) -> None:
    """Founder-facing product-analytics summary (STORY-381).

    Aggregates the first-party product_events across all tenants — event counts
    and the two key funnels (login→attestation, subscribe→first-evaluation). Runs
    with operator authority; the underlying events carry no PII by construction.
    """
    from sqlalchemy import func

    from models import ProductEvent
    import services.product_analytics as analytics

    db = _session_factory()()
    try:
        rows = (
            db.query(ProductEvent.event_name, func.count(ProductEvent.id))
            .group_by(ProductEvent.event_name)
            .all()
        )
        counts = {name: int(n) for name, n in rows}
    finally:
        db.close()

    def _rate(numer: str, denom: str) -> Optional[float]:
        d = counts.get(denom, 0)
        return round(counts.get(numer, 0) / d, 4) if d else None

    summary: dict[str, Any] = {
        "event_counts": {name: counts.get(name, 0) for name in sorted(analytics.EVENT_NAMES)},
        "funnels": {
            "login_to_attestation_view": _rate(
                analytics.ATTESTATION_VIEWED, analytics.LOGIN
            ),
            "subscribe_to_first_evaluation": _rate(
                analytics.FIRST_EVALUATION, analytics.RULE_PACK_SUBSCRIBED
            ),
        },
    }

    if as_json:
        click.echo(_json.dumps(summary, indent=2, sort_keys=True))
    else:
        click.echo("Event counts:")
        for name, n in summary["event_counts"].items():
            click.echo(f"  {name}: {n}")
        click.echo("Funnels (conversion rate):")
        for name, rate in summary["funnels"].items():
            click.echo(f"  {name}: {rate if rate is not None else 'n/a (no entries)'}")


if __name__ == "__main__":
    cli()
