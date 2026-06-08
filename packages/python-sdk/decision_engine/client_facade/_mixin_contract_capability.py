"""_ContractCapabilityMixin for the DecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/client_facade.py during modularization.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._capability_plane_surface_module()



class _ContractCapabilityMixin:
    def get_contract(self) -> PlatformContractResult:
        return _contract_surface_module().get_contract(self)

    def get_runtime_manifest(self) -> RuntimeManifestResult:
        return _contract_surface_module().get_runtime_manifest(self)

    def get_runtime_modules(self) -> RuntimeAdminModulesResult:
        return _contract_surface_module().get_runtime_modules(self)

    def get_runtime_benchmarks(self) -> RuntimeAdminBenchmarksResult:
        return _contract_surface_module().get_runtime_benchmarks(self)

    def get_runtime_release_validation(self) -> RuntimeReleaseValidationResult:
        return _contract_surface_module().get_runtime_release_validation(self)

    def list_capability_providers(self) -> list[CapabilityProviderResult]:
        return _capability_plane_surface_module().list_capability_providers(self)

    def get_capability_provider(self, provider_id: str) -> CapabilityProviderResult:
        return _capability_plane_surface_module().get_capability_provider(self, provider_id)

    def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> list[CapabilityBindingResult]:
        return _capability_plane_surface_module().list_capability_bindings(
            self,
            provider_id=provider_id,
            scope=scope,
        )

    def create_capability_binding(self, request: dict[str, Any]) -> CapabilityBindingResult:
        return _capability_plane_surface_module().create_capability_binding(self, request)

    def get_capability_binding(self, binding_id: str) -> CapabilityBindingResult:
        return _capability_plane_surface_module().get_capability_binding(self, binding_id)

    def update_capability_binding(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityBindingResult:
        return _capability_plane_surface_module().update_capability_binding(
            self,
            binding_id,
            request,
        )

    def delete_capability_binding(self, binding_id: str) -> None:
        _capability_plane_surface_module().delete_capability_binding(self, binding_id)

    def preview_test_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityBindingTestResult:
        return _capability_plane_surface_module().preview_test_capability_binding(self, request)

    def test_capability_binding(self, binding_id: str) -> CapabilityBindingTestResult:
        return _capability_plane_surface_module().test_capability_binding(self, binding_id)

    def preview_discover_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityDiscoverResult:
        return _capability_plane_surface_module().preview_discover_capability_binding(
            self,
            request,
        )

    def discover_capability_binding(self, binding_id: str) -> CapabilityDiscoverResult:
        return _capability_plane_surface_module().discover_capability_binding(self, binding_id)

    def start_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationStartResult:
        return _capability_plane_surface_module().start_capability_authorization(
            self,
            binding_id,
            request,
        )

    def complete_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationCompleteResult:
        return _capability_plane_surface_module().complete_capability_authorization(
            self,
            binding_id,
            request,
        )

    def list_capabilities(
        self,
        *,
        kinds: list[str] | tuple[str, ...] | None = None,
        provider_ids: list[str] | tuple[str, ...] | None = None,
        binding_ids: list[str] | tuple[str, ...] | None = None,
    ) -> list[CapabilityCatalogEntryResult]:
        return _capability_plane_surface_module().list_capabilities(
            self,
            kinds=kinds,
            provider_ids=provider_ids,
            binding_ids=binding_ids,
        )

    def get_capability(
        self,
        capability_id: str,
        *,
        include_instruction: bool = False,
    ) -> CapabilityCatalogEntryResult:
        return _capability_plane_surface_module().get_capability(
            self,
            capability_id,
            include_instruction=include_instruction,
        )

    def route_capabilities(self, request: dict[str, Any]) -> CapabilityRoutePlanResult:
        return _capability_plane_surface_module().route_capabilities(self, request)

    def execute_capability(self, request: dict[str, Any]) -> CapabilityExecutionResult:
        return _capability_plane_surface_module().execute_capability(self, request)

    def record_capability_outcome(
        self,
        request: dict[str, Any],
    ) -> CapabilityOutcomeRecordResult:
        return _capability_plane_surface_module().record_capability_outcome(self, request)

    def list_skills(self) -> list[CapabilityCatalogEntryResult]:
        return _capability_plane_surface_module().list_skills(self)

    def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> CapabilityDiscoverResult:
        return _capability_plane_surface_module().enable_skill(
            self,
            skill_name=skill_name,
            instruction=instruction,
            description=description,
            tags=tags,
            artifact_affinities=artifact_affinities,
            execution_owner=execution_owner,
        )

    def disable_skill(self, binding_id: str) -> None:
        _capability_plane_surface_module().disable_skill(self, binding_id)

    def list_mcp_providers(self) -> list[CapabilityProviderResult]:
        return _capability_plane_surface_module().list_mcp_providers(self)

