"""Reader for customer-owned Vertex AI log exports (STORY-360).

Cloud Logging sink → customer-owned GCS bucket, read by SARO (mirror-async,
INV-6). Scoping and iteration come from ``adapters/export_source.py``; this
module supplies the Vertex binding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from adapters.export_source import (  # noqa: F401 — re-exported for callers/tests
    ExportReader,
    LocalExportStore,
    ObjectStore,
    OutOfScopeKey,
    build_store,
)
from adapters.vertex_ai.parse import parse_record
from adapters.vertex_ai.records import VertexAdapterConfig


class VertexExportReader(ExportReader):
    uri_scheme = "gs"

    def __init__(self, config: VertexAdapterConfig, store: ObjectStore) -> None:
        super().__init__(config, store, parse_record)


def for_tenant(
    tenant_id: Any,
    container: str,
    *,
    prefix: str = "",
    store: Optional[ObjectStore] = None,
    root: Optional[str | Path] = None,
) -> VertexExportReader:
    """Build a reader scoped to one tenant — the only supported construction path."""
    return VertexExportReader(
        VertexAdapterConfig(tenant_id=tenant_id, container=container, prefix=prefix),
        build_store(store, root),
    )
