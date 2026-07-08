from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{context}.{key} must be a string when provided.")
    return value


def _require_bool(data: dict[str, Any], key: str, context: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{context}.{key} must be a boolean.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _optional_number(data: dict[str, Any], key: str, context: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number when provided.")
    return float(value)


def _optional_integer(data: dict[str, Any], key: str, context: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer when provided.")
    return value


def _require_mapping(data: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise TypeError(f"{context}.{key} must be an object.")
    return value


def _optional_mapping(data: dict[str, Any], key: str, context: str) -> dict[str, Any] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"{context}.{key} must be an object when provided.")
    return value


def _require_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{context}.{key} must be a list of strings.")
    return list(value)


def _optional_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{context}.{key} must be a list of strings when provided.")
    return list(value)


@dataclass(frozen=True)
class CapabilityProviderProfileOutput:
    profile_id: str
    provider_id: str
    name: str
    description: str | None
    auth_kind: str
    default_execution_owner: str
    binding_scope_default: str
    supported_binding_scopes: list[str] = field(default_factory=list)
    profile_metadata: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityProviderProfileOutput:
        context = "capability_provider_profile"
        data = coerce_payload_mapping(payload)
        return cls(
            profile_id=_require_string(data, "profile_id", context),
            provider_id=_require_string(data, "provider_id", context),
            name=_require_string(data, "name", context),
            description=_optional_string(data, "description", context),
            auth_kind=_require_string(data, "auth_kind", context),
            default_execution_owner=_require_string(data, "default_execution_owner", context),
            binding_scope_default=_require_string(data, "binding_scope_default", context),
            supported_binding_scopes=_optional_string_list(data, "supported_binding_scopes", context),
            profile_metadata=_optional_mapping(data, "profile_metadata", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityProviderOutput:
    provider_id: str
    provider_type: str
    name: str
    description: str | None
    docs_url: str | None
    auth_schema: dict[str, Any] | None
    certification_summary: dict[str, Any] | None
    policy_summary: dict[str, Any] | None
    supported_execution_owners: list[str] = field(default_factory=list)
    install_metadata: dict[str, Any] | None = None
    customer_metadata: dict[str, Any] | None = None
    active: bool = True
    profiles: list[CapabilityProviderProfileOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityProviderOutput:
        context = "capability_provider"
        data = coerce_payload_mapping(payload)
        raw_profiles = data.get("profiles", [])
        if not isinstance(raw_profiles, list):
            raise TypeError(f"{context}.profiles must be a list.")
        return cls(
            provider_id=_require_string(data, "provider_id", context),
            provider_type=_require_string(data, "provider_type", context),
            name=_require_string(data, "name", context),
            description=_optional_string(data, "description", context),
            docs_url=_optional_string(data, "docs_url", context),
            auth_schema=_optional_mapping(data, "auth_schema", context),
            certification_summary=_optional_mapping(data, "certification_summary", context),
            policy_summary=_optional_mapping(data, "policy_summary", context),
            supported_execution_owners=_optional_string_list(data, "supported_execution_owners", context),
            install_metadata=_optional_mapping(data, "install_metadata", context),
            customer_metadata=_optional_mapping(data, "customer_metadata", context),
            active=_require_bool(data, "active", context),
            profiles=[CapabilityProviderProfileOutput.from_api(item) for item in raw_profiles],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                **asdict(self),
                "profiles": [profile.to_dict() for profile in self.profiles],
            }
        )


@dataclass(frozen=True)
class CapabilityBindingOutput:
    binding_id: str
    provider_id: str
    profile_id: str
    binding_name: str
    scope: str
    scope_ref: str
    status: str
    execution_owner: str
    config: dict[str, Any] | None
    customer_metadata: dict[str, Any] | None
    system_managed: bool
    last_tested_at: str | None
    last_discovered_at: str | None
    authorized_at: str | None
    quarantine_reason: str | None
    discovery_error_message: str | None
    test_error_message: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityBindingOutput:
        context = "capability_binding"
        data = coerce_payload_mapping(payload)
        return cls(
            binding_id=_require_string(data, "binding_id", context),
            provider_id=_require_string(data, "provider_id", context),
            profile_id=_require_string(data, "profile_id", context),
            binding_name=_require_string(data, "binding_name", context),
            scope=_require_string(data, "scope", context),
            scope_ref=_require_string(data, "scope_ref", context),
            status=_require_string(data, "status", context),
            execution_owner=_require_string(data, "execution_owner", context),
            config=_optional_mapping(data, "config", context),
            customer_metadata=_optional_mapping(data, "customer_metadata", context),
            system_managed=_require_bool(data, "system_managed", context),
            last_tested_at=_optional_string(data, "last_tested_at", context),
            last_discovered_at=_optional_string(data, "last_discovered_at", context),
            authorized_at=_optional_string(data, "authorized_at", context),
            quarantine_reason=_optional_string(data, "quarantine_reason", context),
            discovery_error_message=_optional_string(data, "discovery_error_message", context),
            test_error_message=_optional_string(data, "test_error_message", context),
            created_at=_require_string(data, "created_at", context),
            updated_at=_require_string(data, "updated_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityBindingTestOutput:
    success: bool
    binding_status: str
    message: str
    latency_ms: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityBindingTestOutput:
        context = "capability_binding_test"
        data = coerce_payload_mapping(payload)
        return cls(
            success=_require_bool(data, "success", context),
            binding_status=_require_string(data, "binding_status", context),
            message=_require_string(data, "message", context),
            latency_ms=_optional_integer(data, "latency_ms", context),
            details=_optional_mapping(data, "details", context) or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityCatalogEntryOutput:
    capability_id: str
    provider_id: str
    profile_id: str
    binding_id: str
    kind: str
    name: str
    description: str | None
    implementation_kind: str
    execution_owner: str
    input_schema_ref: str
    output_schema_ref: str
    side_effect_class: str
    risk_level: str
    required_policy: str
    replayability: str
    approval_required: bool
    trust_tier: str
    manifest_hash: str
    artifact_affinities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    required_binding_ids: list[str] = field(default_factory=list)
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None
    binding_status: str = "ready"
    discovered_at: str | None = None
    customer_metadata: dict[str, Any] | None = None
    instruction_text: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityCatalogEntryOutput:
        context = "capability_catalog_entry"
        data = coerce_payload_mapping(payload)
        return cls(
            capability_id=_require_string(data, "capability_id", context),
            provider_id=_require_string(data, "provider_id", context),
            profile_id=_require_string(data, "profile_id", context),
            binding_id=_require_string(data, "binding_id", context),
            kind=_require_string(data, "kind", context),
            name=_require_string(data, "name", context),
            description=_optional_string(data, "description", context),
            implementation_kind=_require_string(data, "implementation_kind", context),
            execution_owner=_require_string(data, "execution_owner", context),
            input_schema_ref=_require_string(data, "input_schema_ref", context),
            output_schema_ref=_require_string(data, "output_schema_ref", context),
            side_effect_class=_require_string(data, "side_effect_class", context),
            risk_level=_require_string(data, "risk_level", context),
            required_policy=_require_string(data, "required_policy", context),
            replayability=_require_string(data, "replayability", context),
            approval_required=_require_bool(data, "approval_required", context),
            trust_tier=_require_string(data, "trust_tier", context),
            manifest_hash=_require_string(data, "manifest_hash", context),
            artifact_affinities=_optional_string_list(data, "artifact_affinities", context),
            tags=_optional_string_list(data, "tags", context),
            required_binding_ids=_optional_string_list(data, "required_binding_ids", context),
            selected_tool_name=_optional_string(data, "selected_tool_name", context),
            instruction_artifact_ref=_optional_string(data, "instruction_artifact_ref", context),
            binding_status=_require_string(data, "binding_status", context),
            discovered_at=_optional_string(data, "discovered_at", context),
            customer_metadata=_optional_mapping(data, "customer_metadata", context),
            instruction_text=_optional_string(data, "instruction_text", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityDiscoverOutput:
    binding_id: str | None
    provider_id: str
    profile_id: str
    snapshot_id: str | None
    binding_status: str
    manifest_hash: str
    capability_count: int
    discovered_at: str
    message: str
    capabilities: list[CapabilityCatalogEntryOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityDiscoverOutput:
        context = "capability_discover"
        data = coerce_payload_mapping(payload)
        raw_capabilities = data.get("capabilities", [])
        if not isinstance(raw_capabilities, list):
            raise TypeError(f"{context}.capabilities must be a list.")
        return cls(
            binding_id=_optional_string(data, "binding_id", context),
            provider_id=_require_string(data, "provider_id", context),
            profile_id=_require_string(data, "profile_id", context),
            snapshot_id=_optional_string(data, "snapshot_id", context),
            binding_status=_require_string(data, "binding_status", context),
            manifest_hash=_require_string(data, "manifest_hash", context),
            capability_count=int(_require_number(data, "capability_count", context)),
            discovered_at=_require_string(data, "discovered_at", context),
            message=_require_string(data, "message", context),
            capabilities=[CapabilityCatalogEntryOutput.from_api(item) for item in raw_capabilities],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                **asdict(self),
                "capabilities": [capability.to_dict() for capability in self.capabilities],
            }
        )


@dataclass(frozen=True)
class CapabilityRouteFallbackOutput:
    capability_id: str
    provider_id: str
    binding_id: str
    kind: str
    execution_owner: str
    confidence: float
    reason: str
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityRouteFallbackOutput:
        context = "capability_route_fallback"
        data = coerce_payload_mapping(payload)
        return cls(
            capability_id=_require_string(data, "capability_id", context),
            provider_id=_require_string(data, "provider_id", context),
            binding_id=_require_string(data, "binding_id", context),
            kind=_require_string(data, "kind", context),
            execution_owner=_require_string(data, "execution_owner", context),
            confidence=_require_number(data, "confidence", context),
            reason=_require_string(data, "reason", context),
            selected_tool_name=_optional_string(data, "selected_tool_name", context),
            instruction_artifact_ref=_optional_string(data, "instruction_artifact_ref", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityRoutePlanOutput:
    selected_capability_id: str
    selected_provider_id: str
    selected_binding_id: str
    kind: str
    execution_owner: str
    requires_approval: bool
    confidence: float
    reason: str
    fallbacks: list[CapabilityRouteFallbackOutput] = field(default_factory=list)
    policy_snapshot_id: str = "capability-plane-policy-v1"
    selected_tool_name: str | None = None
    instruction_artifact_ref: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityRoutePlanOutput:
        context = "capability_route_plan"
        data = coerce_payload_mapping(payload)
        raw_fallbacks = data.get("fallbacks", [])
        if not isinstance(raw_fallbacks, list):
            raise TypeError(f"{context}.fallbacks must be a list.")
        return cls(
            selected_capability_id=_require_string(data, "selected_capability_id", context),
            selected_provider_id=_require_string(data, "selected_provider_id", context),
            selected_binding_id=_require_string(data, "selected_binding_id", context),
            kind=_require_string(data, "kind", context),
            execution_owner=_require_string(data, "execution_owner", context),
            requires_approval=_require_bool(data, "requires_approval", context),
            confidence=_require_number(data, "confidence", context),
            reason=_require_string(data, "reason", context),
            fallbacks=[CapabilityRouteFallbackOutput.from_api(item) for item in raw_fallbacks],
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            selected_tool_name=_optional_string(data, "selected_tool_name", context),
            instruction_artifact_ref=_optional_string(data, "instruction_artifact_ref", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                **asdict(self),
                "fallbacks": [fallback.to_dict() for fallback in self.fallbacks],
            }
        )


@dataclass(frozen=True)
class CapabilityExecutionOutput:
    execution_session_id: str
    capability_id: str
    provider_id: str
    binding_id: str
    execution_owner: str
    status: str
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    started_at: str
    completed_at: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityExecutionOutput:
        context = "capability_execution"
        data = coerce_payload_mapping(payload)
        return cls(
            execution_session_id=_require_string(data, "execution_session_id", context),
            capability_id=_require_string(data, "capability_id", context),
            provider_id=_require_string(data, "provider_id", context),
            binding_id=_require_string(data, "binding_id", context),
            execution_owner=_require_string(data, "execution_owner", context),
            status=_require_string(data, "status", context),
            output=_optional_mapping(data, "output", context),
            error=_optional_mapping(data, "error", context),
            started_at=_require_string(data, "started_at", context),
            completed_at=_optional_string(data, "completed_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityOutcomeRecordOutput:
    outcome_id: str
    capability_id: str
    provider_id: str
    binding_id: str | None
    success: bool | None
    result_status: str
    confidence: float | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None
    created_at: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityOutcomeRecordOutput:
        context = "capability_outcome"
        data = coerce_payload_mapping(payload)
        success = data.get("success")
        if success is not None and not isinstance(success, bool):
            raise TypeError(f"{context}.success must be a boolean when provided.")
        return cls(
            outcome_id=_require_string(data, "outcome_id", context),
            capability_id=_require_string(data, "capability_id", context),
            provider_id=_require_string(data, "provider_id", context),
            binding_id=_optional_string(data, "binding_id", context),
            success=success,
            result_status=_require_string(data, "result_status", context),
            confidence=_optional_number(data, "confidence", context),
            latency_ms=_optional_integer(data, "latency_ms", context),
            error_code=_optional_string(data, "error_code", context),
            details=_optional_mapping(data, "details", context),
            created_at=_require_string(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityAuthorizationStartOutput:
    session_id: str
    binding_id: str
    provider_id: str
    authorize_url: str
    expires_at: str
    requested_scopes: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityAuthorizationStartOutput:
        context = "capability_authorization_start"
        data = coerce_payload_mapping(payload)
        return cls(
            session_id=_require_string(data, "session_id", context),
            binding_id=_require_string(data, "binding_id", context),
            provider_id=_require_string(data, "provider_id", context),
            authorize_url=_require_string(data, "authorize_url", context),
            expires_at=_require_string(data, "expires_at", context),
            requested_scopes=_optional_string_list(data, "requested_scopes", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CapabilityAuthorizationCompleteOutput:
    session_id: str
    binding_id: str
    provider_id: str
    status: str
    authorized_at: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> CapabilityAuthorizationCompleteOutput:
        context = "capability_authorization_complete"
        data = coerce_payload_mapping(payload)
        return cls(
            session_id=_require_string(data, "session_id", context),
            binding_id=_require_string(data, "binding_id", context),
            provider_id=_require_string(data, "provider_id", context),
            status=_require_string(data, "status", context),
            authorized_at=_optional_string(data, "authorized_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
