# SPDX-License-Identifier: Apache-2.0

"""_AsyncContractCapabilityMixin for the AsyncDecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/async_client_facade.py during modularization.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from decision_engine.models_capability_plane import (
        CapabilityAuthorizationCompleteResult,
        CapabilityAuthorizationStartResult,
        CapabilityBindingResult,
        CapabilityBindingTestResult,
        CapabilityCatalogEntryResult,
        CapabilityDiscoverResult,
        CapabilityExecutionResult,
        CapabilityOutcomeRecordResult,
        CapabilityProviderResult,
        CapabilityRoutePlanResult,
    )
    from decision_engine.models_contract import PlatformContractResult
    from decision_engine.models_runtime_manifest import (
        RuntimeAdminBenchmarksResult,
        RuntimeAdminModulesResult,
        RuntimeManifestResult,
        RuntimeReleaseValidationResult,
    )

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import async_client_facade as _facade
    return _facade._capability_plane_surface_module()



class _AsyncContractCapabilityMixin:
    async def get_contract(self) -> PlatformContractResult:
        return await _contract_surface_module().get_contract(self)

    async def get_runtime_manifest(self) -> RuntimeManifestResult:
        return await _contract_surface_module().get_runtime_manifest(self)

    async def get_runtime_modules(self) -> RuntimeAdminModulesResult:
        return await _contract_surface_module().get_runtime_modules(self)

    async def get_runtime_benchmarks(self) -> RuntimeAdminBenchmarksResult:
        return await _contract_surface_module().get_runtime_benchmarks(self)

    async def get_runtime_release_validation(self) -> RuntimeReleaseValidationResult:
        return await _contract_surface_module().get_runtime_release_validation(self)

    async def list_capability_providers(self) -> list[CapabilityProviderResult]:
        return await _capability_plane_surface_module().list_capability_providers(self)

    async def get_capability_provider(self, provider_id: str) -> CapabilityProviderResult:
        return await _capability_plane_surface_module().get_capability_provider(self, provider_id)

    async def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> list[CapabilityBindingResult]:
        return await _capability_plane_surface_module().list_capability_bindings(
            self,
            provider_id=provider_id,
            scope=scope,
        )

    async def create_capability_binding(self, request: dict[str, Any]) -> CapabilityBindingResult:
        return await _capability_plane_surface_module().create_capability_binding(self, request)

    async def get_capability_binding(self, binding_id: str) -> CapabilityBindingResult:
        return await _capability_plane_surface_module().get_capability_binding(self, binding_id)

    async def update_capability_binding(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityBindingResult:
        return await _capability_plane_surface_module().update_capability_binding(
            self,
            binding_id,
            request,
        )

    async def delete_capability_binding(self, binding_id: str) -> None:
        await _capability_plane_surface_module().delete_capability_binding(self, binding_id)

    async def preview_test_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityBindingTestResult:
        return await _capability_plane_surface_module().preview_test_capability_binding(
            self,
            request,
        )

    async def test_capability_binding(self, binding_id: str) -> CapabilityBindingTestResult:
        return await _capability_plane_surface_module().test_capability_binding(self, binding_id)

    async def preview_discover_capability_binding(
        self,
        request: dict[str, Any],
    ) -> CapabilityDiscoverResult:
        return await _capability_plane_surface_module().preview_discover_capability_binding(
            self,
            request,
        )

    async def discover_capability_binding(self, binding_id: str) -> CapabilityDiscoverResult:
        return await _capability_plane_surface_module().discover_capability_binding(
            self,
            binding_id,
        )

    async def start_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationStartResult:
        return await _capability_plane_surface_module().start_capability_authorization(
            self,
            binding_id,
            request,
        )

    async def complete_capability_authorization(
        self,
        binding_id: str,
        request: dict[str, Any],
    ) -> CapabilityAuthorizationCompleteResult:
        return await _capability_plane_surface_module().complete_capability_authorization(
            self,
            binding_id,
            request,
        )

    async def list_capabilities(
        self,
        *,
        kinds: list[str] | tuple[str, ...] | None = None,
        provider_ids: list[str] | tuple[str, ...] | None = None,
        binding_ids: list[str] | tuple[str, ...] | None = None,
    ) -> list[CapabilityCatalogEntryResult]:
        return await _capability_plane_surface_module().list_capabilities(
            self,
            kinds=kinds,
            provider_ids=provider_ids,
            binding_ids=binding_ids,
        )

    async def get_capability(
        self,
        capability_id: str,
        *,
        include_instruction: bool = False,
    ) -> CapabilityCatalogEntryResult:
        return await _capability_plane_surface_module().get_capability(
            self,
            capability_id,
            include_instruction=include_instruction,
        )

    async def route_capabilities(self, request: dict[str, Any]) -> CapabilityRoutePlanResult:
        return await _capability_plane_surface_module().route_capabilities(self, request)

    async def execute_capability(self, request: dict[str, Any]) -> CapabilityExecutionResult:
        return await _capability_plane_surface_module().execute_capability(self, request)

    async def record_capability_outcome(
        self,
        request: dict[str, Any],
    ) -> CapabilityOutcomeRecordResult:
        return await _capability_plane_surface_module().record_capability_outcome(self, request)

    async def list_skills(self) -> list[CapabilityCatalogEntryResult]:
        return await _capability_plane_surface_module().list_skills(self)

    async def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> CapabilityDiscoverResult:
        return await _capability_plane_surface_module().enable_skill(
            self,
            skill_name=skill_name,
            instruction=instruction,
            description=description,
            tags=tags,
            artifact_affinities=artifact_affinities,
            execution_owner=execution_owner,
        )

    async def disable_skill(self, binding_id: str) -> None:
        await _capability_plane_surface_module().disable_skill(self, binding_id)

    async def list_mcp_providers(self) -> list[CapabilityProviderResult]:
        return await _capability_plane_surface_module().list_mcp_providers(self)

