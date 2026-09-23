"""MCP tools for machine-readable Algenta platform contract + runtime-manifest discovery.

Thin proxies: each fetches the authoritative contract / runtime manifest from the API and returns
it verbatim. The standalone package deliberately does NOT re-validate against engine-internal
pydantic models (the API is the source of truth) — that keeps algenta-mcp decoupled from the
monorepo and is the right posture for a client proxy.
"""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

GET_CONTRACT_SPEC: dict[str, Any] = {
    "name": "get_contract",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the machine-readable Algenta public contract. "
        "Use this when an agent needs the canonical discovery, summary, query, "
        "batch, SQL report, governed filter rules, CLI, or MCP entrypoints "
        "before planning tool use. Read-only and non-destructive; not separately rate-limited."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_MANIFEST_SPEC: dict[str, Any] = {
    "name": "get_runtime_manifest",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the signed Algenta runtime manifest. "
        "Use this when an agent needs the canonical runtime-core inventory, "
        "maturity states, proof matrix, typed failure contract, or release theorem "
        "before using runtime-backed execution paths. Read-only and non-destructive; "
        "not separately rate-limited."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_RELEASE_VALIDATION_SPEC: dict[str, Any] = {
    "name": "get_runtime_release_validation",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the authenticated Algenta runtime release validation result. "
        "Use this when an agent needs the current manifest-listed release verdict, "
        "formal theorem conditions, or fail-closed proof status before using runtime-backed paths. "
        "Read-only and non-destructive; not separately rate-limited."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_MODULES_SPEC: dict[str, Any] = {
    "name": "get_runtime_modules",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the authenticated Algenta runtime module proof catalog. "
        "Use this when an agent needs the shipping module inventory, proof-matrix entries, "
        "maturity counts, or compiled module evidence before using runtime-backed paths. "
        "Read-only and non-destructive; not separately rate-limited."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_RUNTIME_BENCHMARKS_SPEC: dict[str, Any] = {
    "name": "get_runtime_benchmarks",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the authenticated Algenta runtime benchmark catalog. "
        "Use this when an agent needs benchmark classes, benchmark evidence paths, "
        "evaluation quality gates, SLO budgets, compiled artifacts, or module benchmark "
        "linkage before reasoning about runtime performance claims. Read-only and "
        "non-destructive; not separately rate-limited."
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
    # api() raises a redacted MCPAPIError on >=400 (no raw-body leak), returns the payload on 200.
    return json.dumps(await api("GET", "/v1/meta/contract"), indent=2)


async def _proxy_get(endpoint: str, *, no_args_name: str, arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError(f"{no_args_name} does not accept arguments.")
    return json.dumps(await api("GET", endpoint), indent=2)


async def get_runtime_manifest_handler(arguments: dict[str, Any]) -> str:
    return await _proxy_get(
        "/v1/runtime/manifest", no_args_name="get_runtime_manifest", arguments=arguments
    )


async def get_runtime_release_validation_handler(arguments: dict[str, Any]) -> str:
    return await _proxy_get(
        "/v1/admin/runtime/validation",
        no_args_name="get_runtime_release_validation",
        arguments=arguments,
    )


async def get_runtime_modules_handler(arguments: dict[str, Any]) -> str:
    return await _proxy_get(
        "/v1/admin/runtime/modules", no_args_name="get_runtime_modules", arguments=arguments
    )


async def get_runtime_benchmarks_handler(arguments: dict[str, Any]) -> str:
    return await _proxy_get(
        "/v1/admin/runtime/benchmarks", no_args_name="get_runtime_benchmarks", arguments=arguments
    )
