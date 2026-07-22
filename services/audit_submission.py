"""Synchronous audit submission (STORY-406).

The HTTP ingest route (`routers/ingest.py:_run_audit_background`) runs the engine
in a FastAPI BackgroundTask. Backfill adapters have no request context and want
a blocking call that returns the ``audit_id``. This is that entry point.

It deliberately does NOT emit an observation-coverage heartbeat: for the Bedrock
backfill, coverage is owned by the adapter's envelope-only branch
(`adapters.bedrock.replay.emit_coverage`) using the stream cursor as watermark.
Keeping coverage out of the audit path preserves the INV-2 seam (the branch that
touches bodies never writes coverage evidence).

Engine + trace-persistence are injectable so the plumbing is unit-testable
without a live engine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from engine import SARoEngine
from models import Audit, AuditMetadata, ScanReport

logger = logging.getLogger(__name__)

EngineFactory = Callable[[Session], Any]
TracePersister = Callable[[Any, uuid.UUID, Session], Any]


def _default_persist_traces(engine_obj: Any, audit_id: uuid.UUID, db: Session) -> None:
    # Lazy import mirrors the existing route (avoids a routers<-services cycle at load).
    from routers.scan import _persist_traces

    _persist_traces(engine_obj, audit_id, db)


def submit_audit_sync(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    prompt: str,
    raw_output: str,
    source_model: str,
    vertical: str = "general",
    metadata: Optional[dict[str, Any]] = None,
    dataset_name: Optional[str] = None,
    ingestion_method: str = "adapter",
    engine_factory: EngineFactory = SARoEngine,
    persist_traces: TracePersister = _default_persist_traces,
) -> uuid.UUID:
    """Run the SARO engine for one output synchronously; return the audit id.

    Creates the ``Audit`` + ``AuditMetadata`` rows, runs the engine, persists the
    ``ScanReport`` (with adapter metadata folded in) and hash-chained traces, and
    marks the audit terminal. On any failure the audit is marked ``failed`` and
    the exception re-raised so the caller can tally it (replay fails soft).
    """
    audit_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    audit = Audit(
        id=audit_id,
        tenant_id=tenant_id,
        user_id=user_id,
        batch_id=None,
        dataset_name=dataset_name or f"Ingest:{source_model}",
        sample_count=1,
        status="running",
        prompt_text=prompt,
        raw_output_text=raw_output,
        created_at=now,
    )
    # FND-4: the initial insert must be inside try/rollback too — a constraint or
    # size error here (e.g. an oversized resolved body) would otherwise leave the
    # SHARED session in a PendingRollbackError state and cascade to every later
    # record in a backfill corpus.
    try:
        db.add(audit)
        db.add(
            AuditMetadata(
                audit_id=audit_id,
                source_model=source_model,
                ingestion_method=ingestion_method,
                vertical=vertical,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.error(
            "submit_audit_sync: initial insert for %s failed", audit_id, exc_info=True
        )
        raise

    try:
        engine_obj = engine_factory(db)
        report = engine_obj.run_output_audit(
            audit_id=audit_id,
            raw_output=raw_output,
            prompt=prompt,
            source_model=source_model,
            metadata=metadata,
        )

        db.add(
            ScanReport(
                audit_id=audit_id,
                tenant_id=tenant_id,
                mit_coverage_score=report.mit_coverage.score,
                fixed_delta=report.fixed_delta.delta,
                overall_risk_score=report.bayesian_scores.overall,
                confidence_score=report.confidence_score,
                report_json={
                    **report.model_dump(mode="json"),
                    "source_model": source_model,
                    "adapter_metadata": metadata or {},
                },
            )
        )
        persist_traces(engine_obj, audit_id, db)
        audit.status = report.status
        audit.completed_at = datetime.now(tz=timezone.utc)
        db.commit()

        # STORY-374: meter the evaluate/attest boundary AFTER the attestation is
        # durably committed. One ScanReport row is one attestation, deduped by
        # audit id, so these two meters recount EXACTLY against the scan_reports
        # table (metering_service.verify_exact). safe_increment fails open — a
        # metering fault must never block or unwind an attestation that landed.
        import services.metering_service as _metering

        _metering.safe_increment(
            db, tenant_id=tenant_id, meter_key=_metering.EVALUATIONS_EXECUTED,
            idempotency_key=f"eval:{audit_id}",
        )
        _metering.safe_increment(
            db, tenant_id=tenant_id, meter_key=_metering.ATTESTATIONS_ISSUED,
            idempotency_key=f"attest:{audit_id}",
        )

        # STORY-381: emit first_evaluation once per tenant (funnel conversion).
        # Guarded by an existence check so it fires only on the first ever
        # evaluation; fail-open so analytics never unwinds an attestation.
        try:
            import services.product_analytics as _analytics
            from models import ProductEvent

            seen = (
                db.query(ProductEvent.id)
                .filter(
                    ProductEvent.tenant_id == tenant_id,
                    ProductEvent.event_name == _analytics.FIRST_EVALUATION,
                )
                .first()
            )
            if seen is None:
                _analytics.safe_record(
                    db, tenant_id=tenant_id, event_name=_analytics.FIRST_EVALUATION,
                    properties={"surface": "api", "outcome": "success"},
                )
        except Exception:  # noqa: BLE001 — analytics must never break the attest path
            db.rollback()
    except Exception:
        db.rollback()
        try:
            failed = db.get(Audit, audit_id)
            if failed is not None:
                failed.status = "failed"
                failed.completed_at = datetime.now(tz=timezone.utc)
                db.commit()
        except Exception:  # noqa: BLE001 — best-effort status write
            db.rollback()
        logger.error("submit_audit_sync: audit %s failed", audit_id, exc_info=True)
        raise

    return audit_id
