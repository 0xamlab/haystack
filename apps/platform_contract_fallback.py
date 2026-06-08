from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from apps.platform_contract import (
    PlatformContractResponse,
    load_platform_contract_manifest_model,
)
from apps.platform_contract_constants import (
    ALGENTA_OWNED_HOSTS,
    ALGENTA_OWNED_SUFFIXES,
    API_BASE_URL,
    API_KEY_PREFIX_LIVE,
    API_KEY_PREFIX_TEST,
    AUTH_SCHEME,
    BRAND,
    CONTRACT_VERSION,
    DEPRECATION_WINDOW_DAYS,
    LEGACY_DOMAINS,
    LEGACY_ENV_VARS,
    LEGACY_HEADERS,
    MCP_ENDPOINT,
    MCP_TOOLS_ENDPOINT,
    PLAN_LIMITS,
    PRIVATE_HOST_SUFFIXES,
    VENDOR_TELEMETRY_HOSTS,
)


class PlatformContractFallbackError(ValueError):
    """Typed OpenAPI fallback validation error for app-side contract discovery."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _raise_fallback_error(code: str, message: str) -> None:
    raise PlatformContractFallbackError(code, message)


def _require_object(payload: Any, *, message: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        _raise_fallback_error("invalid_contract_payload", message)
    return payload


def _endpoint_suffix(endpoint: str) -> str:
    normalized_default = API_BASE_URL.rstrip("/")
    if endpoint.startswith(normalized_default):
        suffix = endpoint[len(normalized_default) :]
        return suffix or "/"
    parsed = urlsplit(endpoint)
    if parsed.scheme and parsed.netloc:
        suffix = parsed.path or "/"
        if parsed.query:
            suffix = f"{suffix}?{parsed.query}"
        return suffix
    if endpoint.startswith("/"):
        return endpoint
    return f"/{endpoint}"


def _rebase_endpoint(api_base_url: str, endpoint: str) -> str:
    return f"{api_base_url.rstrip('/')}{_endpoint_suffix(endpoint)}"


def _merge_contract_sections(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            merged[key] = _merge_contract_sections(merged.get(key), value)
        return merged
    return deepcopy(override)


def build_platform_contract_from_openapi(
    *,
    api_base_url: str,
    openapi_payload: Any,
) -> dict[str, Any]:
    schema = _require_object(
        openapi_payload,
        message="OpenAPI contract fallback payload must be a JSON object.",
    )
    primary_contract = schema.get("x-primary-data-query-contract")
    if not isinstance(primary_contract, dict):
        _raise_fallback_error(
            "contract_extension_missing",
            "OpenAPI schema is missing x-primary-data-query-contract.",
        )
    capability_plane_contract = schema.get("x-capability-plane-contract")
    if capability_plane_contract is not None and not isinstance(capability_plane_contract, dict):
        _raise_fallback_error(
            "invalid_contract_payload",
            "OpenAPI contract fallback returned an invalid x-capability-plane-contract payload.",
        )
    primary_api_contract = primary_contract.get("api")
    if not isinstance(primary_api_contract, dict):
        _raise_fallback_error(
            "invalid_contract_payload",
            "OpenAPI contract fallback is missing the api contract section.",
        )
    if not isinstance(primary_api_contract.get("contract_endpoint"), str):
        _raise_fallback_error(
            "invalid_contract_payload",
            "OpenAPI contract fallback is missing api.contract_endpoint.",
        )

    manifest = load_platform_contract_manifest_model()
    merged_primary_contract = _merge_contract_sections(
        manifest.primary_data_query_contract.model_dump(mode="python"),
        primary_contract,
    )
    if not isinstance(merged_primary_contract, dict):
        _raise_fallback_error(
            "invalid_contract_payload",
            "OpenAPI contract fallback returned an invalid payload.",
        )
    merged_api_contract = merged_primary_contract.get("api")
    if not isinstance(merged_api_contract, dict):
        _raise_fallback_error(
            "invalid_contract_payload",
            "OpenAPI contract fallback is missing the api contract section.",
        )
    merged_capability_plane_contract = None
    if capability_plane_contract is not None:
        manifest_capability_plane = (
            manifest.capability_plane.model_dump(mode="python")
            if manifest.capability_plane is not None
            else {}
        )
        merged_capability_plane_contract = _merge_contract_sections(
            manifest_capability_plane,
            capability_plane_contract,
        )
        if not isinstance(merged_capability_plane_contract, dict):
            _raise_fallback_error(
                "invalid_contract_payload",
                "OpenAPI capability-plane fallback returned an invalid payload.",
            )

    payload = {
        "contract_version": CONTRACT_VERSION,
        "brand": BRAND,
        "api_base_url": api_base_url.rstrip("/"),
        "mcp_endpoint": _rebase_endpoint(api_base_url, MCP_ENDPOINT),
        "mcp_tools_endpoint": _rebase_endpoint(api_base_url, MCP_TOOLS_ENDPOINT),
        "auth_scheme": AUTH_SCHEME,
        "api_key_prefixes": {
            "live": API_KEY_PREFIX_LIVE,
            "test": API_KEY_PREFIX_TEST,
        },
        "compatibility": {
            "legacy_headers": list(LEGACY_HEADERS),
            "legacy_env_vars": list(LEGACY_ENV_VARS),
            "legacy_domains": list(LEGACY_DOMAINS),
            "deprecation_window_days": DEPRECATION_WINDOW_DAYS,
        },
        "privacy_registry": {
            "algenta_owned_hosts": list(ALGENTA_OWNED_HOSTS),
            "algenta_owned_suffixes": list(ALGENTA_OWNED_SUFFIXES),
            "vendor_telemetry_hosts": list(VENDOR_TELEMETRY_HOSTS),
            "private_host_suffixes": list(PRIVATE_HOST_SUFFIXES),
        },
        "defaults": {
            "read_only_default": manifest.defaults.read_only_default,
            "write_confirmation_required": manifest.defaults.write_confirmation_required,
            "plan_limits": deepcopy(PLAN_LIMITS),
        },
        "primary_data_query_contract": merged_primary_contract,
        "capability_plane": merged_capability_plane_contract,
        "integrations": [item.model_dump(mode="python") for item in manifest.integrations],
    }
    try:
        return PlatformContractResponse.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        _raise_fallback_error(
            "invalid_contract_payload",
            f"OpenAPI contract fallback returned an invalid payload: {exc}",
        )
