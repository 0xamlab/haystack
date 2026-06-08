from __future__ import annotations

import asyncio
import sys
import types
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.background import BackgroundTasks
from jose import JWTError, jwt

from apps.api_server.compute import mojo_adapter
from apps.api_server.config import get_settings
from apps.api_server.main import app
import apps.api_server.routers.auth as auth_router
import apps.api_server.routers.data_map as data_map_router
import apps.api_server.routers.infrastructure as infrastructure_router
import apps.api_server.routers.playground as playground_router
import apps.api_server.routers.simulate as simulate_router
import apps.api_server.services._persist_helpers as persist_helpers
import apps.api_server.services.auth_service as auth_service
import apps.api_server.services.email_service as email_service
import apps.api_server.services.quota_service as quota_service
import apps.api_server.services.storage_service as storage_service
import apps.api_server.services.stripe_service as stripe_service
import apps.api_server.services.webhook_service as webhook_service
from apps.api_server.schemas.auth import LoginRequest
from apps.api_server.services.public_url_policy import PublicUrlConfigurationError
from apps.api_server.services.storage_service import ResultStorageUnavailableError
from tests._asgi_client import SyncASGIClient


def _refresh_api_server_settings() -> None:
    get_settings.cache_clear()
    app.openapi_schema = None
    app.middleware_stack = None


class _FakeRedis:
    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


class _RunningMojoPool:
    def __init__(self) -> None:
        self.running = True
        self.size = 1

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        return None


class _NotRunningMojoPool(_RunningMojoPool):
    async def start(self) -> None:
        self.running = False


@contextmanager
def _patched_lifespan_dependencies(pool_cls: type[_RunningMojoPool]) -> Iterator[None]:
    with (
        patch("redis.asyncio.from_url", return_value=_FakeRedis()),
        patch("apps.api_server.compute.mojo_pool.MojoWorkerPool", pool_cls),
        patch("apps.api_server.compute.mojo_pool.set_pool", lambda pool: None),
    ):
        yield


