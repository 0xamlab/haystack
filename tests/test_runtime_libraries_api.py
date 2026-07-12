from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api_server.config import get_settings
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.services.runtime_library_service import (
    RuntimeLibraryDescriptor,
    RuntimeLibraryExecutionResult,
    RuntimeLibraryHealth,
)


def _reload_api_server_app():
    get_settings.cache_clear()
    if "apps.api_server.main" in sys.modules:
        module = importlib.reload(sys.modules["apps.api_server.main"])
    else:
        module = importlib.import_module("apps.api_server.main")
    return module.app


@pytest.fixture
def runtime_library_api_app_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[bool | None], Any]:
    env_name = "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"

    def load(enabled: bool | None):
        if enabled is None:
            monkeypatch.delenv(env_name, raising=False)
        else:
            monkeypatch.setenv(env_name, "1" if enabled else "0")
        return _reload_api_server_app()

    yield load

    monkeypatch.delenv(env_name, raising=False)
    _reload_api_server_app()


@pytest.mark.anyio
async def test_public_api_can_explicitly_disable_runtime_library_routes(
    runtime_library_api_app_loader,
) -> None:
    app = runtime_library_api_app_loader(False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        list_response = await client.get("/v1/libraries")
        health_response = await client.get("/v1/libraries/health")
        execute_response = await client.post(
            "/v1/libraries/execute",
            json={"module": "ab_testing", "function": "sample_size", "args": {}},
        )
        openapi_response = await client.get("/openapi.json")

    assert list_response.status_code == 404
    assert health_response.status_code == 404
    assert execute_response.status_code == 404
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/v1/libraries" not in paths
    assert "/v1/libraries/health" not in paths
    assert "/v1/libraries/execute" not in paths


@pytest.mark.anyio
async def test_runtime_library_routes_are_enabled_by_default(
    runtime_library_api_app_loader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = runtime_library_api_app_loader(None)

    from apps.api_server.routers import runtime_libraries as runtime_libraries_router

    async def _fake_auth() -> dict[str, str]:
        return {"org_id": "org_runtime_http", "plan": "pro"}

    async def _fake_redis() -> object:
        return object()

    async def _allow_rate_limit(
        *,
        request: object,
        auth: object,
        redis_client: object,
    ) -> None:
        return None

    async def _fake_execute(
        *,
        module: str,
        function: str,
        args: Any = None,
        request_id: str | None = None,
    ) -> RuntimeLibraryExecutionResult:
        return RuntimeLibraryExecutionResult(
            module=module,
            function=function,
            result={"echo": args},
            latency_ms=0.42,
            engine_used="mojo",
            request_id=request_id,
        )

    monkeypatch.setattr(
        runtime_libraries_router,
        "_enforce_runtime_library_rate_limit",
        _allow_rate_limit,
    )
    monkeypatch.setattr(
        runtime_libraries_router,
        "list_public_runtime_library_descriptors",
        lambda query=None: (
            RuntimeLibraryDescriptor(
                name="kv_cache",
                engine="mojo",
                functions=("kv_cache_total_memory", "kv_cache_utilization"),
            ),
            RuntimeLibraryDescriptor(
                name="vector_kernels.table",
                engine="mojo",
                functions=("build_table_json",),
            ),
        ),
    )
    monkeypatch.setattr(
        runtime_libraries_router,
        "get_public_runtime_library_health",
        lambda: RuntimeLibraryHealth(
            status="ok",
            engine="mojo",
            module_count=22,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        runtime_libraries_router,
        "execute_public_runtime_library",
        _fake_execute,
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = _fake_redis

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            list_response = await client.get("/v1/libraries")
            health_response = await client.get("/v1/libraries/health")
            execute_response = await client.post(
                "/v1/libraries/execute",
                json={
                    "module": "kv_cache",
                    "function": "kv_cache_total_memory",
                    "args": [4096.0, 32.0],
                    "request_id": "req_http_rollout_001",
                },
            )
            openapi_response = await client.get("/openapi.json")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json() == {
        "modules": [
            {
                "name": "kv_cache",
                "engine": "mojo",
                "functions": ["kv_cache_total_memory", "kv_cache_utilization"],
            },
            {
                "name": "vector_kernels.table",
                "engine": "mojo",
                "functions": ["build_table_json"],
            },
        ],
        "count": 2,
        "total": 2,
        "page": 1,
        "limit": 50,
        "pages": 1,
    }

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "engine": "mojo",
        "module_count": 22,
        "runtime_available": True,
    }

    assert execute_response.status_code == 200
    assert execute_response.json() == {
        "module": "kv_cache",
        "function": "kv_cache_total_memory",
        "result": {"echo": [4096.0, 32.0]},
        "latency_ms": 0.42,
        "engine_used": "mojo",
        "request_id": "req_http_rollout_001",
    }

    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/v1/libraries" in paths
    assert "/v1/libraries/health" in paths
    assert "/v1/libraries/execute" in paths
