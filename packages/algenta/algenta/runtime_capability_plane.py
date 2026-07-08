from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import re
from typing import Any
from uuid import uuid4

from algenta.runtime_errors import RuntimeValidationError
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
    CapabilityProviderProfileOutput,
    CapabilityRouteFallbackOutput,
    CapabilityRoutePlanOutput,
)


def _now_text() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _seed_providers() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "provider.data_connector.algenta",
            "provider_type": "data_connector",
            "name": "Algenta Governed Data",
            "description": "Governed data connectors surfaced through the capability plane.",
            "supported_execution_owners": ["algenta_managed"],
            "policy_summary": {"route_authority": "capability_plane"},
            "active": True,
            "profiles": [
                {
                    "profile_id": "profile.data_connector.workspace",
                    "provider_id": "provider.data_connector.algenta",
                    "name": "Workspace Data",
                    "description": "Workspace-scoped governed data bindings.",
                    "auth_kind": "managed",
                    "default_execution_owner": "algenta_managed",
                    "binding_scope_default": "workspace",
                    "supported_binding_scopes": ["workspace", "organization"],
                }
            ],
        },
        {
            "provider_id": "provider.mcp.generic",
            "provider_type": "mcp_provider",
            "name": "Generic MCP Provider",
            "description": "Customer-managed MCP capabilities exposed through the capability plane.",
            "supported_execution_owners": ["algenta_managed", "client_managed"],
            "policy_summary": {"route_authority": "capability_plane"},
            "active": True,
            "profiles": [
                {
                    "profile_id": "profile.mcp.workspace",
                    "provider_id": "provider.mcp.generic",
                    "name": "Workspace MCP",
                    "description": "Workspace-scoped MCP bindings.",
                    "auth_kind": "oauth2",
                    "default_execution_owner": "client_managed",
                    "binding_scope_default": "workspace",
                    "supported_binding_scopes": ["workspace", "organization"],
                }
            ],
        },
        {
            "provider_id": "provider.skill_pack.algenta",
            "provider_type": "skill_pack",
            "name": "Algenta Skill Pack",
            "description": "Instruction and hybrid skills exposed through the capability plane.",
            "supported_execution_owners": ["algenta_managed", "client_managed"],
            "policy_summary": {"route_authority": "capability_plane"},
            "active": True,
            "profiles": [
                {
                    "profile_id": "profile.skill_pack.user",
                    "provider_id": "provider.skill_pack.algenta",
                    "name": "User Skills",
                    "description": "User-scoped skill bindings.",
                    "auth_kind": "none",
                    "default_execution_owner": "client_managed",
                    "binding_scope_default": "user",
                    "supported_binding_scopes": ["user", "workspace"],
                }
            ],
        },
        {
            "provider_id": "provider.native_tool_pack.customer",
            "provider_type": "native_tool_pack",
            "name": "Customer Native Tools",
            "description": "Customer-managed native tool definitions exposed through the capability plane.",
            "supported_execution_owners": ["client_managed"],
            "policy_summary": {"route_authority": "capability_plane"},
            "active": True,
            "profiles": [
                {
                    "profile_id": "profile.native_tool_pack.workspace",
                    "provider_id": "provider.native_tool_pack.customer",
                    "name": "Workspace Native Tools",
                    "description": "Workspace-scoped native tool bindings.",
                    "auth_kind": "none",
                    "default_execution_owner": "client_managed",
                    "binding_scope_default": "workspace",
                    "supported_binding_scopes": ["workspace", "organization"],
                }
            ],
        },
        {
            "provider_id": "provider.runtime_library_pack.algenta",
            "provider_type": "runtime_library_pack",
            "name": "Algenta Runtime Libraries",
            "description": "Runtime libraries exposed through the capability plane.",
            "supported_execution_owners": ["algenta_managed", "client_managed"],
            "policy_summary": {"route_authority": "capability_plane"},
            "active": True,
            "profiles": [
                {
                    "profile_id": "profile.runtime_library_pack.workspace",
                    "provider_id": "provider.runtime_library_pack.algenta",
                    "name": "Workspace Runtime Libraries",
                    "description": "Workspace-scoped runtime library bindings.",
                    "auth_kind": "managed",
                    "default_execution_owner": "algenta_managed",
                    "binding_scope_default": "workspace",
                    "supported_binding_scopes": ["workspace", "organization"],
                }
            ],
        },
    ]