class _PersistSimulationStub:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc

    def delay(self, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        if self._exc is not None:
            raise self._exc
        return None


def _install_worker_task_module(
    monkeypatch: pytest.MonkeyPatch,
    persist_stub: _PersistSimulationStub,
) -> None:
    module = types.ModuleType("apps.worker.tasks.simulation_task")
    module.persist_simulation = persist_stub
    monkeypatch.setitem(sys.modules, "apps.worker.tasks.simulation_task", module)


def _auth_context() -> dict[str, object]:
    return {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "plan": "pro",
        "email": "owner@example.com",
    }


class _FailingRedisCounter:
    async def incr(self, key: str) -> int:
        del key
        raise RuntimeError("redis unavailable")

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        del key, ttl_seconds
        return True

    async def get(self, key: str) -> object | None:
        del key
        return None

    async def set(
        self,
        key: str,
        value: int | str,
        *,
        ex: int | None = None,
    ) -> bool:
        del key, value, ex
        return True

    async def aclose(self) -> None:
        return None


def _cors_preflight(client: SyncASGIClient, origin: str):
    return client.request(
        "OPTIONS",
        "/v1/version",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_version_endpoint_tracks_current_environment_without_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("API_ENV", "staging")
        _refresh_api_server_settings()
        with SyncASGIClient(app) as client:
            response = client.get("/v1/version")
        assert response.status_code == 200
        assert response.json()["environment"] == "staging"

        monkeypatch.setenv("API_ENV", "production")
        _refresh_api_server_settings()
        with SyncASGIClient(app) as client:
            response = client.get("/v1/version")
        assert response.status_code == 200
        assert response.json()["environment"] == "production"
    finally:
        _refresh_api_server_settings()


def test_settings_separate_public_and_transport_base_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
        monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://public.customer.example")
        monkeypatch.setenv("ALGENTA_BASE_URL", "https://internal.customer.example")
        _refresh_api_server_settings()

        settings = get_settings()

        assert settings.api_public_base_url == "https://public.customer.example"
        assert settings.api_transport_base_url == "https://internal.customer.example"
    finally:
        _refresh_api_server_settings()


def test_settings_accept_algenta_api_url_as_transport_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
        monkeypatch.delenv("DE_BASE_URL", raising=False)
        monkeypatch.setenv("ALGENTA_API_URL", "https://transport.customer.example")
        _refresh_api_server_settings()

        settings = get_settings()

        assert settings.api_transport_base_url == "https://transport.customer.example"
    finally:
        _refresh_api_server_settings()


def test_infrastructure_route_uses_contract_deployment_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "vpc")
        _refresh_api_server_settings()
        monkeypatch.setattr(
            infrastructure_router,
            "_check_engine_health",
            AsyncMock(return_value=("live", 8.4, "0.3.1", "binary")),
        )

        response = asyncio.run(infrastructure_router.get_infrastructure(auth=_auth_context()))

        assert response.deployment_mode == "vpc"
    finally:
        _refresh_api_server_settings()


def test_lifespan_resyncs_cors_origins_from_current_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("CORS_ORIGINS", "https://alpha.customer.example")
        _refresh_api_server_settings()
        with (
            _patched_lifespan_dependencies(_RunningMojoPool),
            SyncASGIClient(app, manage_lifespan=True) as client,
        ):
            response = _cors_preflight(client, "https://alpha.customer.example")
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://alpha.customer.example"

        monkeypatch.setenv("CORS_ORIGINS", "https://beta.customer.example")
        _refresh_api_server_settings()
        with (
            _patched_lifespan_dependencies(_RunningMojoPool),
            SyncASGIClient(app, manage_lifespan=True) as client,
        ):
            response = _cors_preflight(client, "https://beta.customer.example")
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://beta.customer.example"
    finally:
        _refresh_api_server_settings()


def test_lifespan_honors_current_runtime_fallback_mode_without_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
        _refresh_api_server_settings()
        with (
            _patched_lifespan_dependencies(_NotRunningMojoPool),
            pytest.raises(
                RuntimeError,
                match="runtime fallbacks are denied",
            ),
        ):
            with SyncASGIClient(app, manage_lifespan=True):
                pass
    finally:
        _refresh_api_server_settings()


def test_lifespan_rejects_private_profile_algenta_public_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.setenv("ALGENTA_APP_BASE_URL", "https://app.algenta.ai")
        _refresh_api_server_settings()
        with (
            _patched_lifespan_dependencies(_RunningMojoPool),
            pytest.raises(
                PublicUrlConfigurationError,
                match="ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL must not point to an Algenta-owned host",
            ),
        ):
            with SyncASGIClient(app, manage_lifespan=True):
                pass
    finally:
        _refresh_api_server_settings()


def test_lifespan_rejects_private_profile_algenta_public_api_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.setenv("API_PUBLIC_BASE_URL", "https://api.algenta.ai")
        _refresh_api_server_settings()
        with (
            _patched_lifespan_dependencies(_RunningMojoPool),
            pytest.raises(
                ValueError,
                match="ALGENTA_API_PUBLIC_BASE_URL / API_PUBLIC_BASE_URL must not point to an Algenta-owned host",
            ),
        ):
            with SyncASGIClient(app, manage_lifespan=True):
                pass
    finally:
        _refresh_api_server_settings()


def test_simulate_dispatch_persist_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persist_stub = _PersistSimulationStub(exc=RuntimeError("broker down"))
    _install_worker_task_module(monkeypatch, persist_stub)

    try:
        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
        _refresh_api_server_settings()

        background_tasks = BackgroundTasks()
        with pytest.raises(HTTPException) as exc_info:
            simulate_router._dispatch_persist(
                persist_meta={"run_id": "run_123"},
                auth=_auth_context(),
                client_ip="127.0.0.1",
                background_tasks=background_tasks,
                redis_client=object(),
                request_id="req_123",
            )
        assert exc_info.value.status_code == 503
        assert background_tasks.tasks == []

        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "allow")
        _refresh_api_server_settings()

        background_tasks = BackgroundTasks()
        simulate_router._dispatch_persist(
            persist_meta={"run_id": "run_123"},
            auth=_auth_context(),
            client_ip="127.0.0.1",
            background_tasks=background_tasks,
            redis_client=object(),
            request_id="req_123",
        )
        assert len(background_tasks.tasks) == 1
        assert background_tasks.tasks[0].func is simulate_router._persist_in_process
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_quota_service_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
        _refresh_api_server_settings()
        with pytest.raises(HTTPException) as exc_info:
            await quota_service.check_named_rate_limit(
                org_id=uuid.uuid4(),
                redis_client=_FailingRedisCounter(),
                key_prefix="ratelimit",
                limit_per_minute=5,
            )
        assert exc_info.value.status_code == 503

        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "allow")
        _refresh_api_server_settings()
        await quota_service.check_named_rate_limit(
            org_id=uuid.uuid4(),
            redis_client=_FailingRedisCounter(),
            key_prefix="ratelimit",
            limit_per_minute=5,
        )
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_persist_helpers_honor_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(output_blob_ref=None, result_url=None)

    async def _fake_store_result(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise ResultStorageUnavailableError("storage unavailable")

    monkeypatch.setattr("apps.api_server.services.storage_service.store_result", _fake_store_result)

    try:
        monkeypatch.setenv("RESULT_STORAGE_ENABLED", "true")
        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
        _refresh_api_server_settings()
        with pytest.raises(RuntimeError, match="Result storage backend unavailable"):
            await persist_helpers._persist_result_reference(
                run=run,
                persist_meta={
                    "run_id": str(uuid.uuid4()),
                    "org_id": str(uuid.uuid4()),
                    "envelope_json": {"status": "completed"},
                },
            )

        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "allow")
        _refresh_api_server_settings()
        await persist_helpers._persist_result_reference(
            run=run,
            persist_meta={
                "run_id": str(uuid.uuid4()),
                "org_id": str(uuid.uuid4()),
                "envelope_json": {"status": "completed"},
            },
        )
        assert run.output_blob_ref is None
        assert run.result_url is None
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_mojo_adapter_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_calls = 0

    async def _fake_invoke_python_fallback(payload: dict[str, object]) -> dict[str, object]:
        nonlocal fallback_calls
        fallback_calls += 1
        return {
            "engine_version": "0.1.0-python-fallback",
            "scenarios_run": payload["runs"],
            "summary": {"mean": 123.0},
            "percentiles": {"p5": 1.0, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p95": 5.0},
            "risk": {"probability_of_loss": 0.0, "var_95": 1.0},
            "simulation_model": payload["engine_type"],
            "engine_type": payload["engine_type"],
        }

    monkeypatch.setattr(mojo_adapter, "_BINARY_PATH", Path("/tmp/does-not-exist-mojo"))
    monkeypatch.setattr(mojo_adapter.os, "access", lambda path, mode: False)
    monkeypatch.setattr(mojo_adapter, "_invoke_python_fallback", _fake_invoke_python_fallback)

    try:
        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "deny")
        _refresh_api_server_settings()
        with pytest.raises(mojo_adapter.MojoEngineError, match="Mojo binary not found"):
            await mojo_adapter._invoke_subprocess({"engine_type": "lhs", "runs": 25})
        assert fallback_calls == 0

        monkeypatch.setenv("RUNTIME_FALLBACK_MODE", "allow")
        _refresh_api_server_settings()
        result = await mojo_adapter._invoke_subprocess({"engine_type": "lhs", "runs": 25})
        assert result["engine_version"] == "0.1.0-python-fallback"
        assert result["simulation_model"] == "lhs"
        assert fallback_calls == 1
    finally:
        _refresh_api_server_settings()


