"""MCP tools for the unified customer-agnostic capability plane."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_CAPABILITY_PROVIDERS_SPEC: dict[str, Any] = {
    "name": "list_capability_providers",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the unified capability providers available to the organization — data "
        "sources, MCP servers, skill packs, native tools, and runtime libraries — "
        "with their profiles, auth kinds, supported execution owners, and binding "
        "scopes. Start here to find provider_id and profile_id for "
        "create_capability_binding, then discover_capability_binding to see what a "
        "binding exposes. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_CAPABILITY_BINDINGS_SPEC: dict[str, Any] = {
    "name": "list_capability_bindings",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the capability bindings saved under the caller's organization, "
        "optionally narrowed by provider_id or scope (user, workspace, organization). "
        "A binding pairs a provider profile with credentials/config and is what makes "
        "capabilities executable. Use create_capability_binding to add one, "
        "test_capability_binding to verify one, and list_capabilities to browse what "
        "they expose. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider_id": {
                "type": "string",
                "minLength": 1,
                "description": "Keep only bindings of this provider.",
            },
            "scope": {
                "type": "string",
                "enum": ["user", "workspace", "organization"],
                "description": "Keep only bindings at this scope.",
            },
        },
        "additionalProperties": False,
    },
}

CREATE_CAPABILITY_BINDING_SPEC: dict[str, Any] = {
    "name": "create_capability_binding",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Save one capability binding for a provider/profile pair and return it with "
        "its binding_id. scope (default workspace) decides who can use it, "
        "execution_owner decides where executions run (algenta_managed on the engine, "
        "client_managed in the customer app or adapter path), and config carries the "
        "profile's credentials and options. Find valid provider_id/profile_id pairs "
        "with list_capability_providers, then call discover_capability_binding to "
        "publish the binding's capabilities and test_capability_binding to verify. "
        "Persists the binding."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider_id": {
                "type": "string",
                "minLength": 1,
                "description": "Provider id from list_capability_providers.",
            },
            "profile_id": {
                "type": "string",
                "minLength": 1,
                "description": "Profile id within the provider.",
            },
            "binding_name": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable binding name.",
            },
            "scope": {
                "type": "string",
                "enum": ["user", "workspace", "organization"],
                "description": "Visibility scope; defaults to workspace.",
            },
            "scope_ref": {
                "type": "string",
                "description": "Optional concrete user/workspace id the scope binds to.",
            },
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
                "description": (
                    "Where executions run; defaults to the profile's "
                    "default_execution_owner."
                ),
            },
            "config": {
                "type": "object",
                "description": "Profile credentials and options.",
            },
            "customer_metadata": {
                "type": "object",
                "description": "Optional caller metadata stored with the binding.",
            },
        },
        "required": ["provider_id", "profile_id", "binding_name"],
        "additionalProperties": False,
    },
}

TEST_CAPABILITY_BINDING_SPEC: dict[str, Any] = {
    "name": "test_capability_binding",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Run a health test on one capability binding and return the outcome. Pass "
        "binding_id to test a saved binding, or a full inline definition "
        "(provider_id, profile_id, config, ...) to preview-test one that was never "
        "saved — nothing is persisted in the preview form. Use this after "
        "create_capability_binding or update, before routing traffic to the binding."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "binding_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved binding id to test; omit to preview-test inline.",
            },
            "provider_id": {
                "type": "string",
                "minLength": 1,
                "description": "Provider id for the inline preview form.",
            },
            "profile_id": {
                "type": "string",
                "minLength": 1,
                "description": "Profile id for the inline preview form.",
            },
            "scope": {
                "type": "string",
                "enum": ["user", "workspace", "organization"],
                "description": "Scope for the inline preview form.",
            },
            "scope_ref": {
                "type": "string",
                "description": "Scope reference for the inline preview form.",
            },
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
                "description": "Execution owner for the inline preview form.",
            },
            "config": {
                "type": "object",
                "description": "Credentials/options for the inline preview form.",
            },
            "customer_metadata": {
                "type": "object",
                "description": "Metadata for the inline preview form.",
            },
        },
        "additionalProperties": False,
    },
}

DISCOVER_CAPABILITY_BINDING_SPEC: dict[str, Any] = {
    "name": "discover_capability_binding",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Discover the capabilities one binding exposes and return them as catalog "
        "entries. Pass binding_id to discover a saved binding (this publishes or "
        "refreshes its capabilities in the catalog), or a full inline definition to "
        "preview-discover one that was never saved. Call this after "
        "create_capability_binding, then browse the result with list_capabilities."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "binding_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved binding id to discover; omit to preview inline.",
            },
            "provider_id": {
                "type": "string",
                "minLength": 1,
                "description": "Provider id for the inline preview form.",
            },
            "profile_id": {
                "type": "string",
                "minLength": 1,
                "description": "Profile id for the inline preview form.",
            },
            "scope": {
                "type": "string",
                "enum": ["user", "workspace", "organization"],
                "description": "Scope for the inline preview form.",
            },
            "scope_ref": {
                "type": "string",
                "description": "Scope reference for the inline preview form.",
            },
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
                "description": "Execution owner for the inline preview form.",
            },
            "config": {
                "type": "object",
                "description": "Credentials/options for the inline preview form.",
            },
            "customer_metadata": {
                "type": "object",
                "description": "Metadata for the inline preview form.",
            },
        },
        "additionalProperties": False,
    },
}

LIST_CAPABILITIES_SPEC: dict[str, Any] = {
    "name": "list_capabilities",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the unified capability catalog visible to the caller — datasets, MCP "
        "tools, resources and prompts, skills, native tools, and runtime libraries — "
        "with each entry's kind, provider, binding, and execution owner. Filter by "
        "kinds, provider_ids, or binding_ids to narrow the catalog. Use "
        "get_capability for one entry's detail, route_capabilities to pick the best "
        "entry for an objective, and list_skills for the skill subset. Read-only."
    ),
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
                "description": "Keep only these capability kinds.",
            },
            "provider_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keep only capabilities from these providers.",
            },
            "binding_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keep only capabilities from these bindings.",
            },
        },
        "additionalProperties": False,
    },
}

GET_CAPABILITY_SPEC: dict[str, Any] = {
    "name": "get_capability",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch one unified capability catalog entry by capability_id: kind, provider, "
        "binding, execution owner, approval requirement, and tags. "
        "include_instruction=true also returns the skill instruction text. Find "
        "capability ids with list_capabilities or route_capabilities. Read-only; an "
        "unknown id fails with not_found."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "capability_id": {
                "type": "string",
                "minLength": 1,
                "description": "Capability id from list_capabilities or route_capabilities.",
            },
            "include_instruction": {
                "type": "boolean",
                "description": "Also return the instruction text for skill capabilities.",
            },
        },
        "required": ["capability_id"],
        "additionalProperties": False,
    },
}

ROUTE_CAPABILITIES_SPEC: dict[str, Any] = {
    "name": "route_capabilities",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Pick the best unified capability for a natural-language objective and return "
        "the route plan: the selected capability, binding, and kind, the authoritative "
        "execution_owner, whether approval is required, confidence and reason, plus "
        "ordered fallbacks (max_fallbacks, default 3). The optional filters narrow "
        "which catalog entries may be selected. Routing never executes anything — "
        "feed the selected_capability_id to execute_capability. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "objective": {
                "type": "string",
                "minLength": 1,
                "description": "What you want to accomplish, in plain words.",
            },
            "binding_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Restrict candidates to these bindings.",
            },
            "provider_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Restrict candidates to these providers.",
            },
            "kinds": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Restrict candidates to these capability kinds.",
            },
            "execution_owners": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Restrict candidates to these execution owners.",
            },
            "artifact_affinities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Prefer capabilities affine to these artifacts.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Prefer capabilities carrying these tags.",
            },
            "max_fallbacks": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "description": "How many fallback routes to return, 0-10; defaults to 3.",
            },
        },
        "required": ["objective"],
        "additionalProperties": False,
    },
}

EXECUTE_CAPABILITY_SPEC: dict[str, Any] = {
    "name": "execute_capability",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Execute one routed or known algenta_managed capability by capability id and "
        "return the execution receipt. client_managed routes must execute in the "
        "customer app or adapter path — this tool will not run them. If the capability "
        "requires approval (approval_required), this returns a pending plan "
        "(status='approval_required', plus plan_id/plan_hash/nonce) instead of "
        "executing — approval and the final plan_id execution are separate, "
        "credentialed HTTP operations and are NOT available as tools. Route first "
        "with route_capabilities when the right capability is not known."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "capability_id": {
                "type": "string",
                "minLength": 1,
                "description": "Capability id from route_capabilities or list_capabilities.",
            },
            "binding_id": {
                "type": "string",
                "description": "Optional binding id to disambiguate the execution target.",
            },
            "input": {
                "type": "object",
                "description": "Capability-specific execution input.",
            },
            "request_id": {
                "type": "string",
                "description": "Optional caller request id for correlation.",
            },
        },
        "required": ["capability_id"],
        "additionalProperties": False,
    },
}

LIST_SKILLS_SPEC: dict[str, Any] = {
    "name": "list_skills",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the skill capabilities in the unified capability plane — prompt skills "
        "enabled for the caller's organization with their names, bindings, and "
        "execution owners. This is list_capabilities narrowed to kind=skill. Use "
        "enable_skill to add one and disable_skill to remove one. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

ENABLE_SKILL_SPEC: dict[str, Any] = {
    "name": "enable_skill",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Enable one prompt skill as a first-class capability binding and return its "
        "discovered catalog entry. The skill's instruction text becomes an "
        "instruction_only capability under the caller's user scope, selectable by "
        "route_capabilities. Persists a new binding; remove it with disable_skill. "
        "Use list_skills to see what is already enabled."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "minLength": 1,
                "description": "Skill name; also names the new binding.",
            },
            "instruction": {
                "type": "string",
                "minLength": 1,
                "description": "Instruction text the skill injects when selected.",
            },
            "description": {
                "type": "string",
                "description": "Optional human-readable summary of the skill.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional routing tags.",
            },
            "artifact_affinities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional artifact affinities for routing.",
            },
            "execution_owner": {
                "type": "string",
                "enum": ["algenta_managed", "client_managed"],
                "description": "Where executions run; defaults to client_managed.",
            },
        },
        "required": ["skill_name", "instruction"],
        "additionalProperties": False,
    },
}

DISABLE_SKILL_SPEC: dict[str, Any] = {
    "name": "disable_skill",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Disable one skill by deleting its capability binding (find binding ids with "
        "list_skills or list_capability_bindings). The skill immediately stops "
        "appearing in the capability catalog and can no longer be routed or "
        "executed; the deletion is permanent. Returns binding_id with disabled: "
        "true."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "binding_id": {
                "type": "string",
                "minLength": 1,
                "description": "Skill binding id from list_skills.",
            },
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
