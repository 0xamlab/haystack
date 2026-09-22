"""MCP proxies for the Algenta runtime-library HTTP surface."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_RUNTIME_LIBRARIES_SPEC: dict[str, Any] = {
    "name": "list_runtime_libraries",
    "description": (
        "List the executable Algenta runtime libraries with their engine and public "
        "functions — the discovery step before execute_runtime_library. q filters by "
        "substring against module names and exported functions. The tool paginates "
        "the API for you and returns up to limit modules in one response (default "
        "1000). Read-only. Returns modules, total, count, page, and limit."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "q": {
                "type": "string",
                "minLength": 1,
                "description": "Substring match against module names and exported functions.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 1000,
                "description": "Maximum modules to return, up to 1000; defaults to 1000.",
            },
        },
        "additionalProperties": False,
    },
}

EXECUTE_RUNTIME_LIBRARY_SPEC: dict[str, Any] = {
    "name": "execute_runtime_library",
    "description": (
        "Execute one public function from an Algenta runtime library with positional "
        "args and return its result, latency_ms, engine_used, and request_id. Call "
        "list_runtime_libraries first to discover exact module and function names — "
        "an unknown pair fails with module_not_registered or function_not_registered, "
        "and a mismatched args list fails with invalid_arguments. Synchronous "
        "compute; nothing is persisted."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["module", "function"],
        "properties": {
            "module": {
                "type": "string",
                "minLength": 1,
                "description": "Runtime library module name from list_runtime_libraries.",
            },
            "function": {
                "type": "string",
                "minLength": 1,
                "description": "Public function exported by the module.",
            },
            "args": {
                "description": "Positional argument list passed to the function.",
            },
            "request_id": {
                "type": "string",
                "minLength": 1,
                "description": "Optional caller request id for correlation.",
            },
        },
        "additionalProperties": False,
    },
}


async def list_runtime_libraries_handler(arguments: dict[str, Any]) -> str:
    requested_limit = int(arguments.get("limit", 1000))
    params: dict[str, Any] = {"limit": min(requested_limit, 200)}
    query = arguments.get("q")
    if query is not None:
        params["q"] = query
    first_page = await api("GET", "/v1/libraries", params=params)
    if not isinstance(first_page, dict) or not isinstance(first_page.get("modules"), list):
        return json.dumps(first_page, indent=2)

    modules = list(first_page["modules"])
    total = int(first_page.get("total", len(modules)))
    page = 2
    while len(modules) < min(total, requested_limit):
        page_payload = await api(
            "GET",
            "/v1/libraries",
            params={**params, "page": page},
        )
        if not isinstance(page_payload, dict) or not isinstance(
            page_payload.get("modules"), list
        ):
            raise RuntimeError("Runtime library API returned a malformed page.")
        page_modules = page_payload["modules"]
        if not page_modules:
            break
        modules.extend(page_modules)
        page += 1

    result = dict(first_page)
    result["modules"] = modules[:requested_limit]
    result["count"] = len(result["modules"])
    result["limit"] = requested_limit
    result["page"] = 1
    return json.dumps(result, indent=2)


async def execute_runtime_library_handler(arguments: dict[str, Any]) -> str:
    payload = {
        "module": arguments["module"],
        "function": arguments["function"],
        "args": arguments.get("args"),
    }
    if "request_id" in arguments:
        payload["request_id"] = arguments["request_id"]
    return json.dumps(await api("POST", "/v1/libraries/execute", json=payload), indent=2)
