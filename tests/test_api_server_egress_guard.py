from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from apps.api_server.config import get_settings
from apps.api_server.services.data_map_sources import read_url_text
from apps.api_server.services.egress_guard import EgressPolicyDeniedError
from apps.api_server.services.stripe_service import create_checkout_session
from apps.api_server.services.webhook_service import deliver_webhook


@pytest.mark.anyio
async def test_deliver_webhook_blocks_unallowlisted_public_destination_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    class _UnexpectedAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("network client should not be created when egress is denied")

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.httpx.AsyncClient",
        _UnexpectedAsyncClient,
    )

    delivered, status_code, message = await deliver_webhook(
        callback_url="https://example.com/webhook",
        payload={"event": "job.completed", "job_id": "job_123"},
        max_retries=0,
    )

    assert delivered is False
    assert status_code == 0
    assert message == "egress_policy_denied: destination_not_allowlisted"
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_deliver_webhook_allows_allowlisted_customer_destination_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "*.customer.internal")
    get_settings.cache_clear()

    class _FakeResponse:
        status_code = 204

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self.calls: list[tuple[str, bytes, dict[str, str]]] = []

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(
            self,
            callback_url: str,
            *,
            content: bytes,
            headers: dict[str, str],
        ) -> _FakeResponse:
            assert callback_url == "https://hooks.customer.internal/webhook"
            assert content
            assert headers["Content-Type"] == "application/json"
            return _FakeResponse()

    monkeypatch.setattr("apps.api_server.services.egress_guard.httpx.AsyncClient", _FakeAsyncClient)

    delivered, status_code, message = await deliver_webhook(
        callback_url="https://hooks.customer.internal/webhook",
        payload={"event": "job.completed", "job_id": "job_123"},
        max_retries=0,
    )

    assert delivered is True
    assert status_code == 204
    assert message == "delivered"
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_create_checkout_session_blocks_private_profile_operator_egress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    class _UnexpectedAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("stripe network client should not be created when blocked")

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.httpx.AsyncClient",
        _UnexpectedAsyncClient,
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_checkout_session(
            org_id=str(uuid.uuid4()),
            org_email="owner@example.com",
            plan="developer",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"]["code"] == "egress_policy_denied"
    get_settings.cache_clear()


def test_read_url_text_blocks_unallowlisted_public_destination_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    def _unexpected_urlopen(*args, **kwargs):
        raise AssertionError("urlopen should not be called when egress is denied")

    monkeypatch.setattr(
        "apps.api_server.services.data_map_sources.urllib.request.urlopen",
        _unexpected_urlopen,
    )

    with pytest.raises(EgressPolicyDeniedError) as exc_info:
        read_url_text("https://example.com/facts.json")

    assert exc_info.value.decision.reason == "destination_not_allowlisted"
    get_settings.cache_clear()
