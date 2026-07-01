"""Control-plane role (P4a) — ALGENTA_SERVICE_ROLE=control_plane builds an engine-free app.

Guarantees: it mounts ONLY the control-plane surfaces (no engine routers / Mojo / /mcp), engine
paths 404 (not 401 — genuinely not mounted), the full app is unchanged + a strict superset, and
— the top risk — building the control-plane app imports NO engine modules (subprocess check).
"""

from __future__ import annotations

import os
import subprocess
import sys

from fastapi.testclient import TestClient

from apps.api_server.app_support import create_app
from apps.api_server.control_plane import build_control_plane_app

# Engine surfaces that must NEVER appear on the control plane.
_ENGINE_PREFIXES = (
    "/v1/simulate",
    "/v1/recommend",
    "/v1/llm",
    "/v1/agent-runs",
    "/v1/whatif",
    "/v1/query",
    "/v1/data",
    "/v1/map",
    "/v1/ingest",
    "/v1/sources",
    "/v1/datasets",
    "/v1/products",
    "/v1/runs",
    "/v1/export",
    "/v1/stream",
    "/v1/engines",
    "/v1/connectors",
    "/v1/repositories",
    "/v1/deployments",
    "/v1/decisions",
    "/v1/triggers",
    "/v1/calibration",
    "/v1/execution",
    "/v1/logs",
    "/v1/playground",
    "/v1/capabilities",
    "/v1/infrastructure",
    "/v1/libraries",
    "/mcp",
)


def _paths(app) -> set[str]:
    return {r.path for r in app.routes if hasattr(r, "path")}


def test_control_plane_mounts_no_engine_paths() -> None:
    cp = _paths(build_control_plane_app())
    leaked = sorted(p for p in cp for pre in _ENGINE_PREFIXES if p.startswith(pre))
    assert not leaked, f"engine paths leaked onto the control plane: {leaked}"


def test_control_plane_has_required_surfaces() -> None:
    cp = _paths(build_control_plane_app())
    for required in (
        "/v1/health",  # liveness (Fly healthcheck) — from meta router
        "/v1/health/ready",
        "/metrics",
        "/.well-known/jwks.json",  # license verification (B1)
        "/v1/license/revocations",  # CRL (D1)
        "/v1/control-plane/meta",
        "/v1/device/register",
        "/v1/billing/webhook",
        "/oauth/device/code",  # RFC 8628 CLI device-login (telys login)
        "/oauth/device/token",
        "/oauth/device/approve",
        "/v1/runtime/authorize",  # self-service runtime-download gate (packages.telys.ai)
    ):
        assert required in cp, f"control plane missing required surface: {required}"


def test_full_app_unchanged_and_superset() -> None:
    from apps.api_server.main import app as full_app

    full_paths = _paths(full_app)
    cp_paths = _paths(build_control_plane_app())
    # create_app('full') and the default (ALGENTA_SERVICE_ROLE unset → full) ARE the full app.
    assert _paths(create_app("full")) == full_paths
    assert _paths(create_app()) == full_paths
    # The control plane reuses the full app's routers — every surface EXCEPT its own role marker
    # is shared (it introduces no novel routes), and it is strictly smaller than the full app.
    cp_only = {"/v1/control-plane/meta"}  # the role marker is deliberately control-plane-only
    assert (cp_paths - cp_only) <= full_paths
    assert cp_paths < (full_paths | cp_only)
    # the engine lives only on the full app.
    assert any(p.startswith("/v1/simulate") for p in full_paths)


def test_engine_paths_404_not_401_on_control_plane() -> None:
    # 404 = route not mounted (correct). 401/403 would mean mounted-but-auth-gated (a leak).
    with TestClient(build_control_plane_app()) as client:
        assert client.post("/v1/simulate", json={}).status_code == 404
        assert client.get("/mcp/tools").status_code == 404
        assert client.get("/v1/repositories").status_code == 404
        # a control-plane surface IS reachable (proves the app is serving, not blanket-404).
        assert client.get("/v1/control-plane/meta").status_code == 200
        assert client.get("/.well-known/jwks.json").status_code == 200


def test_control_plane_normalizes_errors() -> None:
    # The control plane registers the same {"error": {...}} normalizers as the full app: an
    # unauthenticated authed route returns the normalized contract (top-level "error"), not
    # FastAPI's default {"detail": ...} — proving register_exception_handlers ran.
    with TestClient(build_control_plane_app()) as client:
        resp = client.post("/v1/device/register", json={"device": {"device_id": "x" * 16}})
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body and "code" in body["error"]


def test_control_plane_imports_no_engine_modules() -> None:
    """Top risk: building the control-plane app must not transitively import engine code."""
    code = (
        "import sys;"
        "from apps.api_server.control_plane import build_control_plane_app;"
        "build_control_plane_app();"
        "bad=[m for m in ("
        "'apps.api_server.compute.mojo_pool',"
        "'apps.api_server.routers.simulate',"
        "'apps.api_server.routers.query',"
        "'apps.api_server.routers.repositories',"
        "'apps.api_server.services.simulation_service',"
        "'apps.api_server.services.source_registry',"
        "'apps.api_server.main'"
        ") if m in sys.modules];"
        "print('LEAK:'+repr(bad) if bad else 'CLEAN')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "ALGENTA_SERVICE_ROLE": "control_plane"},
        timeout=120,
    )
    assert "CLEAN" in result.stdout, f"engine leak / error:\nSTDOUT={result.stdout}\nSTDERR={result.stderr}"