def _profile_defaults(runtime: Any, provider_id: str, profile_id: str) -> dict[str, Any]:
    for provider in _seed_providers():
        if provider["provider_id"] != provider_id:
            continue
        for profile in provider["profiles"]:
            if profile["profile_id"] == profile_id:
                return profile
    raise RuntimeValidationError(
        "unknown_capability_profile",
        "Capability provider profile is not registered in the local runtime.",
        {"provider_id": provider_id, "profile_id": profile_id},
    )


def _coerce_mapping(value: Any, name: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    raise RuntimeValidationError(
        "invalid_capability_request",
        f"{name} must be a mapping.",
        {"field": name},
    )


def _hash_manifest(capabilities: list[dict[str, Any]]) -> str:
    return sha256(repr(capabilities).encode("utf-8")).hexdigest()


def _normalize_capability_entry(
    raw_capability: Mapping[str, Any],
    *,
    provider_id: str,
    profile_id: str,
    binding_id: str,
    binding_status: str,
) -> dict[str, Any]:
    capability = dict(raw_capability)
    capability_id = str(capability.get("capability_id") or "").strip()
    if not capability_id:
        raise RuntimeValidationError(
            "invalid_capability_manifest",
            "Capability manifest entry is missing capability_id.",
            {"entry": capability},
        )
    name = str(capability.get("name") or capability_id).strip()
    if not name:
        raise RuntimeValidationError(
            "invalid_capability_manifest",
            "Capability manifest entry is missing name.",
            {"capability_id": capability_id},
        )
    manifest_hash = _hash_manifest([capability])
    return {
        "capability_id": capability_id,
        "provider_id": provider_id,
        "profile_id": profile_id,
        "binding_id": binding_id,
        "kind": str(capability.get("kind") or "skill"),
        "name": name,
        "description": capability.get("description"),
        "implementation_kind": str(capability.get("implementation_kind") or "instruction_only"),
        "execution_owner": str(capability.get("execution_owner") or "client_managed"),
        "input_schema_ref": str(capability.get("input_schema_ref") or "capability.input.none"),
        "output_schema_ref": str(
            capability.get("output_schema_ref") or "capability.output.generic"
        ),
        "side_effect_class": str(capability.get("side_effect_class") or "read_only"),
        "risk_level": str(capability.get("risk_level") or "low"),
        "required_policy": str(
            capability.get("required_policy") or "capability_plane.default"
        ),
        "replayability": str(capability.get("replayability") or "deterministic"),
        "approval_required": bool(capability.get("approval_required", False)),
        "trust_tier": str(capability.get("trust_tier") or "workspace"),
        "manifest_hash": manifest_hash,
        "artifact_affinities": list(capability.get("artifact_affinities") or []),
        "tags": list(capability.get("tags") or []),
        "required_binding_ids": list(capability.get("required_binding_ids") or [binding_id]),
        "selected_tool_name": capability.get("selected_tool_name"),
        "instruction_artifact_ref": capability.get("instruction_artifact_ref"),
        "binding_status": binding_status,
        "discovered_at": _now_text(),
        "customer_metadata": capability.get("customer_metadata"),
        "instruction_text": capability.get("instruction"),
    }


def _normalize_adapter(runtime: Any, adapter: Any) -> dict[str, Any]:
    descriptor = getattr(adapter, "descriptor", None)
    if descriptor is None and isinstance(adapter, Mapping):
        descriptor = adapter.get("descriptor")
    if not isinstance(descriptor, Mapping):
        raise RuntimeValidationError(
            "invalid_capability_adapter",
            "Capability adapter must expose a descriptor mapping.",
        )
    descriptor_data = dict(descriptor)
    capability_id = str(descriptor_data.get("capability_id") or "").strip()
    provider_id = str(descriptor_data.get("provider_id") or "").strip()
    name = str(descriptor_data.get("name") or "").strip()
    kind = str(descriptor_data.get("kind") or "").strip()
    if not capability_id or not provider_id or not name or not kind:
        raise RuntimeValidationError(
            "invalid_capability_adapter",
            "Capability adapter descriptor must include capability_id, provider_id, name, and kind.",
            {"descriptor": descriptor_data},
        )
    profile_id = str(
        descriptor_data.get("profile_id")
        or {
            "provider.mcp.generic": "profile.mcp.workspace",
            "provider.native_tool_pack.customer": "profile.native_tool_pack.workspace",
            "provider.skill_pack.algenta": "profile.skill_pack.user",
        }.get(provider_id, "profile.native_tool_pack.workspace")
    )
    binding_id = str(descriptor_data.get("binding_id") or f"binding.local.{capability_id}")
    binding_name = str(descriptor_data.get("binding_name") or name)
    entry = _normalize_capability_entry(
        descriptor_data,
        provider_id=provider_id,
        profile_id=profile_id,
        binding_id=binding_id,
        binding_status="ready",
    )
    binding = {
        "binding_id": binding_id,
        "provider_id": provider_id,
        "profile_id": profile_id,
        "binding_name": binding_name,
        "scope": str(descriptor_data.get("scope") or "workspace"),
        "scope_ref": str(descriptor_data.get("scope_ref") or "local"),
        "status": "ready",
        "execution_owner": str(entry["execution_owner"]),
        "config": {"adapter_registered": True},
        "customer_metadata": descriptor_data.get("customer_metadata"),
        "system_managed": False,
        "last_tested_at": None,
        "last_discovered_at": entry["discovered_at"],
        "authorized_at": None,
        "quarantine_reason": None,
        "discovery_error_message": None,
        "test_error_message": None,
        "created_at": _now_text(),
        "updated_at": _now_text(),
    }
    execute_fn = getattr(adapter, "execute", None)
    if execute_fn is None and isinstance(adapter, Mapping):
        execute_fn = adapter.get("execute")
    test_fn = getattr(adapter, "test", None)
    if test_fn is None and isinstance(adapter, Mapping):
        test_fn = adapter.get("test")
    runtime._capability_adapters[capability_id] = {
        "descriptor": descriptor_data,
        "execute": execute_fn,
        "test": test_fn,
    }
    runtime._local_capability_bindings[binding_id] = binding
    runtime._local_capability_catalog[capability_id] = entry
    return entry


def register_capability_adapter(runtime: Any, adapter: Any) -> None:
    _normalize_adapter(runtime, adapter)


def _local_provider_outputs() -> list[CapabilityProviderOutput]:
    return [CapabilityProviderOutput.from_api(item) for item in _seed_providers()]


def list_capability_providers(runtime: Any) -> list[CapabilityProviderOutput]:
    if runtime._uses_api_transport():
        return [
            CapabilityProviderOutput.from_api(item)
            for item in runtime._client().list_capability_providers()
        ]
    return _local_provider_outputs()


def get_capability_provider(runtime: Any, provider_id: str) -> CapabilityProviderOutput:
    for provider in list_capability_providers(runtime):
        if provider.provider_id == provider_id:
            return provider
    raise RuntimeValidationError(
        "capability_provider_not_found",
        "Capability provider was not found.",
        {"provider_id": provider_id},
    )


def list_capability_bindings(
    runtime: Any,
    *,
    provider_id: str | None = None,
    scope: str | None = None,
) -> list[CapabilityBindingOutput]:
    if runtime._uses_api_transport():
        return [
            CapabilityBindingOutput.from_api(item)
            for item in runtime._client().list_capability_bindings(
                provider_id=provider_id,
                scope=scope,
            )
        ]
    bindings = []
    for binding in runtime._local_capability_bindings.values():
        if provider_id and binding["provider_id"] != provider_id:
            continue
        if scope and binding["scope"] != scope:
            continue
        bindings.append(CapabilityBindingOutput.from_api(binding))
    return bindings


def create_capability_binding(runtime: Any, request: Mapping[str, Any]) -> CapabilityBindingOutput:
    if runtime._uses_api_transport():
        return CapabilityBindingOutput.from_api(runtime._client().create_capability_binding(dict(request)))
    request_data = _coerce_mapping(request, "request")
    provider_id = str(request_data.get("provider_id") or "").strip()
    profile_id = str(request_data.get("profile_id") or "").strip()
    binding_name = str(request_data.get("binding_name") or "").strip()
    if not provider_id or not profile_id or not binding_name:
        raise RuntimeValidationError(
            "invalid_capability_binding_request",
            "provider_id, profile_id, and binding_name are required.",
        )
    defaults = _profile_defaults(runtime, provider_id, profile_id)
    now = _now_text()
    binding = {
        "binding_id": str(uuid4()),
        "provider_id": provider_id,
        "profile_id": profile_id,
        "binding_name": binding_name,
        "scope": str(request_data.get("scope") or defaults["binding_scope_default"]),
        "scope_ref": str(request_data.get("scope_ref") or "local"),
        "status": str(request_data.get("status") or "ready"),
        "execution_owner": str(
            request_data.get("execution_owner") or defaults["default_execution_owner"]
        ),
        "config": dict(request_data.get("config") or {}),
        "customer_metadata": request_data.get("customer_metadata"),
        "system_managed": False,
        "last_tested_at": None,
        "last_discovered_at": None,
        "authorized_at": None,
        "quarantine_reason": None,
        "discovery_error_message": None,
        "test_error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    runtime._local_capability_bindings[binding["binding_id"]] = binding
    return CapabilityBindingOutput.from_api(binding)


def get_capability_binding(runtime: Any, binding_id: str) -> CapabilityBindingOutput:
    if runtime._uses_api_transport():
        return CapabilityBindingOutput.from_api(runtime._client().get_capability_binding(binding_id))
    binding = runtime._local_capability_bindings.get(binding_id)
    if binding is None:
        raise RuntimeValidationError(
            "capability_binding_not_found",
            "Capability binding was not found.",
            {"binding_id": binding_id},
        )
    return CapabilityBindingOutput.from_api(binding)


def update_capability_binding(
    runtime: Any,
    binding_id: str,
    request: Mapping[str, Any],
) -> CapabilityBindingOutput:
    if runtime._uses_api_transport():
        return CapabilityBindingOutput.from_api(
            runtime._client().update_capability_binding(binding_id, dict(request))
        )
    binding = get_capability_binding(runtime, binding_id).to_dict()
    for field in (
        "binding_name",
        "scope",
        "scope_ref",
        "status",
        "execution_owner",
        "config",
        "customer_metadata",
    ):
        if field in request and request[field] is not None:
            binding[field] = request[field]
    binding["updated_at"] = _now_text()
    runtime._local_capability_bindings[binding_id] = binding
    return CapabilityBindingOutput.from_api(binding)


def delete_capability_binding(runtime: Any, binding_id: str) -> None:
    if runtime._uses_api_transport():
        runtime._client().delete_capability_binding(binding_id)
        return
    runtime._local_capability_bindings.pop(binding_id, None)
    for capability_id, entry in list(runtime._local_capability_catalog.items()):
        if entry["binding_id"] == binding_id:
            runtime._local_capability_catalog.pop(capability_id, None)


def preview_test_capability_binding(
    runtime: Any,
    request: Mapping[str, Any],
) -> CapabilityBindingTestOutput:
    if runtime._uses_api_transport():
        return CapabilityBindingTestOutput.from_api(
            runtime._client().preview_test_capability_binding(dict(request))
        )
    request_data = _coerce_mapping(request, "request")
    provider_id = str(request_data.get("provider_id") or "").strip()
    get_capability_provider(runtime, provider_id)
    return CapabilityBindingTestOutput.from_api(
        {
            "success": True,
            "binding_status": "ready",
            "message": "Local capability binding preview succeeded.",
            "latency_ms": 0,
            "details": {"mode": "preview"},
        }
    )


def test_capability_binding(runtime: Any, binding_id: str) -> CapabilityBindingTestOutput:
    if runtime._uses_api_transport():
        return CapabilityBindingTestOutput.from_api(
            runtime._client().test_capability_binding(binding_id)
        )
    binding = get_capability_binding(runtime, binding_id).to_dict()
    binding["last_tested_at"] = _now_text()
    runtime._local_capability_bindings[binding_id] = binding
    adapter = next(
        (
            item
            for item in runtime._capability_adapters.values()
            if str(item["descriptor"].get("binding_id") or f"binding.local.{item['descriptor']['capability_id']}") == binding_id
        ),
        None,
    )
    details = {"mode": "saved"}
    if adapter and callable(adapter.get("test")):
        test_result = adapter["test"]()
        if isinstance(test_result, Mapping):
            details["adapter"] = dict(test_result)
    return CapabilityBindingTestOutput.from_api(
        {
            "success": True,
            "binding_status": binding["status"],
            "message": "Local capability binding test succeeded.",
            "latency_ms": 0,
            "details": details,
        }
    )


def _discover_local_from_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
    config = dict(binding.get("config") or {})
    manifest = dict(config.get("manifest") or {})
    raw_capabilities = manifest.get("capabilities") or []
    if not isinstance(raw_capabilities, list):
        raise RuntimeValidationError(
            "invalid_capability_manifest",
            "Capability manifest capabilities must be a list.",
        )
    capabilities = [
        _normalize_capability_entry(
            item,
            provider_id=str(binding["provider_id"]),
            profile_id=str(binding["profile_id"]),
            binding_id=str(binding["binding_id"]),
            binding_status=str(binding["status"]),
        )
        for item in raw_capabilities
        if isinstance(item, Mapping)
    ]
    if not capabilities:
        for capability_id, entry in list(binding.get("adapter_capabilities", {}).items()):
            capabilities.append(dict(entry))
    manifest_hash = _hash_manifest(capabilities)
    discovered_at = _now_text()
    return {
        "binding_id": binding["binding_id"],
        "provider_id": binding["provider_id"],
        "profile_id": binding["profile_id"],
        "snapshot_id": f"snapshot.{binding['binding_id']}",
        "binding_status": binding["status"],
        "manifest_hash": manifest_hash,
        "capability_count": len(capabilities),
        "discovered_at": discovered_at,
        "message": f"Discovered {len(capabilities)} capability{'ies' if len(capabilities) != 1 else ''}.",
        "capabilities": capabilities,
    }


def preview_discover_capability_binding(
    runtime: Any,
    request: Mapping[str, Any],
) -> CapabilityDiscoverOutput:
    if runtime._uses_api_transport():
        return CapabilityDiscoverOutput.from_api(
            runtime._client().preview_discover_capability_binding(dict(request))
        )
    preview_binding = create_capability_binding(
        runtime,
        {
            **dict(request),
            "binding_name": str(dict(request).get("binding_name") or "Preview Binding"),
        },
    ).to_dict()
    result = _discover_local_from_binding(preview_binding)
    runtime._local_capability_bindings.pop(preview_binding["binding_id"], None)
    return CapabilityDiscoverOutput.from_api(result)


def discover_capability_binding(runtime: Any, binding_id: str) -> CapabilityDiscoverOutput:
    if runtime._uses_api_transport():
        return CapabilityDiscoverOutput.from_api(
            runtime._client().discover_capability_binding(binding_id)
        )
    binding = get_capability_binding(runtime, binding_id).to_dict()
    result = _discover_local_from_binding(binding)
    binding["last_discovered_at"] = result["discovered_at"]
    binding["updated_at"] = result["discovered_at"]
    runtime._local_capability_bindings[binding_id] = binding
    for capability in result["capabilities"]:
        runtime._local_capability_catalog[capability["capability_id"]] = capability
    return CapabilityDiscoverOutput.from_api(result)


def start_capability_authorization(
    runtime: Any,
    binding_id: str,
    request: Mapping[str, Any],
) -> CapabilityAuthorizationStartOutput:
    if runtime._uses_api_transport():
        return CapabilityAuthorizationStartOutput.from_api(
            runtime._client().start_capability_authorization(binding_id, dict(request))
        )
    binding = get_capability_binding(runtime, binding_id)
    session_id = str(uuid4())
    expires_at = (datetime.now(UTC) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    session = {
        "session_id": session_id,
        "binding_id": binding.binding_id,
        "provider_id": binding.provider_id,
        "authorize_url": f"https://local.algenta.invalid/capability-auth/{binding.binding_id}",
        "expires_at": expires_at,
        "requested_scopes": list(dict(request).get("requested_scopes") or []),
    }
    runtime._local_capability_auth_sessions[session_id] = session
    return CapabilityAuthorizationStartOutput.from_api(session)


def complete_capability_authorization(
    runtime: Any,
    binding_id: str,
    request: Mapping[str, Any],
) -> CapabilityAuthorizationCompleteOutput:
    if runtime._uses_api_transport():
        return CapabilityAuthorizationCompleteOutput.from_api(
            runtime._client().complete_capability_authorization(binding_id, dict(request))
        )
    request_data = _coerce_mapping(request, "request")
    session_id = str(request_data.get("session_id") or "").strip()
    if not session_id or session_id not in runtime._local_capability_auth_sessions:
        raise RuntimeValidationError(
            "capability_authorization_session_not_found",
            "Capability authorization session was not found.",
            {"session_id": session_id},
        )
    binding = get_capability_binding(runtime, binding_id).to_dict()
    binding["status"] = "ready"
    binding["authorized_at"] = _now_text()
    binding["updated_at"] = binding["authorized_at"]
    runtime._local_capability_bindings[binding_id] = binding
    return CapabilityAuthorizationCompleteOutput.from_api(
        {
            "session_id": session_id,
            "binding_id": binding_id,
            "provider_id": binding["provider_id"],
            "status": "completed",
            "authorized_at": binding["authorized_at"],
        }
    )


def list_capabilities(
    runtime: Any,
    *,
    kinds: list[str] | tuple[str, ...] | None = None,
    provider_ids: list[str] | tuple[str, ...] | None = None,
    binding_ids: list[str] | tuple[str, ...] | None = None,
) -> list[CapabilityCatalogEntryOutput]:
    if runtime._uses_api_transport():
        return [
            CapabilityCatalogEntryOutput.from_api(item)
            for item in runtime._client().list_capabilities(
                kinds=kinds,
                provider_ids=provider_ids,
                binding_ids=binding_ids,
            )
        ]
    entries = []
    for entry in runtime._local_capability_catalog.values():
        if kinds and entry["kind"] not in kinds:
            continue
        if provider_ids and entry["provider_id"] not in provider_ids:
            continue
        if binding_ids and entry["binding_id"] not in binding_ids:
            continue
        entries.append(CapabilityCatalogEntryOutput.from_api(entry))
    return entries


def get_capability(
    runtime: Any,
    capability_id: str,
    *,
    include_instruction: bool = False,
) -> CapabilityCatalogEntryOutput:
    if runtime._uses_api_transport():
        return CapabilityCatalogEntryOutput.from_api(
            runtime._client().get_capability(
                capability_id,
                include_instruction=include_instruction,
            )
        )
    entry = runtime._local_capability_catalog.get(capability_id)
    if entry is None:
        raise RuntimeValidationError(
            "capability_not_found",
            "Capability was not found in the local runtime.",
            {"capability_id": capability_id},
        )
    if not include_instruction:
        entry = {**entry, "instruction_text": None}
    return CapabilityCatalogEntryOutput.from_api(entry)


def _score_capability(entry: Mapping[str, Any], objective: str, artifact_affinities: list[str]) -> float:
    objective_tokens = {token for token in re.findall(r"[a-z0-9_]+", objective.lower()) if token}
    if not objective_tokens:
        return 0.0
    text = " ".join(
        [
            str(entry.get("name") or ""),
            str(entry.get("description") or ""),
            " ".join(str(item) for item in entry.get("tags") or []),
            " ".join(str(item) for item in entry.get("artifact_affinities") or []),
        ]
    ).lower()
    score = sum(1.0 for token in objective_tokens if token in text)
    affinity_bonus = sum(
        1.5
        for affinity in artifact_affinities
        if affinity and affinity in {str(item) for item in entry.get("artifact_affinities") or []}
    )
    return score + affinity_bonus


def route_capabilities(runtime: Any, request: Mapping[str, Any]) -> CapabilityRoutePlanOutput:
    if runtime._uses_api_transport():
        return CapabilityRoutePlanOutput.from_api(runtime._client().route_capabilities(dict(request)))
    request_data = _coerce_mapping(request, "request")
    objective = str(request_data.get("objective") or "").strip()
    if not objective:
        raise RuntimeValidationError(
            "invalid_capability_route_request",
            "Capability route request requires objective.",
        )
    kinds = list(request_data.get("kinds") or [])
    provider_ids = list(request_data.get("provider_ids") or [])
    binding_ids = list(request_data.get("binding_ids") or [])
    artifact_affinities = list(request_data.get("artifact_affinities") or [])
    candidates = [
        entry.to_dict()
        for entry in list_capabilities(
            runtime,
            kinds=kinds or None,
            provider_ids=provider_ids or None,
            binding_ids=binding_ids or None,
        )
    ]
    if not candidates:
        raise RuntimeValidationError(
            "capability_route_no_candidates",
            "No local capabilities matched the route request filters.",
            {"objective": objective},
        )
    scored = sorted(
        (
            (_score_capability(entry, objective, artifact_affinities), entry)
            for entry in candidates
        ),
        key=lambda item: (-item[0], item[1]["capability_id"]),
    )
    best_score, best_entry = scored[0]
    if best_score <= 0:
        raise RuntimeValidationError(
            "capability_route_no_match",
            "No local capability matched the objective.",
            {"objective": objective},
        )
    fallback_items = [
        CapabilityRouteFallbackOutput.from_api(
            {
                "capability_id": entry["capability_id"],
                "provider_id": entry["provider_id"],
                "binding_id": entry["binding_id"],
                "kind": entry["kind"],
                "execution_owner": entry["execution_owner"],
                "confidence": round(min(score / 10.0, 0.99), 2),
                "reason": "Alternative local match.",
                "selected_tool_name": entry.get("selected_tool_name"),
                "instruction_artifact_ref": entry.get("instruction_artifact_ref"),
            }
        )
        for score, entry in scored[1:3]
        if score > 0
    ]
    return CapabilityRoutePlanOutput.from_api(
        {
            "selected_capability_id": best_entry["capability_id"],
            "selected_provider_id": best_entry["provider_id"],
            "selected_binding_id": best_entry["binding_id"],
            "kind": best_entry["kind"],
            "execution_owner": best_entry["execution_owner"],
            "requires_approval": bool(best_entry["approval_required"]),
            "confidence": round(min(best_score / 10.0, 0.99), 2),
            "reason": "Best local capability match for the objective.",
            "fallbacks": [item.to_dict() for item in fallback_items],
            "policy_snapshot_id": "capability-plane-policy-v1",
            "selected_tool_name": best_entry.get("selected_tool_name"),
            "instruction_artifact_ref": best_entry.get("instruction_artifact_ref"),
        }
    )


def execute_capability(runtime: Any, request: Mapping[str, Any]) -> CapabilityExecutionOutput:
    if runtime._uses_api_transport():
        return CapabilityExecutionOutput.from_api(
            runtime._client().execute_capability(dict(request))
        )
    request_data = _coerce_mapping(request, "request")
    capability_id = str(request_data.get("capability_id") or "").strip()
    if not capability_id:
        raise RuntimeValidationError(
            "invalid_capability_execution_request",
            "Capability execution requires capability_id.",
        )
    entry = get_capability(runtime, capability_id, include_instruction=True).to_dict()
    if entry["execution_owner"] != "client_managed":
        raise RuntimeValidationError(
            "capability_execution_owner_unsupported",
            "Local runtime execution only supports client_managed capabilities.",
            {
                "capability_id": capability_id,
                "execution_owner": entry["execution_owner"],
            },
        )
    started_at = _now_text()
    output: dict[str, Any] | None
    if entry["implementation_kind"] == "instruction_only":
        output = {
            "instruction_text": entry.get("instruction_text"),
            "instruction_artifact_ref": entry.get("instruction_artifact_ref"),
        }
    else:
        adapter = runtime._capability_adapters.get(capability_id)
        execute_fn = adapter.get("execute") if adapter else None
        if not callable(execute_fn):
            raise RuntimeValidationError(
                "capability_adapter_missing",
                "Local capability execution requires a registered adapter.",
                {"capability_id": capability_id},
            )
        adapter_result = execute_fn(dict(request_data.get("input") or {}))
        output = dict(adapter_result) if isinstance(adapter_result, Mapping) else {"result": adapter_result}
    execution = {
        "execution_session_id": str(uuid4()),
        "capability_id": capability_id,
        "provider_id": entry["provider_id"],
        "binding_id": entry["binding_id"],
        "execution_owner": entry["execution_owner"],
        "status": "succeeded",
        "output": output,
        "error": None,
        "started_at": started_at,
        "completed_at": _now_text(),
    }
    runtime._local_capability_executions[execution["execution_session_id"]] = execution
    return CapabilityExecutionOutput.from_api(execution)


def record_capability_outcome(
    runtime: Any,
    request: Mapping[str, Any],
) -> CapabilityOutcomeRecordOutput:
    if runtime._uses_api_transport():
        return CapabilityOutcomeRecordOutput.from_api(
            runtime._client().record_capability_outcome(dict(request))
        )
    request_data = _coerce_mapping(request, "request")
    if not request_data.get("capability_id") or not request_data.get("provider_id"):
        raise RuntimeValidationError(
            "invalid_capability_outcome_request",
            "Capability outcome requires capability_id and provider_id.",
        )
    outcome = {
        "outcome_id": str(uuid4()),
        "capability_id": str(request_data["capability_id"]),
        "provider_id": str(request_data["provider_id"]),
        "binding_id": request_data.get("binding_id"),
        "success": request_data.get("success"),
        "result_status": str(request_data.get("result_status") or "completed"),
        "confidence": request_data.get("confidence"),
        "latency_ms": request_data.get("latency_ms"),
        "error_code": request_data.get("error_code"),
        "details": dict(request_data.get("details") or {}) or None,
        "created_at": _now_text(),
    }
    runtime._local_capability_outcomes.append(outcome)
    return CapabilityOutcomeRecordOutput.from_api(outcome)


def list_skills(runtime: Any) -> list[CapabilityCatalogEntryOutput]:
    return list_capabilities(runtime, kinds=["skill"])


def enable_skill(
    runtime: Any,
    *,
    skill_name: str,
    instruction: str,
    description: str | None = None,
    tags: list[str] | None = None,
    artifact_affinities: list[str] | None = None,
    execution_owner: str = "client_managed",
) -> CapabilityDiscoverOutput:
    binding = create_capability_binding(
        runtime,
        {
            "provider_id": "provider.skill_pack.algenta",
            "profile_id": "profile.skill_pack.user",
            "binding_name": skill_name,
            "scope": "user",
            "execution_owner": execution_owner,
            "config": {
                "manifest": {
                    "capabilities": [
                        {
                            "capability_id": f"cap.skill.{skill_name.lower().replace(' ', '_')}",
                            "name": skill_name,
                            "description": description,
                            "kind": "skill",
                            "implementation_kind": "instruction_only",
                            "execution_owner": execution_owner,
                            "instruction": instruction,
                            "artifact_affinities": artifact_affinities or [],
                            "tags": tags or [],
                            "replayability": "deterministic",
                        }
                    ]
                }
            },
        },
    )
    return discover_capability_binding(runtime, binding.binding_id)


def disable_skill(runtime: Any, binding_id: str) -> None:
    delete_capability_binding(runtime, binding_id)


def list_mcp_providers(runtime: Any) -> list[CapabilityProviderOutput]:
    return [
        provider
        for provider in list_capability_providers(runtime)
        if provider.provider_type == "mcp_provider"
    ]
