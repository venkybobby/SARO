"""Shared reader for customer-owned log exports (STORY-359/360).

Every observation adapter ingests the same way: a customer exports provider logs
to storage they own, and SARO reads them (mirror-async, INV-6 read-only). Only
the per-record parsing differs. This module owns everything that does not —
above all the tenant-isolation logic, which must have exactly one implementation
so a fix lands once instead of once per adapter.

Tenant isolation (INV-3) has two independent controls, since either alone is a
single point of failure:

1. **Scope** — a reader is bound to one tenant's ``container`` + ``prefix`` and
   refuses any key outside it, including traversal (``../``) and prefix
   confusion (``tenant-1`` must not read ``tenant-10``).
2. **Tenancy binding** — each adapter's parser takes tenancy from operator
   config, never from log content. Provider logs are full of tenant-shaped
   identifiers (Azure subscription GUIDs, GCP project ids) that must not
   influence which SARO tenant an observation belongs to.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional, Protocol

from adapters.contract import NormalizedInvocationRecord

logger = logging.getLogger(__name__)


class ObjectStore(Protocol):
    """Minimal read-only surface an export backend must provide (INV-6).

    Deliberately read-only: there is no write method to call by accident, which
    is a stronger guarantee than a policy saying not to write.
    """

    def list_keys(self, container: str, prefix: str) -> Iterable[str]: ...

    def read_text(self, container: str, key: str) -> str: ...


class OutOfScopeKey(PermissionError):
    """A key outside the tenant's bound container/prefix was requested."""


class ExportRecordError(ValueError):
    """A record could not be interpreted. Adapters subclass this."""


class RecordSkipped(ExportRecordError):
    """Record is valid but not of interest (e.g. a different log category)."""


def normalize_key(key: str) -> str:
    """Reject traversal outright rather than trying to sanitise it.

    Normalising ``a/../b`` into ``b`` invites disagreement between what this code
    believes the key is and what the storage backend resolves it to. On a read
    path guarding tenant isolation, refusing the input is the safer contract.
    """
    if "\\" in key:
        key = key.replace("\\", "/")
    if any(part == ".." for part in key.split("/")):
        raise OutOfScopeKey(f"path traversal rejected in key {key!r}")
    return key.lstrip("/")


def in_scope(key: str, prefix: str) -> bool:
    """Prefix containment on SEGMENT boundaries.

    Plain ``startswith`` would let a reader bound to ``tenant-1/`` read
    ``tenant-10/...`` — a cross-tenant read caused purely by string matching.
    """
    if not prefix:
        return True
    normalized = prefix.rstrip("/")
    return key == normalized or key.startswith(normalized + "/")


class LocalExportStore:
    """Filesystem-backed store — a downloaded/mounted customer export.

    Also what the tests use, so the isolation logic exercised in CI is the same
    code that runs in production rather than a stub of it.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def list_keys(self, container: str, prefix: str) -> list[str]:
        base = self.root / container
        if not base.is_dir():
            return []
        keys = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                key = path.relative_to(base).as_posix()
                if in_scope(key, prefix):
                    keys.append(key)
        return keys

    def read_text(self, container: str, key: str) -> str:
        return (self.root / container / key).read_text(encoding="utf-8")


def iter_raw_records(text: str) -> Iterator[Any]:
    """Yield raw records from NDJSON, a JSON array, or a ``{"records": [...]}`` wrapper.

    All three appear in the wild: Azure blob exports use the wrapper, GCS log
    sinks write NDJSON, and hand-assembled exports are often arrays.
    """
    stripped = text.strip()
    if not stripped:
        return
    if stripped.startswith("["):
        try:
            for item in json.loads(stripped):
                yield item
            return
        except json.JSONDecodeError:
            pass
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
            for item in parsed["records"]:
                yield item
            return
        if isinstance(parsed, dict):
            yield parsed
            return
    for line in stripped.splitlines():
        line = line.strip()
        if line:
            yield line


# Parser signature every adapter provides.
RecordParser = Callable[..., NormalizedInvocationRecord]


class ExportReader:
    """Tenant-scoped reader over a customer-owned export.

    Subclasses supply ``parse`` and the ``uri_scheme`` used for provenance
    pointers; everything about scoping and iteration lives here.
    """

    uri_scheme = "export"

    def __init__(self, config: Any, store: ObjectStore, parser: RecordParser) -> None:
        self.config = config
        self.store = store
        self._parser = parser

    # ── Scope enforcement ───────────────────────────────────────────────────

    def _check_scope(self, key: str) -> str:
        normalized = normalize_key(key)
        if not in_scope(normalized, self.config.prefix):
            raise OutOfScopeKey(
                f"key {key!r} is outside tenant prefix {self.config.prefix!r}"
            )
        return normalized

    def list_objects(self) -> list[str]:
        return [
            self._check_scope(k)
            for k in self.store.list_keys(self.config.container, self.config.prefix)
        ]

    # ── Reading ─────────────────────────────────────────────────────────────

    def read_object(
        self, key: str, *, strict: bool = False
    ) -> list[NormalizedInvocationRecord]:
        """Parse one exported object.

        Unparseable records are skipped with a warning by default: one corrupt
        line must not cost the whole batch's evidence. ``strict`` raises instead
        — the conformance suite (STORY-361) uses it to assert malformed records
        are genuinely detected rather than quietly absorbed.
        """
        key = self._check_scope(key)
        text = self.store.read_text(self.config.container, key)

        records: list[NormalizedInvocationRecord] = []
        for line_no, raw in enumerate(iter_raw_records(text), start=1):
            cursor = f"{key}:L{line_no}"
            try:
                records.append(
                    self._parser(
                        raw,
                        config=self.config,
                        cursor=cursor,
                        source_uri=f"{self.uri_scheme}://{self.config.container}/{key}",
                    )
                )
            except RecordSkipped:
                continue  # valid record, not of interest — not an error
            except ExportRecordError as exc:
                if strict:
                    raise
                logger.warning("skipping unparseable record at %s: %s", cursor, exc)
        return records

    def read_all(self, *, strict: bool = False) -> list[NormalizedInvocationRecord]:
        out: list[NormalizedInvocationRecord] = []
        for key in self.list_objects():
            out.extend(self.read_object(key, strict=strict))
        return out


def build_store(
    store: Optional[ObjectStore], root: Optional[str | Path]
) -> ObjectStore:
    if store is not None:
        return store
    if root is None:
        raise ValueError("provide either a store or a root path")
    return LocalExportStore(root)
