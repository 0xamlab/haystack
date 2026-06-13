"""MCP tools for the unified customer-agnostic capability plane."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_CAPABILITY_PROVIDERS_SPEC: dict[str, Any] = {
    "name": "list_capability_providers",
    "description": "List unified capability providers across data, MCP, skills, native tools, and runtime libraries.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_CAPABILITY_BINDINGS_SPEC: dict[str, Any] = {
    "name": "list_capability_bindings",
    "description": "List capability bindings for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider_id": {"type": "string", "minLength": 1},
            "scope": {"type": "string", "enum": ["user", "workspace", "organization"]},
        },
        "additionalProperties": False,
    },
}

CREATE_CAPABILITY_BINDING_SPEC: dict[str, Any] = {
    "name": "create_capability_binding",
    "description": "Create one capability binding for a provider/profile pair.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider_id": {"type": "string", "minLength": 1},
            "profile_id": {"type": "string", "minLength": 1},
            "binding_name": {"type": "string", "minLength": 1},
            "scope": {"type": "string", "enum": ["user", "workspace", "organization"]},
            "scope_ref": {"type": "string"},
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
            },
            "config": {"type": "object"},
            "customer_metadata": {"type": "object"},
        },
        "required": ["provider_id", "profile_id", "binding_name"],
        "additionalProperties": False,
    },
}

TEST_CAPABILITY_BINDING_SPEC: dict[str, Any] = {
    "name": "test_capability_binding",
    "description": "Test a saved capability binding or preview-test an unsaved one.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "binding_id": {"type": "string", "minLength": 1},
            "provider_id": {"type": "string", "minLength": 1},
            "profile_id": {"type": "string", "minLength": 1},
            "scope": {"type": "string", "enum": ["user", "workspace", "organization"]},
            "scope_ref": {"type": "string"},
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
            },
            "config": {"type": "object"},
            "customer_metadata": {"type": "object"},
        },
        "additionalProperties": False,
    },
}

DISCOVER_CAPABILITY_BINDING_SPEC: dict[str, Any] = {
    "name": "discover_capability_binding",
    "description": "Discover capabilities for a saved capability binding or preview-discover an unsaved one.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "binding_id": {"type": "string", "minLength": 1},
            "provider_id": {"type": "string", "minLength": 1},
            "profile_id": {"type": "string", "minLength": 1},
            "scope": {"type": "string", "enum": ["user", "workspace", "organization"]},
            "scope_ref": {"type": "string"},
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
            },
            "config": {"type": "object"},
            "customer_metadata": {"type": "object"},
        },
        "additionalProperties": False,
    },
}

LIST_CAPABILITIES_SPEC: dict[str, Any] = {
    "name": "list_capabilities",
    "description": "List unified capabilities filtered by kind, provider, or binding.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "kinds": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "dataset",
                        "mcp_tool",
                        "mcp_resource",
                        "mcp_prompt",
                        "skill",
                        "native_tool",
                        "runtime_library",
                    ],
                },
            },
            "provider_ids": {"type": "array", "items": {"type": "string"}},
            "binding_ids": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    },
}

GET_CAPABILITY_SPEC: dict[str, Any] = {
    "name": "get_capability",
    "description": "Get one unified capability by capability id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "capability_id": {"type": "string", "minLength": 1},
            "include_instruction": {"type": "boolean"},
        },
        "required": ["capability_id"],
        "additionalProperties": False,
    },
}

ROUTE_CAPABILITIES_SPEC: dict[str, Any] = {
    "name": "route_capabilities",
    "description": "Route an objective to the best unified capability with fallbacks and an authoritative execution_owner.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "objective": {"type": "string", "minLength": 1},
            "binding_ids": {"type": "array", "items": {"type": "string"}},
            "provider_ids": {"type": "array", "items": {"type": "string"}},
            "kinds": {"type": "array", "items": {"type": "string"}},
            "execution_owners": {"type": "array", "items": {"type": "string"}},
            "artifact_affinities": {"type": "array", "items": {"type": "string"}},
            "tags": {"type": "array", "items": {"type": "string"}},
            "max_fallbacks": {"type": "integer", "minimum": 0, "maximum": 10},
        },
        "required": ["objective"],
        "additionalProperties": False,
    },
}

EXECUTE_CAPABILITY_SPEC: dict[str, Any] = {
    "name": "execute_capability",
    "description": "Execute one routed or known algenta_managed capability by capability id. client_managed routes must execute in the customer app or adapter path.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "capability_id": {"type": "string", "minLength": 1},
            "binding_id": {"type": "string"},
            "input": {"type": "object"},
            "request_id": {"type": "string"},
        },
        "required": ["capability_id"],
        "additionalProperties": False,
    },
}

LIST_SKILLS_SPEC: dict[str, Any] = {
    "name": "list_skills",
    "description": "List skill capabilities from the unified capability plane.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

ENABLE_SKILL_SPEC: dict[str, Any] = {
    "name": "enable_skill",
    "description": "Enable one prompt-skill as a first-class capability binding.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "minLength": 1},
            "instruction": {"type": "string", "minLength": 1},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "artifact_affinities": {"type": "array", "items": {"type": "string"}},
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
            },
        },
        "required": ["skill_name", "instruction"],
        "additionalProperties": False,
    },
}

DISABLE_SKILL_SPEC: dict[str, Any] = {
    "name": "disable_skill",
    "description": "Disable one skill binding by binding id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "binding_id": {"type": "string", "minLength": 1},
        },
        "required": ["binding_id"],
        "additionalProperties": False,
    },
}


def _query_params(arguments: dict[str, Any], field_name: str) -> list[tuple[str, str]]:
    value = arguments.get(field_name)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field_name} must be an array of non-empty strings.")
    return [(field_name, item) for item in value]


def _json_response(payload: Any) -> str:
    return json.dumps(payload, indent=2)


async def list_capability_providers_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_capability_providers does not accept arguments.")
    return _json_response(await api("GET", "/v1/capability-providers"))


async def list_capability_bindings_handler(arguments: dict[str, Any]) -> str:
    params: list[tuple[str, str]] = []
    provider_id = arguments.get("provider_id")
    scope = arguments.get("scope")
    if provider_id is not None:
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("provider_id must be a non-empty string.")
        params.append(("provider_id", provider_id.strip()))
    if scope is not None:
        if not isinstance(scope, str) or scope not in {"user", "workspace", "organization"}:
            raise ValueError("scope must be one of user, workspace, or organization.")
        params.append(("scope", scope))
    return _json_response(await api("GET", "/v1/capability-bindings", params=params or None))


async def create_capability_binding_handler(arguments: dict[str, Any]) -> str:
    return _json_response(await api("POST", "/v1/capability-bindings", json=arguments))


async def test_capability_binding_handler(arguments: dict[str, Any]) -> str:
    binding_id = arguments.get("binding_id")
    if binding_id is not None:
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ValueError("binding_id must be a non-empty string.")
        return _json_response(
            await api("POST", f"/v1/capability-bindings/{binding_id.strip()}/test")
        )
    return _json_response(await api("POST", "/v1/capability-bindings/test", json=arguments))


async def discover_capability_binding_handler(arguments: dict[str, Any]) -> str:
    binding_id = arguments.get("binding_id")
    if binding_id is not None:
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ValueError("binding_id must be a non-empty string.")
        return _json_response(
            await api("POST", f"/v1/capability-bindings/{binding_id.strip()}/discover")
        )
    return _json_response(
        await api("POST", "/v1/capability-bindings/discover", json=arguments)
    )


async def list_capabilities_handler(arguments: dict[str, Any]) -> str:
    params = [
        *_query_params(arguments, "kinds"),
        *_query_params(arguments, "provider_ids"),
        *_query_params(arguments, "binding_ids"),
    ]
    return _json_response(await api("GET", "/v1/capabilities", params=params or None))


async def get_capability_handler(arguments: dict[str, Any]) -> str:
    capability_id = arguments.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("capability_id must be a non-empty string.")
    params = None
    if "include_instruction" in arguments:
        include_instruction = arguments.get("include_instruction")
        if not isinstance(include_instruction, bool):
            raise ValueError("include_instruction must be a boolean.")
        params = {"include_instruction": int(include_instruction)}
    return _json_response(
        await api("GET", f"/v1/capabilities/{capability_id.strip()}", params=params)
    )


async def route_capabilities_handler(arguments: dict[str, Any]) -> str:
    return _json_response(await api("POST", "/v1/capabilities/route", json=arguments))


async def execute_capability_handler(arguments: dict[str, Any]) -> str:
    return _json_response(await api("POST", "/v1/capabilities/execute", json=arguments))


async def list_skills_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_skills does not accept arguments.")
    return _json_response(await api("GET", "/v1/capabilities", params=[("kinds", "skill")]))


async def enable_skill_handler(arguments: dict[str, Any]) -> str:
    skill_name = arguments.get("skill_name")
    instruction = arguments.get("instruction")
    if not isinstance(skill_name, str) or not skill_name.strip():
        raise ValueError("skill_name must be a non-empty string.")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("instruction must be a non-empty string.")
    binding = await api(
        "POST",
        "/v1/capability-bindings",
        json={
            "provider_id": "provider.skill_pack.algenta",
            "profile_id": "profile.skill_pack.user",
            "binding_name": skill_name.strip(),
            "scope": "user",
            "execution_owner": arguments.get("execution_owner") or "client_managed",
            "config": {
                "manifest": {
                    "capabilities": [
                        {
                            "capability_id": f"cap.skill.{skill_name.strip().lower().replace(' ', '_')}",
                            "name": skill_name.strip(),
                            "description": arguments.get("description"),
                            "kind": "skill",
                            "implementation_kind": "instruction_only",
                            "execution_owner": arguments.get("execution_owner") or "client_managed",
                            "instruction": instruction,
                            "artifact_affinities": arguments.get("artifact_affinities") or [],
                            "tags": arguments.get("tags") or [],
                            "replayability": "deterministic",
                        }
                    ]
                }
            },
        },
    )
    binding_id = binding.get("binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        raise RuntimeError("Capability-plane enable_skill did not return binding_id.")
    return _json_response(await api("POST", f"/v1/capability-bindings/{binding_id}/discover"))


async def disable_skill_handler(arguments: dict[str, Any]) -> str:
    binding_id = arguments.get("binding_id")
    if not isinstance(binding_id, str) or not binding_id.strip():
        raise ValueError("binding_id must be a non-empty string.")
    await api("DELETE", f"/v1/capability-bindings/{binding_id.strip()}")
    return _json_response({"binding_id": binding_id.strip(), "disabled": True})
