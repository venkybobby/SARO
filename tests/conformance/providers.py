"""Per-adapter conformance providers (STORY-361).

Each provider builds the shared scenarios using its adapter's REAL parser — not
a hand-made `NormalizedInvocationRecord`. That distinction is the whole point:
constructing the record directly would test the contract, which we already know
holds, while proving nothing about the adapter's parsing. Every record here
comes out of `parse_record` / `parse_envelope`.

Where a provider's logs cannot express a scenario, the provider says so with a
reason. Those declarations are the honest source for the capability matrix
(STORY-362).
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.azure_openai.parse import parse_record as azure_parse  # noqa: E402
from adapters.azure_openai.records import (  # noqa: E402
    AzureAdapterConfig,
    AzureRecordError,
)
from adapters.bedrock.parse import parse_envelope  # noqa: E402
from adapters.bedrock.records import BEDROCK_ADAPTER_ID  # noqa: E402
from adapters.contract import ToolInvocation, from_bedrock_envelope  # noqa: E402
from adapters.vertex_ai.parse import parse_record as vertex_parse  # noqa: E402
from adapters.vertex_ai.records import (  # noqa: E402
    VertexAdapterConfig,
    VertexRecordError,
)
from conformance.harness import Outcome, Scenario  # noqa: E402

BOUND_TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
ALLOWED_TOOLS = ("search_kb",)
OUT_OF_SCOPE_TOOL = "delete_everything"


def _tagged(outcome: Outcome) -> Outcome:
    """Attach the expected tenant for the tenancy-spoofing assertion."""
    object.__setattr__(outcome, "_expected_tenant", BOUND_TENANT)
    return outcome


# ── Bedrock (adapter #1) ────────────────────────────────────────────────────


class BedrockUnderTest:
    adapter_id = BEDROCK_ADAPTER_ID
    display_name = "Bedrock"

    @staticmethod
    def _raw(**over):
        base = {
            "requestId": "req-1",
            "region": "us-east-1",
            "operation": "Converse",
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
            "timestamp": "2026-07-01T09:00:00Z",
            "input": {"inputTokenCount": 100},
            "output": {"outputTokenCount": 20},
        }
        base.update(over)
        return base

    def _record(self, raw, *, tools=(), truncated=False, stop_reason=None):
        envelope = parse_envelope(raw, cursor="s3:key:L1")
        return from_bedrock_envelope(
            envelope,
            tenant_id=BOUND_TENANT,
            adapter_id=self.adapter_id,
            tools=tools,
            truncated=truncated,
            stop_reason=stop_reason,
        )

    def standard_schema_record(self):
        """A record from the provider's STOCK log shape — no enrichment.

        Drives the buyer-facing capability matrix (STORY-362): field support is
        read from what this record's availability map actually says, so the
        matrix reflects adapter behaviour rather than a prose claim about it.
        Bedrock invocation logs carry token counts, tool metadata, and a stop
        reason natively, so the stock shape is the full one.
        """
        return self._record(
            self._raw(),
            tools=(ToolInvocation(name="search_kb", offered=True, invoked=True),),
            truncated=False,
            stop_reason="end_turn",
        )

    def build(self, scenario: Scenario) -> Outcome:
        if scenario is Scenario.HAPPY_PATH:
            return Outcome.supported(self._record(self._raw()))

        if scenario is Scenario.MISSING_FIELDS:
            raw = self._raw(input={}, output={})
            raw["region"] = ""
            return Outcome.supported(self._record(raw))

        if scenario is Scenario.MALFORMED_RECORD:
            try:
                # timestamp is required by the envelope parser
                self._record(self._raw(timestamp="not-a-timestamp"))
            except Exception as exc:  # noqa: BLE001 — any refusal is the point
                return Outcome.supported(raised=exc)
            return Outcome.supported(record=None)

        if scenario is Scenario.TOOL_SCOPE_VIOLATION:
            rec = self._record(
                self._raw(),
                tools=(ToolInvocation(name=OUT_OF_SCOPE_TOOL, offered=True, invoked=True),),
            )
            return Outcome.supported(rec, allowed_tools=ALLOWED_TOOLS)

        if scenario is Scenario.INCOMPLETE_OBSERVATION:
            return Outcome.supported(
                self._record(self._raw(), truncated=True, stop_reason="max_tokens")
            )

        if scenario is Scenario.TENANCY_SPOOFING:
            # Bedrock logs carry an AWS account id in ARNs; none may set tenancy.
            raw = self._raw(accountId=str(OTHER_TENANT), tenantId=str(OTHER_TENANT))
            return _tagged(Outcome.supported(self._record(raw)))

        raise NotImplementedError(scenario)


# ── Azure OpenAI (adapter #2) ───────────────────────────────────────────────


class AzureUnderTest:
    adapter_id = "azure-openai-diagnostic-log"
    display_name = "Azure OpenAI"

    def __init__(self) -> None:
        self.config = AzureAdapterConfig(tenant_id=BOUND_TENANT, container="logs", prefix="")

    @staticmethod
    def _raw(**over):
        base = {
            "time": "2026-07-01T09:00:00.1234567Z",
            "category": "RequestResponse",
            "operationName": "ChatCompletions_Create",
            "correlationId": "corr-1",
            "location": "eastus",
            "resultSignature": "200",
            "resultType": "Success",
            "properties": {
                "modelName": "gpt-4o",
                "modelVersion": "2024-05-13",
                "promptTokens": 100,
                "completionTokens": 20,
            },
        }
        props = over.pop("properties", None)
        base.update(over)
        if props is not None:
            base["properties"] = props
        return base

    def _parse(self, raw):
        return azure_parse(raw, config=self.config, cursor="obj:L1")

    def standard_schema_record(self):
        """Azure's STOCK RequestResponse entry: no usage fields, no tool data.

        The happy-path fixture above includes token counts because some Azure
        configurations report them — but a buyer must not be told that is
        guaranteed, so the capability matrix reads from this stricter shape.
        """
        return self._parse(
            self._raw(properties={"modelName": "gpt-4o", "modelVersion": "2024-05-13"})
        )

    @staticmethod
    def field_caveats() -> dict[str, str]:
        """Fields supported in principle but dependent on customer configuration."""
        return {
            "Token counts": (
                "Some Azure OpenAI configurations emit promptTokens/completionTokens "
                "and SARO will use them when present, but they are not part of the "
                "guaranteed RequestResponse schema — so volume-based evidence cannot "
                "be assumed for an Azure deployment without checking the export."
            ),
        }

    def build(self, scenario: Scenario) -> Outcome:
        if scenario is Scenario.HAPPY_PATH:
            return Outcome.supported(self._parse(self._raw()))

        if scenario is Scenario.MISSING_FIELDS:
            raw = self._raw(properties={})
            raw.pop("location")
            return Outcome.supported(self._parse(raw))

        if scenario is Scenario.MALFORMED_RECORD:
            raw = self._raw()
            raw.pop("correlationId")
            try:
                self._parse(raw)
            except AzureRecordError as exc:
                return Outcome.supported(raised=exc)
            return Outcome.supported(record=None)

        if scenario is Scenario.TOOL_SCOPE_VIOLATION:
            raw = self._raw()
            raw["properties"]["tools"] = [{"name": OUT_OF_SCOPE_TOOL}]
            raw["properties"]["toolCalls"] = [{"name": OUT_OF_SCOPE_TOOL}]
            return Outcome.conditional(
                self._parse(raw),
                reason=(
                    "Requires an ENRICHED export: Azure's standard RequestResponse "
                    "schema carries no tool/function data, so tool-scope evaluation "
                    "works only if the customer's export adds properties.tools / "
                    ".toolCalls (e.g. a gateway log in the same envelope). On "
                    "stock Azure diagnostic logs this scenario is unobservable."
                ),
                allowed_tools=ALLOWED_TOOLS,
            )

        if scenario is Scenario.INCOMPLETE_OBSERVATION:
            return Outcome.not_supported(
                "Azure OpenAI RequestResponse diagnostic logs do not report a stop "
                "reason, so a truncated generation is indistinguishable from a "
                "complete one. Truncation cannot be observed from this source."
            )

        if scenario is Scenario.TENANCY_SPOOFING:
            raw = self._raw()
            raw["tenantId"] = str(OTHER_TENANT)
            raw["properties"]["objectId"] = str(OTHER_TENANT)
            return _tagged(Outcome.supported(self._parse(raw)))

        raise NotImplementedError(scenario)


# ── Vertex AI (adapter #3) ──────────────────────────────────────────────────


class VertexUnderTest:
    adapter_id = "vertex-ai-audit-log"
    display_name = "Vertex AI"

    def __init__(self) -> None:
        self.config = VertexAdapterConfig(tenant_id=BOUND_TENANT, container="gcs", prefix="")

    @staticmethod
    def _raw(**over):
        base = {
            "insertId": "entry-1",
            "timestamp": "2026-07-01T09:00:00.123456789Z",
            "resource": {
                "type": "aiplatform.googleapis.com/PublisherModel",
                "labels": {"project_id": "p", "location": "us-central1"},
            },
            "protoPayload": {
                "serviceName": "aiplatform.googleapis.com",
                "methodName": "google.cloud.aiplatform.v1.PredictionService.GenerateContent",
                "resourceName": "projects/p/locations/us-central1/publishers/google/models/gemini-1.5-pro",
                "status": {},
            },
        }
        payload = over.pop("protoPayload", None)
        resource = over.pop("resource", None)
        base.update(over)
        if payload is not None:
            base["protoPayload"] = payload
        if resource is not None:
            base["resource"] = resource
        return base

    def _parse(self, raw):
        return vertex_parse(raw, config=self.config, cursor="obj:L1")

    def standard_schema_record(self):
        """Vertex's STOCK Cloud Audit entry: no usage, no stop reason, no tools."""
        return self._parse(self._raw())

    @staticmethod
    def field_caveats() -> dict[str, str]:
        return {
            "Model identity": (
                "Resolvable for publisher models (…/publishers/google/models/X). For "
                "models served behind a customer ENDPOINT the audit log names only "
                "the endpoint id, and which model sits behind it is not in the log — "
                "SARO reports model identity as missing rather than substituting the "
                "endpoint id, which would make a model-allowlist rule meaningless."
            ),
        }

    def build(self, scenario: Scenario) -> Outcome:
        if scenario is Scenario.HAPPY_PATH:
            return Outcome.supported(self._parse(self._raw()))

        if scenario is Scenario.MISSING_FIELDS:
            raw = self._raw()
            raw["resource"]["labels"].pop("location")
            raw["protoPayload"]["resourceName"] = "projects/p/locations/l/endpoints/9"
            return Outcome.supported(self._parse(raw))

        if scenario is Scenario.MALFORMED_RECORD:
            raw = self._raw()
            raw.pop("insertId")
            try:
                self._parse(raw)
            except VertexRecordError as exc:
                return Outcome.supported(raised=exc)
            return Outcome.supported(record=None)

        if scenario is Scenario.TOOL_SCOPE_VIOLATION:
            raw = self._raw()
            raw["labels"] = {
                "tools": [{"name": OUT_OF_SCOPE_TOOL}],
                "toolCalls": [{"name": OUT_OF_SCOPE_TOOL}],
            }
            return Outcome.conditional(
                self._parse(raw),
                reason=(
                    "Requires an ENRICHED export: Vertex Cloud Audit Logs carry no "
                    "tool/function data, so tool-scope evaluation works only if the "
                    "customer's sink adds tool metadata in LogEntry.labels. Note "
                    "SARO will NOT read protoPayload.request/.response to recover "
                    "it — those may contain prompt/completion content (INV-2)."
                ),
                allowed_tools=ALLOWED_TOOLS,
            )

        if scenario is Scenario.INCOMPLETE_OBSERVATION:
            return Outcome.not_supported(
                "Vertex Cloud Audit Logs record that an invocation occurred, not "
                "how generation terminated. No stop reason or token accounting is "
                "emitted, so truncation is not observable from this source."
            )

        if scenario is Scenario.TENANCY_SPOOFING:
            raw = self._raw()
            raw["resource"]["labels"]["project_id"] = str(OTHER_TENANT)
            raw["protoPayload"]["authenticationInfo"] = {
                "principalEmail": f"{OTHER_TENANT}@evil.test"
            }
            return _tagged(Outcome.supported(self._parse(raw)))

        raise NotImplementedError(scenario)


REGISTERED_ADAPTERS = [BedrockUnderTest(), AzureUnderTest(), VertexUnderTest()]

# Kept for the "adapter #4" procedure: the list an adapter must join to be
# claimed as supported anywhere in SARO's documentation.
__all__ = ["REGISTERED_ADAPTERS", "BedrockUnderTest", "AzureUnderTest", "VertexUnderTest"]

# Silence unused-import warnings for symbols used only in type context.
_ = (json, datetime, timezone)
