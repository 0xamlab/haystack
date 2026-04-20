from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from apps.api_server.middleware.request_id import RequestIDMiddleware
from apps.api_server.middleware.response_contract import ResponseContractMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(ResponseContractMiddleware)

    @app.get("/v1/ping")
    async def ping(request: Request) -> dict[str, bool]:
        request.state.mojo_ms = 7
        request.state.rate_limit_limit = 60
        request.state.rate_limit_remaining = 41
        return {"ok": True}

    @app.get("/v1/fail")
    async def fail(request: Request) -> dict[str, bool]:
        request.state.rate_limit_limit = 60
        request.state.rate_limit_remaining = 0
        raise HTTPException(
            status_code=429,
            detail={"error": {"code": "rate_limit_exceeded", "message": "slow down"}},
            headers={"Retry-After": "60"},
        )

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_v1_success_responses_include_observability_headers() -> None:
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/v1/ping")

    assert response.status_code == 200
    assert "X-Execution-Ms" in response.headers
    assert response.headers["X-Mojo-Ms"] == "7"
    assert response.headers["X-RateLimit-Limit"] == "60"
    assert response.headers["X-RateLimit-Remaining"] == "41"
    assert "X-Request-Id" in response.headers


def test_v1_error_responses_include_rate_limit_and_execution_headers() -> None:
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/v1/fail")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.headers["X-RateLimit-Limit"] == "60"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "X-Execution-Ms" in response.headers
    assert response.headers["X-Mojo-Ms"] == "0"


def test_non_v1_responses_do_not_get_contract_headers() -> None:
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert "X-Execution-Ms" not in response.headers
    assert "X-Mojo-Ms" not in response.headers
