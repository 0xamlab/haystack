"""_CapabilitiesSkillsMixin for the CodnaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _CapabilitiesSkillsMixin:
    def get_contract(self) -> Any:
        return self._sdk_client().get_contract()

    def list_capability_providers(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().list_capability_providers())

    def get_capability_provider(self, provider_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().get_capability_provider(provider_id))

    def list_capability_bindings(
        self,
        *,
        provider_id: str | None = None,
        scope: str | None = None,
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().list_capability_bindings(
                provider_id=provider_id,
                scope=scope,
            )
        )

    def create_capability_binding(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().create_capability_binding(request))

    def get_capability_binding(self, binding_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().get_capability_binding(binding_id))

    def update_capability_binding(self, binding_id: str, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().update_capability_binding(binding_id, request)
        )

    def delete_capability_binding(self, binding_id: str) -> None:
        self._sdk_client().delete_capability_binding(binding_id)

    def preview_test_capability_binding(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().preview_test_capability_binding(request)
        )

    def test_capability_binding(self, binding_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().test_capability_binding(binding_id))

    def preview_discover_capability_binding(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().preview_discover_capability_binding(request)
        )

    def discover_capability_binding(self, binding_id: str) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().discover_capability_binding(binding_id))

    def start_capability_authorization(self, binding_id: str, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().start_capability_authorization(binding_id, request)
        )

    def complete_capability_authorization(self, binding_id: str, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().complete_capability_authorization(binding_id, request)
        )

    def list_capabilities(
        self,
        *,
        kinds: list[str] | tuple[str, ...] | None = None,
        provider_ids: list[str] | tuple[str, ...] | None = None,
        binding_ids: list[str] | tuple[str, ...] | None = None,
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().list_capabilities(
                kinds=kinds,
                provider_ids=provider_ids,
                binding_ids=binding_ids,
            )
        )

    def get_capability(self, capability_id: str, *, include_instruction: bool = False) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().get_capability(
                capability_id,
                include_instruction=include_instruction,
            )
        )

    def route_capabilities(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().route_capabilities(request))

    def execute_capability(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().execute_capability(request))

    def record_capability_outcome(self, request: dict[str, Any]) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().record_capability_outcome(request))

    def list_skills(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().list_skills())

    def enable_skill(
        self,
        *,
        skill_name: str,
        instruction: str,
        description: str | None = None,
        tags: list[str] | None = None,
        artifact_affinities: list[str] | None = None,
        execution_owner: str = "client_managed",
    ) -> Any:
        return _sdk_payload_to_plain_data(
            self._sdk_client().enable_skill(
                skill_name=skill_name,
                instruction=instruction,
                description=description,
                tags=tags,
                artifact_affinities=artifact_affinities,
                execution_owner=execution_owner,
            )
        )

    def disable_skill(self, binding_id: str) -> None:
        self._sdk_client().disable_skill(binding_id)

    def list_mcp_providers(self) -> Any:
        return _sdk_payload_to_plain_data(self._sdk_client().list_mcp_providers())

    def get_runtime_manifest(self) -> Any:
        return self._sdk_client().get_runtime_manifest()

    def get_runtime_modules(self) -> Any:
        return self._sdk_client().get_runtime_modules()

    def get_runtime_benchmarks(self) -> Any:
        return self._sdk_client().get_runtime_benchmarks()

    def get_runtime_release_validation(self) -> Any:
        return self._sdk_client().get_runtime_release_validation()

