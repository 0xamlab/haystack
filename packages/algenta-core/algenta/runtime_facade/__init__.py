"""runtime_facade — Runtime class facade.

The Runtime class is split into 10 mixin classes in submodules of this
package; each mixin file is well under 1000 lines. This __init__.py
keeps the original imports + 6 @cache module-getter functions + the
Runtime class core (__init__, __repr__, __getattr__, _connector_surface,
_perf_counter), and composes the full Runtime class via mixin inheritance.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator, Mapping
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from algenta.privacy_profile import resolve_cloud_base_url
from algenta.runtime_errors import RuntimeConfigurationError

if TYPE_CHECKING:
    from types import ModuleType

    from algenta.runtime_model_account import (
        APIKeyCreatedOutput,
        APIKeyInfoOutput,
        UsageOutput,
    )
    from algenta.runtime_model_agent_runs import (
        AgentRunCheckpointListResponseOutput,
        AgentRunCheckpointsOutput,
        AgentRunEventsOutput,
        AgentRunListOutput,
        AgentRunMissionEventListResponseOutput,
        AgentRunMissionEventsOutput,
        AgentRunOutput,
        AgentRunReplayOutput,
        AgentRunStreamEventOutput,
        AgentRunTelemetryListOutput,
        AgentRunTelemetryOutput,
    )
    from algenta.runtime_model_contract import PlatformContractOutput
    from algenta.runtime_model_capability_plane import (
        CapabilityAuthorizationCompleteOutput,
        CapabilityAuthorizationStartOutput,
        CapabilityBindingOutput,
        CapabilityBindingTestOutput,
        CapabilityCatalogEntryOutput,
        CapabilityDiscoverOutput,
        CapabilityExecutionOutput,
        CapabilityOutcomeRecordOutput,
        CapabilityProviderOutput,
        CapabilityRoutePlanOutput,
    )
    from algenta.runtime_model_control_plane import (
        AuditLogOutput,
        BillingInfoOutput,
        BillingSessionOutput,
        CreditRefreshOutput,
        DeviceListOutput,
        DeviceRevokeOutput,
        DistributionListOutput,
        ExecutionPolicyOutput,
        ExecutionPolicySnapshotListOutput,
        MeteringBatchOutput,
        TeamListOutput,
        TemplateListOutput,
    )
    from algenta.runtime_model_decision_envelope import DecisionEnvelopeOutput
    from algenta.runtime_model_decision_memory import (
        DecisionListOutput,
        DecisionLogOutput,
        ExecutionReceiptOutput,
    )
    from algenta.runtime_model_decision_plan import DecisionPlanOutput
    from algenta.runtime_model_deployments import (
        DeploymentCostOutput,
        DeploymentDeleteOutput,
        DeploymentOutput,
        DeploymentRegionsOutput,
    )
    from algenta.runtime_model_import_preview import (
        ImportBundlePreview,
        ImportPreview,
    )
    from algenta.runtime_model_jobs import (
        JobListOutput,
        JobStatusOutput,
        JobSubmitOutput,
        WebhookTestOutput,
    )
    from algenta.runtime_model_llm import (
        ArtifactBridgeResolveOutput,
        ChatCompletionsOutput,
        ChatCompletionsStreamChunkOutput,
        CountTokensOutput,
        EmbeddingSimilarityOutput,
        EmbeddingsOutput,
        LLMModelListOutput,
        RerankResponseOutput,
        ResponsesOutput,
        ResponseStreamEventOutput,
        TokenizeOutput,
    )
    from algenta.runtime_model_manifest import (
        RuntimeAdminBenchmarksOutput,
        RuntimeAdminModulesOutput,
        RuntimeManifestOutput,
        RuntimeReleaseValidationOutput,
    )
    from algenta.runtime_model_products import (
        ProductAgentRunOutput,
        ProductDecisionOutput,
        ProductForecastOutput,
        ProductOptimizeOutput,
        ProductRetrieveOutput,
    )
    from algenta.runtime_model_query_metadata import (
        QueryBatchOutput,
        QuerySqlReportOutput,
        QueryWithMetadataOutput,
    )
    from algenta.runtime_model_query_output import QueryOutput
    from algenta.runtime_model_repository_intelligence import (
        RepositoryApplyOutput,
        RepositoryGraphQueryOutput,
        RepositoryDecisionPlanRevisionOutput,
        RepositorySnapshotOutput,
        RepositoryTriageOutput,
    )
    from algenta.runtime_model_resolve_output import ResolveOutput
    from algenta.runtime_model_resolved_plan import ResolvedPlan
    from algenta.runtime_model_source_registration import SourceRegistration
    from algenta.runtime_model_triggers import (
        TriggerDeleteOutput,
        TriggerFireOutput,
        TriggerListOutput,
        TriggerPauseOutput,
        TriggerSummaryOutput,
    )
    from algenta.runtime_model_verify_output import VerifyOutput

LocalSourceInput = str | Path | list[dict[str, Any]] | Mapping[str, Any]


@cache
def _runtime_execution_surface_module() -> ModuleType:
    return import_module("algenta.runtime_execution_surface")


@cache
def _runtime_registration_surface_module() -> ModuleType:
    return import_module("algenta.runtime_registration_surface")


@cache
def _runtime_model_source_registration_module() -> ModuleType:
    return import_module("algenta.runtime_model_source_registration")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_connectors_module() -> ModuleType:
    return import_module("algenta.runtime_connectors")


@cache
def _runtime_capability_plane_module() -> ModuleType:
    return import_module("algenta.runtime_capability_plane")


@cache
def _runtime_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_repository_intelligence")


from algenta.runtime_facade._connectors_datasets import _ConnectorsDatasetsMixin  # noqa: E402
from algenta.runtime_facade._repository_imports import _RepositoryImportsMixin  # noqa: E402
from algenta.runtime_facade._execution_query import _ExecutionQueryMixin  # noqa: E402
from algenta.runtime_facade._jobs_triggers import _JobsTriggersMixin  # noqa: E402
from algenta.runtime_facade._account_billing_admin import _AccountBillingAdminMixin  # noqa: E402
from algenta.runtime_facade._decisions_products import _DecisionsProductsMixin  # noqa: E402
from algenta.runtime_facade._llm import _LLMMixin  # noqa: E402
from algenta.runtime_facade._agent_runs import _AgentRunsMixin  # noqa: E402
from algenta.runtime_facade._capability_plane import _CapabilityPlaneMixin  # noqa: E402
from algenta.runtime_facade._internal_helpers import _InternalHelpersMixin  # noqa: E402


class Runtime(_ConnectorsDatasetsMixin, _RepositoryImportsMixin, _ExecutionQueryMixin, _JobsTriggersMixin, _AccountBillingAdminMixin, _DecisionsProductsMixin, _LLMMixin, _AgentRunsMixin, _CapabilityPlaneMixin, _InternalHelpersMixin):
    """
    Runtime-first Algenta facade.

    Local mode executes against connected in-memory or file-backed sources.
    API mode delegates to the lower-level `decision_engine.AlgentaClient`.
    """

    def __init__(
        self,
        *,
        mode: str = "local",
        api_key: str | None = None,
        base_url: str | None = None,
        enforce_limits: bool | None = None,
        repository_intelligence_backend: Any | str | None = None,
    ) -> None:
        if mode not in {"local", "api", "self_hosted"}:
            raise ValueError("Invalid mode. Expected 'local', 'api', or 'self_hosted'.")
        api_key_from_env = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        explicit_api_key = api_key is not None
        self._mode = mode
        self._api_key = api_key or api_key_from_env
        if mode == "self_hosted":
            if not isinstance(base_url, str) or not base_url.strip():
                raise RuntimeConfigurationError(
                    "self_hosted_base_url_required",
                    "Runtime(mode='self_hosted') requires an explicit base_url.",
                )
            self._base_url = resolve_cloud_base_url(
                explicit_base_url=base_url,
                component="Runtime(mode='self_hosted')",
            )
        elif mode == "api":
            self._base_url = resolve_cloud_base_url(
                explicit_base_url=base_url,
                component="Runtime(mode='api')",
            )
        else:
            self._base_url = (
                base_url.strip()
                if isinstance(base_url, str) and base_url.strip()
                else ""
            )
        self._local_sources: dict[str, Any] = {}
        self._api_registrations_by_name: dict[str, SourceRegistration] = {}
        self._api_registrations_by_dataset: dict[str, SourceRegistration] = {}
        self._api_source_schema_revision_cache: dict[str, str] = {}
        self._api_client: Any | None = None
        self._connector_surface_helper: Any | None = None
        self._local_license: Any | None = None
        self._api_surface_cache: dict[str, tuple[float, Any]] = {}
        self._inline_preview_events: list[float] = []
        self._inline_preview_pending_cleanup: dict[str, float] = {}
        self._inline_preview_cache: dict[str, tuple[float, Any]] = {}
        self._inline_preview_capabilities: dict[str, tuple[float, bool]] = {}
        self._capability_adapters: dict[str, dict[str, Any]] = {}
        self._local_capability_bindings: dict[str, dict[str, Any]] = {}
        self._local_capability_catalog: dict[str, dict[str, Any]] = {}
        self._local_capability_auth_sessions: dict[str, dict[str, Any]] = {}
        self._local_capability_outcomes: list[dict[str, Any]] = []
        self._local_capability_executions: dict[str, dict[str, Any]] = {}
        self._local_repository_intelligence_backend: Any | None = None
        self._local_repository_intelligence_backend_spec: str | None = None
        if isinstance(repository_intelligence_backend, str):
            self._local_repository_intelligence_backend_spec = (
                repository_intelligence_backend.strip() or None
            )
        elif repository_intelligence_backend is not None:
            _runtime_repository_intelligence_module().register_repository_intelligence_backend(
                self,
                repository_intelligence_backend,
            )
        if enforce_limits is None:
            self._enforce_limits = mode == "local" and explicit_api_key
        else:
            self._enforce_limits = enforce_limits

    def __repr__(self) -> str:
        key_state = "set" if self._api_key else "not set"
        return f"Runtime(mode={self._mode!r}, api_key={key_state})"

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return getattr(self._connector_surface(), name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def _connector_surface(self) -> Any:
        helper = self._connector_surface_helper
        if helper is None:
            helper = _runtime_connectors_module().RuntimeConnectorSurface(self)
            self._connector_surface_helper = helper
        return helper

    @staticmethod
    def _perf_counter() -> float:
        return time.perf_counter()
