"""Reduced, agent-facing OpenAPI for the Decision Service (Workstream K1).

Azure AI Foundry tools and the Microsoft 365 Copilot API-plugin register against a NARROW,
versioned Decision API contract — the coarse decision operations only. This route derives that
spec from the live application OpenAPI (so request/response schemas can never drift from the real
API) and returns ONLY an allowlist of agent-safe operations.

What is deliberately ABSENT (an agent has no operation to call them):
  * approval mutation      — POST /v1/decision-plans/{id}/approve
  * plan execution         — POST /v1/decision-plans/{id}/execute
  * admin / engine primitives, workspace selection, connector-credential operations

Approval and execution are separate, credentialed HUMAN actions. Keeping them out of the
agent-facing spec is defense-in-depth on top of the role checks the endpoints already enforce.

Served at:  GET /openapi/decision-agent.json   (point Foundry / the Copilot plugin here)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Decision Agent"])

# The agent-facing contract version. Bump when the coarse operation set changes shape — external
# tool registrations pin to this, so it is intentionally decoupled from the app's own version.
AGENT_SPEC_VERSION = "2024-11-01"

# (HTTP method, path template) -> coarse agent operationId. Anything NOT in this map is excluded
# from the agent spec entirely. This is the allowlist boundary.
AGENT_OPERATIONS: dict[tuple[str, str], str] = {
    ("post", "/v1/decision-cases"): "create_or_update_decision",
    ("put", "/v1/decision-cases/{case_id}"): "reframe_decision",
    ("get", "/v1/decision-cases/{case_id}"): "get_decision_case",
    ("post", "/v1/decision-cases/{case_id}/analysis-runs"): "run_decision_analysis",
    ("post", "/v1/decision-cases/{case_id}/refresh"): "refresh_decision",
    ("get", "/v1/analysis-runs/{run_id}"): "get_decision_run_status",
    ("get", "/v1/analysis-runs/{run_id}/result"): "get_decision_result",
    ("get", "/v1/analysis-runs/{run_id}/evidence"): "inspect_decision_evidence",
    ("post", "/v1/analysis-runs/{run_id}/action-plans"): "propose_action_plan",
    ("post", "/v1/decision-cases/{case_id}/outcomes"): "record_decision_outcome",
}

# Substrings that must never appear in an agent-facing path (asserted at build time — a new
# privileged route can't silently leak into the spec just because someone forgets the allowlist).
_FORBIDDEN_PATH_SUBSTRINGS = ("/approve", "/execute")


def _collect_schema_refs(node: Any, acc: set[str]) -> None:
    """Walk an OpenAPI fragment collecting referenced component-schema names."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            acc.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _collect_schema_refs(value, acc)
    elif isinstance(node, list):
        for value in node:
            _collect_schema_refs(value, acc)


def _prune_components(components: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    """Keep only the component schemas the included paths reference (transitively)."""
    schemas: dict[str, Any] = components.get("schemas", {}) or {}
    wanted: set[str] = set()
    _collect_schema_refs(paths, wanted)
    # transitive closure over $refs between schemas
    changed = True
    while changed:
        changed = False
        for name in list(wanted):
            sub: set[str] = set()
            _collect_schema_refs(schemas.get(name, {}), sub)
            fresh = sub - wanted
            if fresh:
                wanted |= fresh
                changed = True
    pruned: dict[str, Any] = {"schemas": {k: v for k, v in schemas.items() if k in wanted}}
    if "securitySchemes" in components:
        pruned["securitySchemes"] = components["securitySchemes"]
    return pruned


def build_decision_agent_spec(full: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Derive the reduced, agent-facing OpenAPI from the full application spec.

    Pure function (no app/request state) so it is trivially unit-testable.
    """
    included: dict[str, Any] = {}
    for path, methods in (full.get("paths") or {}).items():
        if any(bad in path for bad in _FORBIDDEN_PATH_SUBSTRINGS):
            continue  # belt-and-braces: never emit a privileged path
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            op_id = AGENT_OPERATIONS.get((method.lower(), path))
            if op_id is None:
                continue
            op = dict(operation)
            op["operationId"] = op_id
            included.setdefault(path, {})[method] = op

    spec: dict[str, Any] = {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "Algenta Decision Agent API",
            "description": (
                "Coarse, governed decision operations for AI agents (Azure AI Foundry, "
                "Microsoft 365 Copilot). Prefer run_decision_analysis — it internally runs "
                "evidence gathering, scenarios, simulation, optimization and sensitivity, and "
                "produces a recommendation with its explanation. Approval and execution are NOT "
                "available here: they are separate, credentialed human actions."
            ),
            "version": AGENT_SPEC_VERSION,
        },
        "servers": [{"url": base_url}],
        "paths": included,
        "components": _prune_components(full.get("components", {}) or {}, included),
    }
    return spec


@router.get("/openapi/decision-agent.json", include_in_schema=False)
async def decision_agent_openapi(request: Request) -> JSONResponse:
    """Serve the reduced agent-facing Decision API spec (Foundry / Copilot register here)."""
    full = request.app.openapi()
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(build_decision_agent_spec(full, base_url))
