"""The reduced agent-facing Decision API spec (Workstream K1).

Asserts the filter that Foundry / the Copilot plugin register against exposes ONLY the coarse
decision operations and structurally omits approval-mutation, execution, and admin routes.
"""

from __future__ import annotations

from apps.api_server.routers.decision_agent_spec import (
    AGENT_OPERATIONS,
    AGENT_SPEC_VERSION,
    build_decision_agent_spec,
)

# A synthetic "full" application spec: the real decision paths + privileged + admin routes and a
# components block with a schema only the (excluded) approve path references.
FULL_SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Algenta API", "version": "1.0.0"},
    "paths": {
        "/v1/decision-cases": {
            "post": {"operationId": "create_decision_case", "responses": {},
                     "requestBody": {"content": {"application/json": {"schema": {
                         "$ref": "#/components/schemas/CreateDecisionCaseRequest"}}}}},
        },
        "/v1/decision-cases/{case_id}": {
            "put": {"operationId": "update_decision_case", "responses": {}},
            "get": {"operationId": "get_decision_case", "responses": {}},
        },
        "/v1/decision-cases/{case_id}/analysis-runs": {
            "post": {"operationId": "start_analysis_run", "responses": {}},
        },
        "/v1/decision-cases/{case_id}/refresh": {
            "post": {"operationId": "refresh_decision", "responses": {}},
        },
        "/v1/analysis-runs/{run_id}": {"get": {"operationId": "get_analysis_run", "responses": {}}},
        "/v1/analysis-runs/{run_id}/result": {
            "get": {"operationId": "get_analysis_result", "responses": {}},
        },
        "/v1/analysis-runs/{run_id}/evidence": {
            "get": {"operationId": "inspect_evidence", "responses": {}},
        },
        "/v1/analysis-runs/{run_id}/action-plans": {
            "post": {"operationId": "propose_action_plan", "responses": {}},
        },
        "/v1/decision-cases/{case_id}/outcomes": {
            "post": {"operationId": "record_outcome", "responses": {}},
        },
        # ---- privileged / admin routes that MUST NOT appear in the agent spec ----
        "/v1/decision-plans/{plan_id}/approve": {
            "post": {"operationId": "approve_plan", "responses": {},
                     "requestBody": {"content": {"application/json": {"schema": {
                         "$ref": "#/components/schemas/ApproveRequest"}}}}},
        },
        "/v1/decision-plans/{plan_id}/execute": {
            "post": {"operationId": "execute_plan", "responses": {}},
        },
        "/v1/admin/config": {"get": {"operationId": "admin_config", "responses": {}}},
    },
    "components": {
        "schemas": {
            "CreateDecisionCaseRequest": {"type": "object",
                                          "properties": {"pack": {"$ref": "#/components/schemas/PackRef"}}},
            "PackRef": {"type": "string"},
            "ApproveRequest": {"type": "object"},      # referenced only by the excluded approve path
            "UnusedSchema": {"type": "object"},        # referenced by nothing
        },
        "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
    },
}


def _spec():
    return build_decision_agent_spec(FULL_SPEC, "https://gw.example.com")


def test_only_coarse_operations_are_exposed() -> None:
    spec = _spec()
    got = {(m, p) for p, methods in spec["paths"].items() for m in methods}
    assert got == set(AGENT_OPERATIONS), "agent spec paths must equal the allowlist exactly"


def test_operation_ids_are_the_coarse_names() -> None:
    spec = _spec()
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            assert op["operationId"] == AGENT_OPERATIONS[(method, path)]
    # e.g. the raw router name is rewritten to the stable agent name
    assert spec["paths"]["/v1/decision-cases"]["post"]["operationId"] == "create_or_update_decision"


def test_approval_execution_and_admin_are_absent() -> None:
    spec = _spec()
    dumped = str(spec["paths"])
    assert "/approve" not in dumped
    assert "/execute" not in dumped
    assert "/admin/" not in dumped
    for path in spec["paths"]:
        assert "approve" not in path and "execute" not in path


def test_components_are_pruned_to_referenced_only() -> None:
    spec = _spec()
    schemas = spec["components"]["schemas"]
    assert "CreateDecisionCaseRequest" in schemas
    assert "PackRef" in schemas  # pulled in transitively
    assert "ApproveRequest" not in schemas  # only the excluded approve path referenced it
    assert "UnusedSchema" not in schemas
    # security schemes are preserved
    assert "bearer" in spec["components"]["securitySchemes"]


def test_versioned_and_server_pinned() -> None:
    spec = _spec()
    assert spec["info"]["version"] == AGENT_SPEC_VERSION
    assert spec["servers"] == [{"url": "https://gw.example.com"}]
    assert spec["openapi"].startswith("3.")


def _req(headers: dict, scheme: str = "http", host: str = "gateway.algenta.ai"):
    from starlette.requests import Request

    hdrs = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({
        "type": "http", "method": "GET", "path": "/openapi/decision-agent.json",
        "query_string": b"", "headers": hdrs, "scheme": scheme,
        "server": (host, 443 if scheme == "https" else 80), "client": ("1.2.3.4", 0),
    })


def test_public_base_url_honors_forwarded_proto_and_never_downgrades() -> None:
    # The served spec's `servers` URL must be https so Foundry/Copilot/the connector don't call http.
    from apps.api_server.routers.decision_agent_spec import _public_base_url

    # Behind a TLS-terminating proxy: internal http + x-forwarded-proto=https -> https.
    assert _public_base_url(_req({"host": "gateway.algenta.ai", "x-forwarded-proto": "https"})) == "https://gateway.algenta.ai"
    # No forwarded header but a public host on http -> upgraded to https (never advertise cleartext).
    assert _public_base_url(_req({"host": "gateway.algenta.ai"})) == "https://gateway.algenta.ai"
    # x-forwarded-host is honored.
    assert _public_base_url(_req({"host": "internal:8000", "x-forwarded-proto": "https", "x-forwarded-host": "gateway.algenta.ai"})) == "https://gateway.algenta.ai"
    # Localhost dev stays http.
    assert _public_base_url(_req({"host": "localhost:8000"})) == "http://localhost:8000"
