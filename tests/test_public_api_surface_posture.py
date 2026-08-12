"""The unauthenticated HTTP surface, pinned endpoint by endpoint.

Measured against the live host on 2026-07-31: 69 keyless GET probes, 55 of which returned 401. Of the
handful that answered, some were public BY DESIGN (a load balancer with no credential has to be able
to probe liveness; an MCP client lists tools before sign-in) and some were public BY OMISSION — most
of all `apps/api_server/routers/engines.py`, which had no `Depends` anywhere in the file, so FastAPI
derived "no security" for the whole engine catalogue including its commercial tier grouping.

Both halves regress silently: adding a route without a dependency quietly widens the surface, and
adding a dependency to a probe endpoint quietly breaks deployment (Fly cycles machines whose health
check 401s). So this file asserts BOTH directions — what must be 401, and what must stay 200 — at the
route level and again at the OpenAPI level, since the published spec is what customers and Swagger UI
read.
"""

from __future__ import annotations

import pytest

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_redis
from apps.runtime_manifest import runtime_version
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]

# Reachable with no credential BY DESIGN. Each entry names the pre-auth consumer that makes gating it
# a breaking change, so a future reader can weigh the trade instead of guessing.
PUBLIC_PATHS = {
    # Fly [[http_service.checks]], both Dockerfile HEALTHCHECKs, compose, install.sh, status.sh.
    "/v1/health",
    # Four integration tests fetch it with auth=False; installers print it.
    "/v1/version",
    # The declared discovery entry point (advertised in the signed runtime manifest as public).
    "/v1/meta/contract",
    # Published promise: "Always available, no auth required" — pre-sign-in tools/list is normal MCP.
    "/mcp/tools",
    # Counts only (no surface): algenta.ai renders its catalog counters from it (lib/engine-stats.ts).
    "/v1/runtime/library-stats",
}

# Public by OMISSION, now gated. Zero pre-auth consumers in the tree; both in-repo callers send a key.
GATED_PATHS = {
    "/v1/engines": "GET",
    "/v1/engines/tiers": "GET",
    # Gated with the collection or the gate is bypassed by enumerating the slugs it just listed.
    "/v1/engines/decision": "GET",
}

# The deprecated MCP HTTP+SSE lane: the streamable mount's tools/call challenge never applied to it,
# so it could execute tools for a caller with no credential.
LEGACY_MCP = {"/mcp/sse": "GET", "/mcp/messages": "POST"}


@pytest.fixture
def _redis_stub():
    """get_current_org resolves Redis before it can reject; a 401 test must not need a live server."""
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        yield
    finally:
        app.dependency_overrides.clear()


# ── What must require a key ────────────────────────────────────────────────────


@pytest.mark.parametrize("path", sorted(GATED_PATHS))
def test_gated_paths_reject_an_unauthenticated_caller(path: str, _redis_stub) -> None:
    with SyncASGIClient(app) as client:
        response = client.get(path)
    assert response.status_code == 401, f"{path} answered {response.status_code} with no key"
    # The envelope shape is a client contract; changing it breaks every SDK's error parsing.
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("path,method", sorted(LEGACY_MCP.items()))
def test_legacy_mcp_transport_rejects_an_unauthenticated_caller(path: str, method: str) -> None:
    """An unauthenticated GET /mcp/sse used to hand out a session id, and the paired
    POST /mcp/messages?session_id=... then ran tools with the SERVER's ambient key."""
    with SyncASGIClient(app) as client:
        response = (
            client.get(path)
            if method == "GET"
            else client.post(path, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call"})
        )
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
    payload = response.json()
    assert payload["error"]["code"] == "authentication_required"
    assert "WWW-Authenticate" in response.headers


# ── What must stay open ────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", sorted(PUBLIC_PATHS))
def test_public_paths_still_answer_without_a_key(path: str) -> None:
    with SyncASGIClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200, (
        f"{path} now needs a key; a keyless pre-auth consumer (load balancer probe, installer, "
        f"MCP tools/list, docs generator) depends on it"
    )


def test_runtime_manifest_is_never_credential_gated() -> None:
    """The signed manifest advertises ITSELF as public (`_PUBLIC_ENDPOINTS`, enforced by a manifest
    validator and two tests), so gating it would mean changing the signed contract.

    Asserted as "not an auth rejection" rather than 200 on purpose: building the manifest reads
    on-disk proof/benchmark artifacts, so a stale artifact makes this route 500 for reasons that have
    nothing to do with the auth posture this file is pinning.
    """
    with SyncASGIClient(app, raise_app_exceptions=False) as client:
        response = client.get("/v1/runtime/manifest")
    assert response.status_code not in (401, 403), "the runtime manifest must stay reachable"


def test_health_stays_minimal() -> None:
    """The liveness probe must not grow into an information surface."""
    with SyncASGIClient(app) as client:
        payload = client.get("/v1/health").json()
    assert set(payload) == {"status", "timestamp"}
    assert payload["status"] == "ok"


def test_version_reports_the_runtime_build_not_a_stale_literal() -> None:
    """`engine_version` was the module literal "0.1.0" while the same process's runtime manifest
    reported a version five years newer. A public build identifier that disagrees with the runtime is
    worse than none, so it is now derived from the manifest."""
    with SyncASGIClient(app) as client:
        payload = client.get("/v1/version").json()
    assert payload["engine_version"] == runtime_version()
    assert payload["engine_version"] != "0.1.0"
    # `environment` is asserted by two scripts and a test and is typed in the TS SDK — removing it is a
    # breaking change across four surfaces to hide what the hostname already says.
    assert set(payload) == {"api_version", "engine_version", "environment"}


# ── The published spec must say the same thing ─────────────────────────────────


def test_openapi_marks_the_gated_paths_protected() -> None:
    schema = app.openapi()
    for path in [*GATED_PATHS, *LEGACY_MCP]:
        spec_path = "/v1/engines/{slug}" if path == "/v1/engines/decision" else path
        operations = schema["paths"][spec_path]
        for method, operation in operations.items():
            assert operation.get("security") == PROTECTED_OPENAPI_SECURITY, (
                f"{method.upper()} {spec_path} is advertised as unauthenticated in the spec"
            )


def test_openapi_keeps_the_public_paths_unauthenticated() -> None:
    schema = app.openapi()
    for path in {*PUBLIC_PATHS, "/v1/runtime/manifest"}:
        for method, operation in schema["paths"][path].items():
            assert operation.get("security") is None, (
                f"{method.upper()} {path} gained spec-level security; keyless probes will break"
            )


def test_the_canonical_spec_file_agrees_with_the_live_app() -> None:
    """`schemas/openapi/openapi.yaml` is what the docs site and Swagger UI publish. It is generated by
    an owner-run `make openapi` against a live process, so it drifts silently — pin the security of the
    routes this change touched rather than letting the published spec keep advertising them as open."""
    import yaml

    spec = yaml.safe_load(open("schemas/openapi/openapi.yaml", encoding="utf-8"))
    for spec_path in [
        "/v1/engines",
        "/v1/engines/tiers",
        "/v1/engines/{slug}",
        "/mcp/sse",
        "/mcp/messages",
    ]:
        for method, operation in spec["paths"][spec_path].items():
            assert operation.get("security"), f"{method.upper()} {spec_path} is published as open"
    for spec_path in ["/v1/health", "/v1/version", "/v1/meta/contract", "/mcp/tools"]:
        for method, operation in spec["paths"][spec_path].items():
            assert not operation.get("security"), (
                f"{method.upper()} {spec_path} is published as gated"
            )
