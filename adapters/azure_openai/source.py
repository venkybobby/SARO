"""Reader for customer-owned Azure OpenAI log exports (STORY-359).

Mirror-async posture: the customer exports diagnostic logs to storage they own,
and SARO reads them. No Azure SDK dependency and no control-plane calls — the
reader works over an object listing/fetch interface, which a filesystem-backed
implementation satisfies for tests and a blob client satisfies in production.

Tenant isolation (INV-3) is enforced in two independent places, because either
one alone is a single point of failure:

1. **Scope** — a reader is constructed for exactly one tenant's
   ``container`` + ``prefix``, and refuses any key outside it, including
   traversal attempts (``../``) and prefix-confusion attacks where one tenant's
   prefix is a string-prefix of another's (``tenant-1`` vs ``tenant-10``).
2. **Tenancy binding** — parsing takes tenancy from operator config only, so
   even a record that *claims* another tenant lands under the bound tenant
   (see ``adapters/azure_openai/parse.py``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Protocol

from adapters.azure_openai.parse import parse_record
from adapters.azure_openai.records import (
    MAX_RECORD_CHARS,
    AzureAdapterConfig,
    AzureCategorySkipped,
    AzureRecordError,
)
from adapters.contract import NormalizedInvocationRecord

logger = logging.getLogger(__name__)


class ObjectStore(Protocol):
    """Minimal read-only surface an export backend must provide (INV-6)."""

    def list_keys(self, container: str, prefix: str) -> Iterable[str]: ...

    def read_text(self, container: str, key: str) -> str: ...


class OutOfScopeKey(PermissionError):
    """A key outside the tenant's bound container/prefix was requested."""


def _normalize_key(key: str) -> str:
    """Reject traversal outright rather than trying to sanitise it.

    Normalising ``a/../b`` into ``b`` invites disagreement between what this
    code thinks the key is and what the storage backend resolves it to. For a
    read path guarding tenant isolation, refusing the input is the safer
    contract.
    """
    if "\\" in key:
        key = key.replace("\\", "/")
    parts = key.split("/")
    if any(p == ".." for p in parts):
        raise OutOfScopeKey(f"path traversal rejected in key {key!r}")
    return key.lstrip("/")


def _in_scope(key: str, prefix: str) -> bool:
    """Prefix containment on SEGMENT boundaries.

    Plain ``startswith`` would let a reader bound to ``tenant-1/`` read
    ``tenant-10/...`` — a cross-tenant read caused purely by string matching.
    """
    if not prefix:
        return True
    normalized = prefix.rstrip("/")
    return key == normalized or key.startswith(normalized + "/")


class LocalExportStore:
    """Filesystem-backed :class:`ObjectStore` — customer export mounted/downloaded.

    Also what the tests use, so the isolation logic exercised in CI is the same
    code that runs in production, not a stub of it.
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
                if _in_scope(key, prefix):
                    keys.append(key)
        return keys

    def read_text(self, container: str, key: str) -> str:
        return (self.root / container / key).read_text(encoding="utf-8")


class AzureExportReader:
    """Reads one tenant's exported Azure OpenAI logs into normalized records."""

    def __init__(self, config: AzureAdapterConfig, store: ObjectStore) -> None:
        self.config = config
        self.store = store

    # ── Scope enforcement ───────────────────────────────────────────────────

    def _check_scope(self, key: str) -> str:
        normalized = _normalize_key(key)
        if not _in_scope(normalized, self.config.prefix):
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

    def read_object(self, key: str, *, strict: bool = False) -> list[NormalizedInvocationRecord]:
        """Parse one exported object (NDJSON, or a JSON array/``{"records": []}``).

        Unparseable records are skipped with a warning by default: one corrupt
        line in an export must not cost the whole batch's evidence. ``strict``
        raises instead — the conformance suite (STORY-361) uses it to assert
        malformed records really are detected rather than quietly absorbed.
        """
        key = self._check_scope(key)
        text = self.store.read_text(self.config.container, key)
        if len(text) > MAX_RECORD_CHARS * 100:
            raise AzureRecordError(f"export object {key!r} exceeds the size cap")

        records: list[NormalizedInvocationRecord] = []
        for line_no, raw in enumerate(_iter_raw_records(text), start=1):
            cursor = f"{key}:L{line_no}"
            try:
                records.append(
                    parse_record(
                        raw,
                        config=self.config,
                        cursor=cursor,
                        source_uri=f"azure://{self.config.container}/{key}",
                    )
                )
            except AzureCategorySkipped:
                continue  # a different diagnostic category — not an error
            except AzureRecordError as exc:
                if strict:
                    raise
                logger.warning("skipping unparseable Azure record at %s: %s", cursor, exc)
        return records

    def read_all(self, *, strict: bool = False) -> list[NormalizedInvocationRecord]:
        out: list[NormalizedInvocationRecord] = []
        for key in self.list_objects():
            out.extend(self.read_object(key, strict=strict))
        return out


def _iter_raw_records(text: str) -> Iterator[Any]:
    """Yield raw records from NDJSON, a JSON array, or an Azure ``records`` wrapper."""
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


def for_tenant(
    tenant_id: Any,
    container: str,
    *,
    prefix: str = "",
    store: Optional[ObjectStore] = None,
    root: Optional[str | Path] = None,
) -> AzureExportReader:
    """Build a reader scoped to one tenant — the only supported construction path.

    Mirrors ``S3LogStore.for_tenant`` (STORY-408): a reader always carries its
    tenant binding, so there is no way to obtain an unscoped reader by accident.
    """
    if store is None:
        if root is None:
            raise ValueError("provide either a store or a root path")
        store = LocalExportStore(root)
    return AzureExportReader(
        AzureAdapterConfig(tenant_id=tenant_id, container=container, prefix=prefix),
        store,
    )
