"""S3-key-layout source reader for the Bedrock backfill adapter (STORY-406 / -407).

``replay_backfill`` consumes an iterable of ``(cursor, raw_record)`` pairs — it is
deliberately agnostic to *where* the log records come from. This module is the
discovery half: it walks Amazon Bedrock's model-invocation-log S3 key layout,
gunzips each NDJSON object, and yields ``(cursor, raw)`` in monotonic stream order,
so the same discovery logic runs unmodified against a real S3 bucket OR a local
directory that mirrors the key layout (STORY-407 AC-2.1).

Read-only and guard-clean: this reaches AWS **S3 object storage** only (lazy boto3
``s3`` client), never a model-inference endpoint. It lives in the ``adapters``
package the STORY-336 guard scans, and imports only stdlib + (lazily) boto3 ``s3``.

The cursor is ``"s3:{key}:L{line}"`` — the Envelope.cursor convention from
records.py — which is monotonic because object keys sort by their hour path and the
line index increases within an object. It becomes the coverage watermark, so a
backfill is resumable and idempotent per cursor.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Protocol

logger = logging.getLogger(__name__)

# Bedrock's fixed S3 key layout for delivered invocation logs. The segment name is
# "BedrockModelInvocationLogs" — a passive log-delivery path, NOT the forbidden
# model-inference service endpoint the STORY-336 guard denylists.
_LOG_SEGMENT = "BedrockModelInvocationLogs"

# .../{yyyy}/{mm}/{dd}/{hh}/ — the hour-partition the objects are batched under.
_KEY_HOUR_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/(\d{2})/")

# The exact, closed shape of a Bedrock invocation-log object key. Every key handed to
# read_bytes() (local disk OR S3) is validated against this before use (FND — security
# review): a key that does not match cannot contain ".." or an absolute-path escape, so
# it cannot walk LocalLogStore's read outside `root` regardless of where it came from
# (a compromised listing, a hand-edited/malicious cursor, a future caller resuming from
# a persisted watermark_position). S3 has no real directory traversal, but the same check
# is applied there too as defense-in-depth against key-shape assumptions elsewhere.
_KEY_SHAPE_RE = re.compile(
    r"^AWSLogs/\d{12}/"
    + re.escape(_LOG_SEGMENT)
    + r"/[a-z0-9-]+/\d{4}/\d{2}/\d{2}/\d{2}/[^/]+\.json\.gz$"
)

# Defensive caps: a single gzip object is read/decompressed one hour-batch at a time.
# Bedrock caps S3 log objects well under MAX_OBJECT_BYTES; MAX_DECOMPRESSED_BYTES bounds
# the OUTPUT of decompression separately, since gzip's compression ratio means a small
# compressed object can expand to an enormous one (decompression-bomb; FND — security
# review). Both caps are enforced by streaming/incremental reads, never by reading the
# full (pre- or post-decompression) payload into memory first and checking after.
MAX_OBJECT_BYTES = 50_000_000
MAX_DECOMPRESSED_BYTES = 200_000_000
_READ_CHUNK = 1_048_576  # 1 MiB


def _validate_key_shape(key: str) -> None:
    if not _KEY_SHAPE_RE.match(key):
        raise ValueError(
            f"log object key does not match the Bedrock invocation-log layout: {key!r}"
        )


def _bounded_gunzip(raw: bytes) -> bytes:
    """Decompress ``raw`` gzip bytes, aborting once the OUTPUT exceeds
    MAX_DECOMPRESSED_BYTES (FND — security review: decompression-bomb guard).

    ``gzip.decompress()`` has no output-size limit — a small compressed object can
    expand to gigabytes. This reads the decompressed stream incrementally and raises
    before an oversized payload is ever fully materialized in memory.
    """
    out = io.BytesIO()
    total = 0
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as gz:
        while True:
            chunk = gz.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DECOMPRESSED_BYTES:
                raise ValueError(
                    f"decompressed log object exceeds {MAX_DECOMPRESSED_BYTES}-byte cap"
                )
            out.write(chunk)
    return out.getvalue()


def bedrock_log_prefix(account_id: str, region: str) -> str:
    """The S3 key prefix under which Bedrock delivers this account/region's logs."""
    return f"AWSLogs/{account_id}/{_LOG_SEGMENT}/{region}/"


def parse_key_hour(key: str) -> Optional[datetime]:
    """Extract the hour-partition (UTC) from an object key, or None if absent."""
    m = _KEY_HOUR_RE.search(key)
    if not m:
        return None
    y, mo, d, h = (int(g) for g in m.groups())
    try:
        return datetime(y, mo, d, h, tzinfo=timezone.utc)
    except ValueError:
        return None


class LogObjectStore(Protocol):
    """Minimal read-only object store: list keys under a prefix, read one object."""

    def iter_object_keys(self, prefix: str) -> Iterable[str]: ...
    def read_bytes(self, key: str) -> bytes: ...


