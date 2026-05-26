"""
HuggingFace Dataset Sampler — S-002

Pulls samples from HuggingFace datasets and inserts them into the
hf_sample_queue table for processing by the hf_processor router.

Usage:
    python scripts/hf_sampler.py \
        --dataset allenai/WildChat-1M \
        --vertical healthcare \
        --tenant-id <uuid> \
        --samples 200 \
        --source-model gpt-4

Environment variables:
    DATABASE_URL  — PostgreSQL connection string (required)
    HF_TOKEN      — HuggingFace API token (optional, for gated datasets)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

import structlog

# Ensure repo root is on path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger(__name__)

# ── Vertical → dataset defaults ───────────────────────────────────────────────

_VERTICAL_DATASETS: dict[str, dict] = {
    "healthcare": {
        "dataset": "medalpaca/medical_meadow_wikidoc",
        "prompt_col": "input",
        "output_col": "output",
        "source_model": "unknown",
    },
    "finance": {
        "dataset": "gbharti/finance-alpaca",
        "prompt_col": "input",
        "output_col": "output",
        "source_model": "unknown",
    },
    "legal": {
        "dataset": "nguha/legalbench",
        "prompt_col": "text",
        "output_col": "answer",
        "source_model": "unknown",
    },
    "general": {
        "dataset": "allenai/WildChat-1M",
        "prompt_col": "conversation",
        "output_col": "conversation",
        "source_model": "unknown",
    },
}

_DEFAULT_PROMPT_COLS = ["prompt", "question", "input", "instruction", "text", "query"]
_DEFAULT_OUTPUT_COLS = ["response", "output", "answer", "completion", "text"]


def _resolve_columns(ds_row: dict, prompt_col: str | None, output_col: str | None) -> tuple[str, str]:
    """Resolve prompt and output column names from a dataset row."""
    cols = list(ds_row.keys())

    if prompt_col and prompt_col in cols:
        p_col = prompt_col
    else:
        p_col = next((c for c in _DEFAULT_PROMPT_COLS if c in cols), cols[0] if cols else "text")

    if output_col and output_col in cols:
        o_col = output_col
    else:
        o_col = next((c for c in _DEFAULT_OUTPUT_COLS if c in cols), p_col)

    return p_col, o_col


def _extract_text(value: object) -> str:
    """Convert a dataset field value to a plain string."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        # WildChat-style: list of dicts with 'role' and 'content'
        parts = []
        for item in value:
            if isinstance(item, dict):
                role = item.get("role", "")
                content = item.get("content", "")
                parts.append(f"[{role}]: {content}")
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(value).strip()


def _load_dataset(dataset_name: str, split: str, num_samples: int, hf_token: str | None):
    """Load a HuggingFace dataset and return an iterable of rows."""
    try:
        from datasets import load_dataset  # type: ignore[import]
    except ImportError:
        log.error("datasets package not installed. Run: pip install datasets>=2.18.0")
        sys.exit(1)

    kwargs: dict = {"streaming": True}
    if hf_token:
        kwargs["token"] = hf_token

    try:
        ds = load_dataset(dataset_name, split=split, trust_remote_code=True, **kwargs)
    except Exception as exc:
        log.error("Failed to load dataset", dataset=dataset_name, error=str(exc))
        sys.exit(1)

    rows = []
    for i, row in enumerate(ds):
        if i >= num_samples:
            break
        rows.append(row)
    return rows


def _insert_samples(
    rows: list[dict],
    tenant_id: uuid.UUID,
    vertical: str,
    source_dataset: str,
    source_model: str,
    prompt_col: str | None,
    output_col: str | None,
    dry_run: bool = False,
) -> int:
    """Insert sampled rows into hf_sample_queue. Returns number inserted."""
    from database import get_db
    from models import HFSampleQueue

    inserted = 0
    db = next(get_db())
    try:
        for row in rows:
            p_col, o_col = _resolve_columns(row, prompt_col, output_col)
            prompt_text = _extract_text(row.get(p_col, ""))
            raw_output_text = _extract_text(row.get(o_col, ""))

            if not prompt_text or not raw_output_text:
                log.warning("Skipping row — empty prompt or output", cols=list(row.keys()))
                continue

            if not dry_run:
                sample = HFSampleQueue(
                    tenant_id=tenant_id,
                    vertical=vertical,
                    source_dataset=source_dataset,
                    prompt_text=prompt_text,
                    raw_output_text=raw_output_text,
                    source_model=source_model,
                    status="pending",
                    sampled_at=datetime.now(timezone.utc),
                )
                db.add(sample)
                inserted += 1

                # Batch-commit every 50 rows to avoid large transactions
                if inserted % 50 == 0:
                    db.commit()
                    log.info("Batch committed", inserted=inserted)
            else:
                inserted += 1

        if not dry_run:
            db.commit()
    except Exception as exc:
        db.rollback()
        log.error("Database insert failed", error=str(exc))
        raise
    finally:
        db.close()

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull HuggingFace dataset samples into the SARO hf_sample_queue."
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="HuggingFace dataset identifier (e.g. allenai/WildChat-1M). "
             "If omitted, defaults to the vertical's configured dataset.",
    )
    parser.add_argument(
        "--vertical",
        required=True,
        choices=list(_VERTICAL_DATASETS.keys()) + ["custom"],
        help="Target vertical for risk analysis context.",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        type=uuid.UUID,
        help="UUID of the tenant that owns the queued samples.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Maximum number of samples to pull (default: 100).",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split to use (default: train).",
    )
    parser.add_argument(
        "--source-model",
        default=None,
        help="Model that produced the outputs (e.g. gpt-4, claude-3). "
             "Defaults to dataset's configured source_model.",
    )
    parser.add_argument(
        "--prompt-col",
        default=None,
        help="Column name for the prompt text. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--output-col",
        default=None,
        help="Column name for the AI output text. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate samples without writing to the database.",
    )
    args = parser.parse_args()

    # Resolve dataset defaults from vertical
    vertical_cfg = _VERTICAL_DATASETS.get(args.vertical, {})
    dataset_name = args.dataset or vertical_cfg.get("dataset")
    if not dataset_name:
        log.error(
            "Dataset name required for custom vertical",
            vertical=args.vertical,
        )
        sys.exit(1)

    source_model = args.source_model or vertical_cfg.get("source_model", "unknown")
    prompt_col = args.prompt_col or vertical_cfg.get("prompt_col")
    output_col = args.output_col or vertical_cfg.get("output_col")
    hf_token = os.environ.get("HF_TOKEN")

    log.info(
        "Starting HF sampler",
        dataset=dataset_name,
        vertical=args.vertical,
        tenant_id=str(args.tenant_id),
        samples=args.samples,
        split=args.split,
        source_model=source_model,
        dry_run=args.dry_run,
    )

    rows = _load_dataset(dataset_name, args.split, args.samples, hf_token)
    log.info("Dataset rows fetched", count=len(rows))

    inserted = _insert_samples(
        rows=rows,
        tenant_id=args.tenant_id,
        vertical=args.vertical,
        source_dataset=dataset_name,
        source_model=source_model,
        prompt_col=prompt_col,
        output_col=output_col,
        dry_run=args.dry_run,
    )

    action = "would insert (dry-run)" if args.dry_run else "inserted"
    log.info(
        "HF sampler complete",
        action=action,
        count=inserted,
        dataset=dataset_name,
        vertical=args.vertical,
    )


if __name__ == "__main__":
    main()
