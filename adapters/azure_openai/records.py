"""Typed records for the Azure OpenAI observation adapter (STORY-359).

Azure OpenAI emits resource logs via Diagnostic Settings (category
``RequestResponse``) to a customer-owned destination — storage account, Log
Analytics, or Event Hub. SARO reads the **customer-owned export** (mirror-async,
INV-6 read-only), never the Azure control plane.

What the standard schema does and does not carry matters for honest coverage
claims, so it is stated here rather than discovered later:

* **Carries:** ``time``, ``operationName``, ``correlationId``, ``location``,
  ``resultSignature`` / ``resultType``, ``durationMs``, and a ``properties``
  bag with ``modelDeploymentName`` / ``modelName`` / ``modelVersion``.
* **Does NOT carry:** prompt or completion content — which is why this source is
  INV-2-safe by nature — and also no tool/function-call data, no stop reason,
  and **no guaranteed token counts** (usage fields appear only on some
  configurations).

Those absences are structural, not data-quality problems. They surface as
``FieldAvailability.UNAVAILABLE`` and as explicit "not supported" rows in the
adapter capability matrix (STORY-362). An adapter that silently returned ``None``
for them would let a buyer infer coverage SARO does not have.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

AZURE_OPENAI_ADAPTER_ID = "azure-openai-diagnostic-log"

# Body-size cap, mirroring the Bedrock adapter's FND-2 defence: exported log
# objects are untrusted input and must not be able to exhaust memory.
MAX_RECORD_CHARS = 1_000_000

# The only diagnostic category this adapter interprets. Others (Audit, Trace,
# categories belonging to other Azure services) are skipped rather than guessed
# at — misreading a category would fabricate observations.
SUPPORTED_CATEGORY = "RequestResponse"


@dataclass(frozen=True)
class AzureAdapterConfig:
    """Per-stream binding supplied by the operator — NOT read from the log.

    ``tenant_id`` decides which SARO tenant an export maps to. This is the
    INV-3 seam: Azure records contain several GUIDs that *look* tenant-shaped
    (the subscription id inside ``resourceId``, ``properties.objectId``, and in
    some schemas an Entra tenant id). None of them may ever set SARO's tenancy —
    a log is attacker-influenced input, and honouring a tenant claim inside it
    would let one customer's export write into another's evidence.

    ``container`` / ``prefix`` scope which exported objects this binding may
    read; the reader refuses anything outside them.
    """

    tenant_id: uuid.UUID
    container: str
    prefix: str = ""
    adapter_id: str = AZURE_OPENAI_ADAPTER_ID


class AzureRecordError(ValueError):
    """A record could not be interpreted as an Azure OpenAI invocation."""


class AzureRecordTooLarge(AzureRecordError):
    """Record exceeds the size cap — refused before parsing (FND-2 class)."""


class AzureCategorySkipped(AzureRecordError):
    """Record belongs to a diagnostic category this adapter does not interpret."""