class LocalLogStore:
    """Filesystem store over a directory that mirrors the S3 key layout.

    ``root`` is the ``--out`` directory the builder wrote into (it contains the
    ``AWSLogs/...`` tree). Keys are POSIX paths relative to ``root`` so they are
    byte-identical to the S3 object keys — the adapter cannot tell the difference.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def iter_object_keys(self, prefix: str) -> Iterator[str]:
        base = self.root / prefix
        if not base.exists():
            return
        for path in sorted(base.rglob("*.json.gz")):
            yield path.relative_to(self.root).as_posix()

    def read_bytes(self, key: str) -> bytes:
        # FND (security review): validate key SHAPE before any path join — closes path
        # traversal (a ".." segment cannot match _KEY_SHAPE_RE) regardless of what
        # produced the key (a hostile listing, a hand-edited cursor, a future caller
        # resuming from a persisted watermark_position).
        _validate_key_shape(key)
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"log object key escapes the store root: {key!r}")
        # Stream-read with an early abort so an oversized file is never fully loaded
        # into memory before the cap is checked (matches S3LogStore's read discipline).
        chunks: list[bytes] = []
        total = 0
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(_READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_OBJECT_BYTES:
                    raise ValueError(
                        f"log object {key!r} exceeds {MAX_OBJECT_BYTES}-byte cap"
                    )
                chunks.append(chunk)
        return b"".join(chunks)


class S3LogStore:
    """Read-only S3 store (lazy boto3 ``s3`` client). Never reaches a model-inference endpoint."""

    def __init__(
        self, bucket: str, *, prefix_root: str = "", client: Any = None
    ) -> None:
        self.bucket = bucket
        self.prefix_root = prefix_root.strip("/")
        self._client = client

    def _s3(self) -> Any:
        if self._client is None:
            import boto3  # lazy: optional dependency, S3 object storage only

            self._client = boto3.client("s3")
        return self._client

    def _full(self, key: str) -> str:
        return f"{self.prefix_root}/{key}" if self.prefix_root else key

    def iter_object_keys(self, prefix: str) -> Iterator[str]:
        client = self._s3()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._full(prefix)):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                if key.endswith(".json.gz"):
                    # Return keys relative to prefix_root so cursors match the local layout.
                    yield key[len(self.prefix_root) + 1 :] if self.prefix_root else key

    def read_bytes(self, key: str) -> bytes:
        # FND (security review): defense-in-depth key-shape check, matching LocalLogStore
        # (S3 has no real directory traversal, but a malformed key should never reach a
        # GetObject call either).
        _validate_key_shape(key)
        client = self._s3()
        obj = client.get_object(Bucket=self.bucket, Key=self._full(key))
        data = obj["Body"].read(MAX_OBJECT_BYTES + 1)
        if len(data) > MAX_OBJECT_BYTES:
            raise ValueError(f"log object {key!r} exceeds {MAX_OBJECT_BYTES}-byte cap")
        return data


def discover_object_keys(
    store: LogObjectStore,
    *,
    account_id: str,
    region: str,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> list[str]:
    """Return the object keys for this account/region whose hour-partition falls in
    ``[window_start, window_end)``, sorted into monotonic stream order (by hour, then
    key). A key with no parseable hour partition is skipped with a warning."""
    prefix = bedrock_log_prefix(account_id, region)
    dated: list[tuple[datetime, str]] = []
    for key in store.iter_object_keys(prefix):
        hour = parse_key_hour(key)
        if hour is None:
            logger.warning(
                "bedrock source: skipping key without hour partition: %s", key
            )
            continue
        if window_start is not None and hour < window_start:
            continue
        if window_end is not None and hour >= window_end:
            continue
        dated.append((hour, key))
    dated.sort()
    return [k for _, k in dated]


def iter_backfill_records(
    store: LogObjectStore, keys: Iterable[str]
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(cursor, raw_record)`` for every NDJSON line in ``keys``, in order.

    Each object is gunzipped and split into records; a malformed (non-JSON) line is
    skipped with a warning rather than aborting the corpus (matching the adapter's
    fail-soft contract). The cursor ``"s3:{key}:L{line}"`` is monotonic across the
    sorted keys, so it is a valid resumable stream watermark.
    """
    for key in keys:
        raw = store.read_bytes(key)
        try:
            text = _bounded_gunzip(raw).decode("utf-8")
        except (OSError, EOFError, UnicodeDecodeError, ValueError):
            logger.warning("bedrock source: cannot gunzip/decode object %s", key)
            continue
        for lineno, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "bedrock source: skipping non-JSON line %s:L%d", key, lineno
                )
                continue
            yield f"s3:{key}:L{lineno}", record


def read_backfill_corpus(
    store: LogObjectStore,
    *,
    account_id: str,
    region: str,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Convenience: discover + iterate in one call, ready to hand to replay_backfill."""
    keys = discover_object_keys(
        store,
        account_id=account_id,
        region=region,
        window_start=window_start,
        window_end=window_end,
    )
    yield from iter_backfill_records(store, keys)