def test_auth_service_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("API_KEY_PREFIX", "de_live_alpha_")
        _refresh_api_server_settings()
        raw_key, _, _ = auth_service.generate_api_key()
        assert raw_key.startswith("de_live_alpha_")

        monkeypatch.setenv("API_KEY_PREFIX", "de_live_beta_")
        _refresh_api_server_settings()
        raw_key, _, _ = auth_service.generate_api_key()
        assert raw_key.startswith("de_live_beta_")
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_auth_router_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=SimpleNamespace(value="owner"),
        password_hash="hashed",
    )
    request = SimpleNamespace(state=SimpleNamespace(request_id="req_auth_123"))

    async def _fake_get_user_by_email(email: str, db: object) -> object:
        del email, db
        return user

    monkeypatch.setattr(auth_router, "get_user_by_email", _fake_get_user_by_email)
    monkeypatch.setattr(auth_router, "verify_password", lambda plain, hashed: True)

    try:
        monkeypatch.setenv("JWT_SECRET", "secret-one")
        monkeypatch.setenv("JWT_EXPIRE_MINUTES", "5")
        _refresh_api_server_settings()
        response = await auth_router.login(
            request=request,
            payload=LoginRequest(email="owner@example.com", password="secret"),
            db=object(),
        )
        claims = jwt.decode(response.access_token, "secret-one", algorithms=["HS256"])
        assert claims["sub"] == str(user.id)
        assert response.expires_in == 300

        monkeypatch.setenv("JWT_SECRET", "secret-two")
        monkeypatch.setenv("JWT_EXPIRE_MINUTES", "15")
        _refresh_api_server_settings()
        response = await auth_router.login(
            request=request,
            payload=LoginRequest(email="owner@example.com", password="secret"),
            db=object(),
        )
        claims = jwt.decode(response.access_token, "secret-two", algorithms=["HS256"])
        assert claims["sub"] == str(user.id)
        assert response.expires_in == 900
        with pytest.raises(JWTError):
            jwt.decode(response.access_token, "secret-one", algorithms=["HS256"])
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_webhook_service_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_signatures: list[str] = []

    class _FakeResponse:
        status_code = 204

    async def _fake_async_http_request(**kwargs):  # type: ignore[no-untyped-def]
        captured_signatures.append(kwargs["headers"]["X-Webhook-Signature"])
        return _FakeResponse()

    monkeypatch.setattr(webhook_service, "async_http_request", _fake_async_http_request)

    try:
        monkeypatch.setenv("WEBHOOK_SIGNING_SECRET", "secret-one")
        _refresh_api_server_settings()
        delivered, status_code, message = await webhook_service.deliver_webhook(
            callback_url="https://hooks.customer.internal/webhook",
            payload={"event": "job.completed", "job_id": "job_123"},
            max_retries=0,
        )
        assert delivered is True
        assert status_code == 204
        assert message == "delivered"

        monkeypatch.setenv("WEBHOOK_SIGNING_SECRET", "secret-two")
        _refresh_api_server_settings()
        delivered, status_code, message = await webhook_service.deliver_webhook(
            callback_url="https://hooks.customer.internal/webhook",
            payload={"event": "job.completed", "job_id": "job_123"},
            max_retries=0,
        )
        assert delivered is True
        assert status_code == 204
        assert message == "delivered"
        assert len(captured_signatures) == 2
        assert captured_signatures[0] != captured_signatures[1]
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_stripe_service_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, str]:
            return {"url": "https://checkout.example/session"}

    async def _fake_stripe_api_request(**kwargs):  # type: ignore[no-untyped-def]
        captured_calls.append(
            {
                "authorization": kwargs["headers"]["Authorization"],
                "price_id": kwargs["data"]["line_items[0][price]"],
                "success_url": kwargs["data"]["success_url"],
                "cancel_url": kwargs["data"]["cancel_url"],
            }
        )
        return _FakeResponse()

    monkeypatch.setattr(stripe_service, "stripe_api_request", _fake_stripe_api_request)

    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.setenv("ALGENTA_APP_BASE_URL", "https://console-a.customer.internal")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_dynamic_a")
        monkeypatch.setenv("STRIPE_PRICE_DEVELOPER", "price_dynamic_a")
        _refresh_api_server_settings()
        response = await stripe_service.create_checkout_session(
            org_id=str(uuid.uuid4()),
            org_email="owner@example.com",
            plan="developer",
        )
        assert response["url"] == "https://checkout.example/session"

        monkeypatch.setenv("ALGENTA_APP_BASE_URL", "https://console-b.customer.internal")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_dynamic_b")
        monkeypatch.setenv("STRIPE_PRICE_DEVELOPER", "price_dynamic_b")
        _refresh_api_server_settings()
        response = await stripe_service.create_checkout_session(
            org_id=str(uuid.uuid4()),
            org_email="owner@example.com",
            plan="developer",
        )
        assert response["url"] == "https://checkout.example/session"
        assert captured_calls == [
            {
                "authorization": "Bearer sk_live_dynamic_a",
                "price_id": "price_dynamic_a",
                "success_url": "https://console-a.customer.internal/dashboard/billing?success=1",
                "cancel_url": "https://console-a.customer.internal/dashboard/billing?cancelled=1",
            },
            {
                "authorization": "Bearer sk_live_dynamic_b",
                "price_id": "price_dynamic_b",
                "success_url": "https://console-b.customer.internal/dashboard/billing?success=1",
                "cancel_url": "https://console-b.customer.internal/dashboard/billing?cancelled=1",
            },
        ]
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_stripe_service_accepts_legacy_dashboard_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, str]:
            return {"url": "https://checkout.example/session"}

    async def _fake_stripe_api_request(**kwargs):  # type: ignore[no-untyped-def]
        captured_calls.append(
            {
                "success_url": kwargs["data"]["success_url"],
                "cancel_url": kwargs["data"]["cancel_url"],
            }
        )
        return _FakeResponse()

    monkeypatch.setattr(stripe_service, "stripe_api_request", _fake_stripe_api_request)

    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("APP_BASE_URL", raising=False)
        monkeypatch.setenv("DE_APP_BASE_URL", "https://console.customer.internal")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_dynamic_alias")
        monkeypatch.setenv("STRIPE_PRICE_DEVELOPER", "price_dynamic_alias")
        _refresh_api_server_settings()
        response = await stripe_service.create_checkout_session(
            org_id=str(uuid.uuid4()),
            org_email="owner@example.com",
            plan="developer",
        )
        assert response["url"] == "https://checkout.example/session"
        assert captured_calls == [
            {
                "success_url": "https://console.customer.internal/dashboard/billing?success=1",
                "cancel_url": "https://console.customer.internal/dashboard/billing?cancelled=1",
            }
        ]
    finally:
        _refresh_api_server_settings()


