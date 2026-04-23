from __future__ import annotations

import builtins
from typing import Any

from fastapi import FastAPI

from apps.mcp_server.server import create_fastapi_router
from tests._asgi_client import SyncASGIClient


def test_create_fastapi_router_keeps_tools_endpoint_without_mcp_package(
    monkeypatch,
) -> None:
    real_import = builtins.__import__

    def _fake_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name.startswith("mcp"):
            raise ImportError("mcp package not installed")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    router = create_fastapi_router()

    assert router is not None
    app = FastAPI()
    app.include_router(router)

    with SyncASGIClient(app) as client:
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        payload = response.json()
        assert "tools" in payload
        assert payload["tools"]
        sse_response = client.get("/mcp/sse")
        assert sse_response.status_code == 503
        assert sse_response.json()["error"]["code"] == "mcp_transport_unavailable"
