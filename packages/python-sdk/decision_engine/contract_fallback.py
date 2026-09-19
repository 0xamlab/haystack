# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from pydantic import ValidationError as PydanticValidationError

from ._contract import (
    ALGENTA_OWNED_HOSTS,
    ALGENTA_OWNED_SUFFIXES,
    API_KEY_PREFIX_LIVE,
    API_KEY_PREFIX_TEST,
    AUTH_SCHEME,
    BRAND,
    CAPABILITY_PLANE_CONTRACT,
    CONTRACT_VERSION,
    DEFAULT_BASE_URL,
    DEPRECATION_WINDOW_DAYS,
    INTEGRATIONS,
    LEGACY_DOMAINS,
    LEGACY_ENV_VARS,
    LEGACY_HEADERS,
    MCP_ENDPOINT,
    MCP_LEGACY_SSE_ENDPOINT,
    MCP_PROTOCOL_VERSION,
    MCP_TOOLS_ENDPOINT,
    MCP_TRANSPORT,
    PLAN_LIMITS,
    PRIMARY_DATA_QUERY_CONTRACT,
    PRIVATE_HOST_SUFFIXES,
    READ_ONLY_DEFAULT,
    VENDOR_TELEMETRY_HOSTS,
    WRITE_CONFIRMATION_REQUIRED,
)
from .exceptions import DecisionEngineError
from .model_loader import validate_model as _validate_model
from .validation_error_details import build_validation_error_details

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient
    from .client_facade import DecisionEngineClient


def _as_object(payload: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DecisionEngineError(
            f"{context} must be a JSON object.",
            response_body={"error": {"code": "invalid_contract_payload"}},
        )
    return payload


def _endpoint_suffix(endpoint: str) -> str:
    normalized_default = DEFAULT_BASE_URL.rstrip("/")
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


def _build_contract_payload(api_base_url: str, openapi_payload: Any) -> dict[str, Any]:
    schema = _as_object(openapi_payload, context="OpenAPI contract fallback payload")
    primary_contract = schema.get("x-primary-data-query-contract")
    if not isinstance(primary_contract, dict):
        raise DecisionEngineError(
            "OpenAPI contract fallback is missing x-primary-data-query-contract.",
            response_body={"error": {"code": "contract_extension_missing"}},
        )
    capability_plane_contract = schema.get("x-capability-plane-contract")
    if capability_plane_contract is not None and not isinstance(capability_plane_contract, dict):
        raise DecisionEngineError(
            "OpenAPI contract fallback returned an invalid x-capability-plane-contract payload.",
            response_body={"error": {"code": "invalid_contract_payload"}},
        )
    primary_api_contract = primary_contract.get("api")
    if not isinstance(primary_api_contract, dict):
        raise DecisionEngineError(
            "OpenAPI contract fallback is missing the api contract section.",
            response_body={"error": {"code": "invalid_contract_payload"}},
        )
    if not isinstance(primary_api_contract.get("contract_endpoint"), str):
        raise DecisionEngineError(
            "OpenAPI contract fallback is missing api.contract_endpoint.",
            response_body={"error": {"code": "invalid_contract_payload"}},
        )
    merged_primary_contract = _merge_contract_sections(
        PRIMARY_DATA_QUERY_CONTRACT,
        primary_contract,
    )
    merged_api_contract = merged_primary_contract.get("api")
    if not isinstance(merged_api_contract, dict):
        raise DecisionEngineError(
            "OpenAPI contract fallback is missing the api contract section.",
            response_body={"error": {"code": "invalid_contract_payload"}},
        )
    merged_capability_plane = None
    if capability_plane_contract is not None:
        merged_capability_plane = _merge_contract_sections(
            CAPABILITY_PLANE_CONTRACT or {},
            capability_plane_contract,
        )
        if not isinstance(merged_capability_plane, dict):
            raise DecisionEngineError(
                "OpenAPI capability-plane fallback returned an invalid payload.",
                response_body={"error": {"code": "invalid_contract_payload"}},
            )
    return {
        "contract_version": CONTRACT_VERSION,
        "brand": BRAND,
        "api_base_url": api_base_url.rstrip("/"),
        "mcp_endpoint": _rebase_endpoint(api_base_url, MCP_ENDPOINT),
        "mcp_transport": MCP_TRANSPORT,
        "mcp_protocol_version": MCP_PROTOCOL_VERSION,
        "mcp_legacy_sse_endpoint": _rebase_endpoint(api_base_url, MCP_LEGACY_SSE_ENDPOINT),
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
            "read_only_default": READ_ONLY_DEFAULT,
            "write_confirmation_required": WRITE_CONFIRMATION_REQUIRED,
            "plan_limits": deepcopy(PLAN_LIMITS),
        },
        "primary_data_query_contract": merged_primary_contract,
        "capability_plane": merged_capability_plane,
        "integrations": deepcopy(INTEGRATIONS),
    }


def _raise_invalid_contract_payload(exc: PydanticValidationError) -> None:
    message = f"OpenAPI contract fallback returned an invalid payload: {exc}"
    raise DecisionEngineError(
        message,
        response_body={
            "error": {
                "code": "invalid_contract_payload",
                "details": build_validation_error_details(exc),
            }
        },
    ) from exc


def load_contract_from_openapi(client: DecisionEngineClient):
    payload = _build_contract_payload(
        client._base_url,
        client._request("GET", "/openapi.json"),
    )
    try:
        return _validate_model("PlatformContractResult", payload)
    except PydanticValidationError as exc:
        _raise_invalid_contract_payload(exc)


async def load_contract_from_openapi_async(client: AsyncDecisionEngineClient):
    payload = _build_contract_payload(
        client._base_url,
        await client._request("GET", "/openapi.json"),
    )
    try:
        return _validate_model("PlatformContractResult", payload)
    except PydanticValidationError as exc:
        _raise_invalid_contract_payload(exc)


__all__ = [
    "load_contract_from_openapi",
    "load_contract_from_openapi_async",
]
