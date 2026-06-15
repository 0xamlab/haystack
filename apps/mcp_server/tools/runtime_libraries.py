"""MCP tools for local runtime-backed Mojo library inventory and execution."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from apps.runtime.client import DaemonClient


class RuntimeLibraryInfo(TypedDict):
    name: str
    engine: str
    functions: list[str]


LIST_RUNTIME_LIBRARIES_SPEC: dict[str, Any] = {
    "name": "list_runtime_libraries",
    "description": (
        "List executable local-runtime Mojo libraries. "
        "Use this when you need the runtime-backed compute catalog rather than the "
        "governed data/query tools. This surface is local/runtime-backed only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional lexical filter over module names and function names.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of libraries to return after filtering.",
            },
        },
    },
}

EXECUTE_RUNTIME_LIBRARY_SPEC: dict[str, Any] = {
    "name": "execute_runtime_library",
    "description": (
        "Execute one local-runtime Mojo library function by module and function name. "
        "Pass args as either a JSON object, array, scalar, or null. "
        "This surface is local/runtime-backed only and does not route through hosted "
        "data/query APIs."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["module", "function"],
        "properties": {
            "module": {
                "type": "string",
                "description": "Canonical runtime module name, including dotted names.",
            },
            "function": {
                "type": "string",
                "description": "Function name exposed by the runtime module.",
            },
            "args": {
                "description": (
                    "JSON-serializable args payload. May be an object, array, scalar, or null."
                ),
            },
            "request_id": {
                "type": "string",
                "description": "Optional stable request identifier for traceability.",
            },
        },
    },
}


async def _list_runtime_modules() -> tuple[dict[str, Any], list[RuntimeLibraryInfo]]:
    client = DaemonClient(timeout=20.0)
    health = await client.health()
    if health.get("status") == "unreachable":
        raise RuntimeError(
            "Local Codna runtime daemon is unavailable. "
            "Start it before using runtime library MCP tools."
        )
    modules = await client.list_modules()
    if not modules:
        raise RuntimeError("Local Codna runtime returned no executable Mojo libraries.")
    normalized: list[RuntimeLibraryInfo] = []
    for module in modules:
        raw_functions = module.get("functions", [])
        functions = (
            [str(function) for function in raw_functions] if isinstance(raw_functions, list) else []
        )
        normalized.append(
            {
                "name": str(module.get("name", "")),
                "engine": str(module.get("engine", "")),
                "functions": functions,
            }
        )
    normalized.sort(key=lambda module: module["name"])
    return dict(health), normalized


async def list_runtime_libraries_handler(arguments: dict[str, Any]) -> str:
    health, modules = await _list_runtime_modules()
    search_value = str(arguments.get("search") or "").strip().lower()
    if search_value:
        modules = [
            module
            for module in modules
            if search_value in module["name"].lower()
            or any(search_value in function.lower() for function in module["functions"])
        ]
    limit_value = arguments.get("limit")
    if limit_value is not None:
        try:
            limit = max(1, int(limit_value))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("limit must be a positive integer.") from exc
        modules = modules[:limit]

    return json.dumps(
        {
            "runtime_health": health,
            "module_count": len(modules),
            "libraries": modules,
        },
        indent=2,
    )


async def execute_runtime_library_handler(arguments: dict[str, Any]) -> str:
    module_name = str(arguments.get("module") or "").strip()
    function_name = str(arguments.get("function") or "").strip()
    if not module_name:
        raise RuntimeError("module is required.")
    if not function_name:
        raise RuntimeError("function is required.")

    client = DaemonClient(timeout=30.0)
    health = await client.health()
    if health.get("status") == "unreachable":
        raise RuntimeError(
            "Local Codna runtime daemon is unavailable. "
            "Start it before using runtime library MCP tools."
        )

    result = await client.execute(
        module_name,
        function_name,
        arguments.get("args"),
        request_id=str(arguments.get("request_id") or ""),
    )
    if not result.get("success", False):
        raise RuntimeError(str(result.get("error", "Runtime-backed Mojo execution failed.")))

    return json.dumps(
        {
            "module": module_name,
            "function": function_name,
            "args": arguments.get("args"),
            "result": result.get("result"),
            "latency_ms": result.get("latency_ms"),
            "engine_used": result.get("engine_used"),
            "success": True,
        },
        indent=2,
    )