def test_email_service_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_messages: list[tuple[str, str, str]] = []

    def _capture_send(to: str, subject: str, html: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        del kwargs
        captured_messages.append((to, subject, html))

    monkeypatch.setattr(email_service, "_send", _capture_send)

    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.setenv("ALGENTA_APP_BASE_URL", "https://console-a.customer.internal")
        monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://api-a.customer.internal")
        _refresh_api_server_settings()
        email_service.send_welcome_email("user@example.com", "Alice", "de_live_alpha")
        welcome_html = captured_messages[-1][2]
        assert "https://api-a.customer.internal/v1/simulate" in welcome_html
        assert "https://console-a.customer.internal/dashboard" in welcome_html
        assert "https://app.algenta.ai" not in welcome_html
        assert "https://api.algenta.ai" not in welcome_html

        monkeypatch.setenv("ALGENTA_APP_BASE_URL", "https://console-b.customer.internal")
        monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://api-b.customer.internal")
        _refresh_api_server_settings()
        email_service.send_quota_alert(
            email="user@example.com",
            org_name="Acme",
            plan="developer",
            used=8_000,
            limit=10_000,
            billing_period="2026-05",
            pct=80.0,
        )
        quota_html = captured_messages[-1][2]
        assert "https://console-b.customer.internal/dashboard/billing" in quota_html
        assert "https://app.algenta.ai" not in quota_html

        monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("ALGENTA_API_PUBLIC_BASE_URL", raising=False)
        monkeypatch.setenv("ALGENTA_BASE_URL", "https://internal.customer.example")
        _refresh_api_server_settings()
        email_service.send_welcome_email("user@example.com", "Alice", "de_live_alpha")
        cloud_managed_html = captured_messages[-1][2]
        assert "https://api.algenta.ai/v1/simulate" in cloud_managed_html
        assert "https://app.algenta.ai/dashboard" in cloud_managed_html
        assert "https://internal.customer.example" not in cloud_managed_html
    finally:
        _refresh_api_server_settings()


def test_email_service_accepts_legacy_dashboard_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_messages: list[tuple[str, str, str]] = []

    def _capture_send(to: str, subject: str, html: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        del kwargs
        captured_messages.append((to, subject, html))

    monkeypatch.setattr(email_service, "_send", _capture_send)

    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
        monkeypatch.delenv("APP_BASE_URL", raising=False)
        monkeypatch.setenv("DE_APP_BASE_URL", "https://console.customer.internal")
        monkeypatch.setenv("ALGENTA_API_PUBLIC_BASE_URL", "https://api.customer.internal")
        _refresh_api_server_settings()
        email_service.send_quota_alert(
            email="user@example.com",
            org_name="Acme",
            plan="developer",
            used=8_000,
            limit=10_000,
            billing_period="2026-05",
            pct=80.0,
        )
        quota_html = captured_messages[-1][2]
        assert "https://console.customer.internal/dashboard/billing" in quota_html
        assert "https://app.algenta.ai" not in quota_html
    finally:
        _refresh_api_server_settings()


@pytest.mark.anyio
async def test_data_map_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_optional_mojo_engine_impl(**kwargs):  # type: ignore[no-untyped-def]
        timeout_s = kwargs["timeout_s"]
        max_payload_bytes = kwargs["max_payload_bytes"]
        return None, {
            "engine_type": "column_profile",
            "status": "disabled",
            "reason": "engine_error",
            "message": f"timeout={timeout_s},max={max_payload_bytes}",
        }

    monkeypatch.setattr(
        data_map_router,
        "_invoke_optional_mojo_engine_impl",
        _fake_optional_mojo_engine_impl,
    )

    try:
        monkeypatch.setenv("MOJO_PROFILING_POLICY", "optional")
        monkeypatch.setenv("ALGENTA_OPTIONAL_MOJO_TIMEOUT_S", "2.5")
        monkeypatch.setenv("ALGENTA_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES", "1234")
        _refresh_api_server_settings()
        result = await data_map_router._call_mojo_column_profile(
            {
                "measure_total": {
                    "values": [10.0, 20.0, 30.0, 40.0],
                    "strings": ["10", "20", "30", "40"],
                    "sample_size": 8,
                }
            }
        )
        assert result is not None
        assert result["_profiling_status"]["message"] == "timeout=2.5,max=1234"

        monkeypatch.setenv("MOJO_PROFILING_POLICY", "required")
        monkeypatch.setenv("ALGENTA_OPTIONAL_MOJO_TIMEOUT_S", "7.5")
        monkeypatch.setenv("ALGENTA_OPTIONAL_MOJO_MAX_PAYLOAD_BYTES", "4321")
        _refresh_api_server_settings()
        with pytest.raises(data_map_router.MojoInstrumentationError):
            await data_map_router._call_mojo_column_profile(
                {
                    "measure_total": {
                        "values": [10.0, 20.0, 30.0, 40.0],
                        "strings": ["10", "20", "30", "40"],
                        "sample_size": 8,
                    }
                }
            )
    finally:
        _refresh_api_server_settings()


def test_playground_upgrade_hint_uses_request_origin_in_private_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
        _refresh_api_server_settings()
        request = SimpleNamespace(base_url="https://decision.customer.internal/")
        hint = playground_router._dashboard_upgrade_hint(request)
        assert hint == "https://decision.customer.internal/dashboard — free tier: 500 simulations/month"
        assert "algenta.ai" not in hint
    finally:
        _refresh_api_server_settings()


def test_storage_service_honors_environment_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_calls: list[dict[str, object]] = []

    boto3_module = types.ModuleType("boto3")

    def _fake_boto3_client(**kwargs):  # type: ignore[no-untyped-def]
        client_calls.append(kwargs)
        return object()

    boto3_module.client = _fake_boto3_client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", boto3_module)
    monkeypatch.setattr(storage_service, "enforce_egress_sync", lambda *args, **kwargs: None)

    try:
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://minio-a.customer.internal")
        monkeypatch.setenv("S3_REGION", "us-east-1")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "access-a")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret-a")
        _refresh_api_server_settings()
        storage_service._get_client()

        monkeypatch.setenv("S3_ENDPOINT_URL", "https://minio-b.customer.internal")
        monkeypatch.setenv("S3_REGION", "eu-central-1")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "access-b")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret-b")
        _refresh_api_server_settings()
        storage_service._get_client()

        assert client_calls == [
            {
                "service_name": "s3",
                "endpoint_url": "https://minio-a.customer.internal",
                "aws_access_key_id": "access-a",
                "aws_secret_access_key": "secret-a",
                "region_name": "us-east-1",
            },
            {
                "service_name": "s3",
                "endpoint_url": "https://minio-b.customer.internal",
                "aws_access_key_id": "access-b",
                "aws_secret_access_key": "secret-b",
                "region_name": "eu-central-1",
            },
        ]
    finally:
        _refresh_api_server_settings()
