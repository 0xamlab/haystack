from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

from apps.api_server.config import get_settings
from apps.api_server.middleware.deployment_router import (
    DeploymentEndpointLookupError,
    DeploymentRoutingMiddleware,
)


def _request(path: str = "/v1/simulate") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 54321),
        "server": ("testserver", 80),
        "app": SimpleNamespace(state=SimpleNamespace(redis=None)),
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)
    request.state.org_id = "org-123"
    request.state.request_id = "req-123"
    return request


def _response_json(response: Response) -> dict[str, object]:
    return json.loads(response.body.decode("utf-8"))


@pytest.mark.anyio
async def test_deployment_router_uses_shared_pool_only_when_no_dedicated_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    get_settings.cache_clear()

    middleware = DeploymentRoutingMiddleware(app=lambda scope, receive, send: None)

    async def _no_endpoint(*_args) -> str | None:
        return None

    monkeypatch.setattr(middleware, "_get_deployment_endpoint", _no_endpoint)

    called = {"count": 0}

    async def call_next(_request: Request) -> Response:
        called["count"] += 1
        return Response("shared-pool", status_code=200)

    response = await middleware.dispatch(_request(), call_next)

    assert response.status_code == 200
    assert called["count"] == 1
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_deployment_router_fails_closed_when_endpoint_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    get_settings.cache_clear()

    middleware = DeploymentRoutingMiddleware(app=lambda scope, receive, send: None)

    async def _raise_lookup_error(*_args) -> str | None:
        raise DeploymentEndpointLookupError("lookup failed")

    monkeypatch.setattr(middleware, "_get_deployment_endpoint", _raise_lookup_error)

    called = {"count": 0}

    async def call_next(_request: Request) -> Response:
        called["count"] += 1
        return Response("shared-pool", status_code=200)

    response = await middleware.dispatch(_request(), call_next)

    assert response.status_code == 503
    assert called["count"] == 0
    assert _response_json(response) == {
        "error": {
            "code": "deployment_endpoint_lookup_failed",
            "message": (
                "Dedicated deployment routing is temporarily unavailable. "
                "The request was not rerouted to the shared pool."
            ),
            "details": {"reason": "endpoint_lookup_failed"},
        }
    }
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_deployment_router_fails_closed_when_proxy_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    get_settings.cache_clear()

    middleware = DeploymentRoutingMiddleware(app=lambda scope, receive, send: None)

    async def _endpoint(*_args) -> str | None:
        return "https://data-plane.customer.internal"

    async def _noop_record(*_args, **_kwargs) -> None:
        return None

    async def _raise_proxy_error(*_args, **_kwargs) -> Response:
        raise RuntimeError("proxy offline")

    monkeypatch.setattr(middleware, "_get_deployment_endpoint", _endpoint)
    monkeypatch.setattr(
        "apps.api_server.middleware.deployment_router.record_service_egress_event",
        _noop_record,
    )
    monkeypatch.setattr(middleware, "_proxy_request", _raise_proxy_error)

    called = {"count": 0}

    async def call_next(_request: Request) -> Response:
        called["count"] += 1
        return Response("shared-pool", status_code=200)

    response = await middleware.dispatch(_request(), call_next)

    assert response.status_code == 503
    assert called["count"] == 0
    assert _response_json(response) == {
        "error": {
            "code": "deployment_proxy_unavailable",
            "message": (
                "Dedicated deployment is temporarily unavailable. "
                "The request was not rerouted to the shared pool."
            ),
            "details": {"reason": "proxy_request_failed"},
        }
    }
    get_settings.cache_clear()
