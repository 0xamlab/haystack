"""MCP tools for machine-readable Algenta platform contract discovery."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from apps.mcp_server.client import api_with_status, resolve_base_url
from apps.platform_contract import PlatformContractResponse
from apps.platform_contract_fallback import (
    PlatformContractFallbackError,
    build_platform_contract_from_openapi,
)
from apps.validation_error_details import format_validation_error_message

GET_CONTRACT_SPEC: dict[str, Any] = {
    "name": "get_contract",
    "description": (
        "Get the machine-readable Algenta public contract. "
        "Use this when an agent needs the canonical discovery, summary, query, "
        "batch, SQL report, governed filter rules, CLI, or MCP entrypoints "
        "before planning tool use."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_MANIFEST_SPEC: dict[str, Any] = {
    "name": "get_runtime_manifest",
    "description": (
        "Get the signed Algenta runtime manifest. "
        "Use this when an agent needs the canonical runtime-core inventory, "
        "maturity states, proof matrix, typed failure contract, or release theorem "
        "before using runtime-backed execution paths."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_RELEASE_VALIDATION_SPEC: dict[str, Any] = {
    "name": "get_runtime_release_validation",
    "description": (
        "Get the authenticated Algenta runtime release validation result. "
        "Use this when an agent needs the current manifest-listed release verdict, "
        "formal theorem conditions, or fail-closed proof status before using runtime-backed paths."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_MODULES_SPEC: dict[str, Any] = {
    "name": "get_runtime_modules",
    "description": (
        "Get the authenticated Algenta runtime module proof catalog. "
        "Use this when an agent needs the shipping module inventory, proof-matrix entries, "
        "maturity counts, or compiled module evidence before using runtime-backed paths."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_BENCHMARKS_SPEC: dict[str, Any] = {
    "name": "get_runtime_benchmarks",
    "description": (
        "Get the authenticated Algenta runtime benchmark catalog. "
        "Use this when an agent needs benchmark classes, benchmark evidence paths, "
        "evaluation quality gates, SLO budgets, compiled artifacts, or module benchmark "
        "linkage before reasoning about runtime performance claims."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


async def get_contract_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_contract does not accept arguments.")
    status, result = await api_with_status("GET", "/v1/meta/contract")
    if status == 404:
        openapi_status, openapi_payload = await api_with_status("GET", "/openapi.json")
        if openapi_status >= 400:
            raise RuntimeError(
                "Failed to load Algenta contract from /v1/meta/contract or /openapi.json."
            )
        try:
            result = build_platform_contract_from_openapi(
                api_base_url=resolve_base_url(),
                openapi_payload=openapi_payload,
            )
        except PlatformContractFallbackError as exc:
            raise RuntimeError(
                f"Algenta contract fallback failed [{exc.code}]: {exc}"
            ) from exc
    elif status >= 400:
        raise RuntimeError(f"API error {status}: {result}")
    try:
        payload = PlatformContractResponse.model_validate(result)
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta contract endpoint returned an invalid payload.",
                exc,
            )
        ) from exc
    output = {
        "contract_version": payload.contract_version,
        "brand": payload.brand,
        "api_base_url": payload.api_base_url,
        "mcp_endpoint": payload.mcp_endpoint,
        "mcp_transport": payload.mcp_transport,
        "mcp_protocol_version": payload.mcp_protocol_version,
        "mcp_legacy_sse_endpoint": payload.mcp_legacy_sse_endpoint,
        "mcp_tools_endpoint": payload.mcp_tools_endpoint,
        "auth_scheme": payload.auth_scheme,
        "primary_data_query_contract": payload.primary_data_query_contract.model_dump(mode="json"),
        "capability_plane": (
            payload.capability_plane.model_dump(mode="json")
            if payload.capability_plane is not None
            else None
        ),
        "integrations": payload.model_dump(mode="json")["integrations"],
    }
    return json.dumps(output, indent=2)


async def get_runtime_manifest_handler(arguments: dict[str, Any]) -> str:
    from apps.runtime_manifest import (
        RuntimeManifestResponse,
        normalize_runtime_validation_payload,
    )

    if arguments:
        raise ValueError("get_runtime_manifest does not accept arguments.")
    status, result = await api_with_status("GET", "/v1/runtime/manifest")
    if status >= 400:
        raise RuntimeError(f"API error {status}: {result}")
    try:
        payload = RuntimeManifestResponse.model_validate(
            normalize_runtime_validation_payload(result)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime manifest endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    return json.dumps(payload.model_dump(mode="json"), indent=2)


async def get_runtime_release_validation_handler(arguments: dict[str, Any]) -> str:
    from apps.runtime_manifest import (
        RuntimeReleaseValidationResponse,
        normalize_runtime_validation_payload,
    )

    if arguments:
        raise ValueError("get_runtime_release_validation does not accept arguments.")
    status, result = await api_with_status("GET", "/v1/admin/runtime/validation")
    if status >= 400:
        raise RuntimeError(f"API error {status}: {result}")
    try:
        payload = RuntimeReleaseValidationResponse.model_validate(
            normalize_runtime_validation_payload(result)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime release validation endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    return json.dumps(payload.model_dump(mode="json"), indent=2)


async def get_runtime_modules_handler(arguments: dict[str, Any]) -> str:
    from apps.runtime_manifest import (
        RuntimeAdminModulesResponse,
        normalize_runtime_validation_payload,
    )

    if arguments:
        raise ValueError("get_runtime_modules does not accept arguments.")
    status, result = await api_with_status("GET", "/v1/admin/runtime/modules")
    if status >= 400:
        raise RuntimeError(f"API error {status}: {result}")
    try:
        payload = RuntimeAdminModulesResponse.model_validate(
            normalize_runtime_validation_payload(result)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime modules endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    return json.dumps(payload.model_dump(mode="json"), indent=2)


async def get_runtime_benchmarks_handler(arguments: dict[str, Any]) -> str:
    from apps.runtime_manifest import (
        RuntimeAdminBenchmarksResponse,
        normalize_runtime_validation_payload,
    )

    if arguments:
        raise ValueError("get_runtime_benchmarks does not accept arguments.")
    status, result = await api_with_status("GET", "/v1/admin/runtime/benchmarks")
    if status >= 400:
        raise RuntimeError(f"API error {status}: {result}")
    try:
        payload = RuntimeAdminBenchmarksResponse.model_validate(
            normalize_runtime_validation_payload(result)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime benchmarks endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    return json.dumps(payload.model_dump(mode="json"), indent=2)
