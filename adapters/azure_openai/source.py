"""Reader for customer-owned Azure OpenAI log exports (STORY-359).

Scoping, traversal rejection, and record iteration live in
``adapters/export_source.py`` — shared by every adapter so the INV-3 controls
have one implementation. This module is the Azure-specific binding: the URI
scheme used for provenance pointers, and the parser to apply.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from adapters.azure_openai.parse import parse_record
from adapters.azure_openai.records import AzureAdapterConfig
from adapters.export_source import (  # noqa: F401 — re-exported for callers/tests
    ExportReader,
    LocalExportStore,
    ObjectStore,
    OutOfScopeKey,
    build_store,
)


class AzureExportReader(ExportReader):
    uri_scheme = "azure"

    def __init__(self, config: AzureAdapterConfig, store: ObjectStore) -> None:
        super().__init__(config, store, parse_record)


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
    tenant binding, so an unscoped reader cannot be obtained by accident.
    """
    return AzureExportReader(
        AzureAdapterConfig(tenant_id=tenant_id, container=container, prefix=prefix),
        build_store(store, root),
    )
