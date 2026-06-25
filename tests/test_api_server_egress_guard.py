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


@pytest.mark.parametrize(
    "private_url",
    [
        "http://127.0.0.1/secret",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/loopback6",
    ],
)
def test_read_url_text_blocks_private_destination_under_permissive_outbound(
    monkeypatch: pytest.MonkeyPatch,
    private_url: str,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "true")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    def _unexpected_urlopen(*args, **kwargs):
        raise AssertionError("urlopen should not be called when SSRF guard denies")

    monkeypatch.setattr(
        "apps.api_server.services.data_map_sources.urllib.request.urlopen",
        _unexpected_urlopen,
    )

    with pytest.raises(EgressPolicyDeniedError) as exc_info:
        read_url_text(private_url)

    # link-local (169.254.x) is denied as ssrf_guard_link_local_destination; other private/loopback
    # ranges as ssrf_guard_private_destination — both are the SSRF guard blocking before any socket.
    assert exc_info.value.decision.reason.startswith("ssrf_guard")
    get_settings.cache_clear()


def test_read_url_text_blocks_private_destination_resolved_via_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "true")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    def _resolver_to_private(host, *args, **kwargs):
        return [(2, 1, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.socket.getaddrinfo",
        _resolver_to_private,
    )

    def _unexpected_urlopen(*args, **kwargs):
        raise AssertionError("urlopen should not be called when SSRF guard denies")

    monkeypatch.setattr(
        "apps.api_server.services.data_map_sources.urllib.request.urlopen",
        _unexpected_urlopen,
    )

    with pytest.raises(EgressPolicyDeniedError) as exc_info:
        read_url_text("https://attacker-controlled.example.com/")

    assert exc_info.value.decision.reason == "ssrf_guard_private_destination"
    get_settings.cache_clear()


def test_ssrf_guard_skipped_for_explicit_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "false")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "internal-bus.svc.cluster.local")
    get_settings.cache_clear()

    def _resolver_to_private(host, *args, **kwargs):
        return [(2, 1, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.socket.getaddrinfo",
        _resolver_to_private,
    )

    captured: dict[str, object] = {}

    class _FakeHeaders:
        def get(self, _key, default=""):
            return "text/plain"

    class _FakeResponse:
        headers = _FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"ok"

    def _capturing_urlopen(request, *args, **kwargs):
        captured["url"] = (
            request.full_url
            if hasattr(request, "full_url")
            else str(request)
        )
        return _FakeResponse()

    monkeypatch.setattr(
        "apps.api_server.services.data_map_sources.urllib.request.urlopen",
        _capturing_urlopen,
    )

    body, content_type = read_url_text("https://internal-bus.svc.cluster.local/queue")
    assert captured["url"] == "https://internal-bus.svc.cluster.local/queue"
    assert body == "ok"
    assert content_type == "text/plain"
    get_settings.cache_clear()


def test_ssrf_guard_blocks_link_local_metadata_even_when_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A wildcard-allowlisted host whose DNS resolves to the cloud-metadata endpoint must be denied —
    # link-local is never a legitimate egress target, even on an operator allowlist.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "false")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "*.evil.example")
    get_settings.cache_clear()

    def _resolver_to_metadata(host, *args, **kwargs):
        return [(2, 1, 6, "", ("169.254.169.254", 0))]

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.socket.getaddrinfo",
        _resolver_to_metadata,
    )
    try:
        with pytest.raises(EgressPolicyDeniedError) as exc_info:
            read_url_text("https://attacker.evil.example/latest/meta-data/")
        assert exc_info.value.decision.reason == "ssrf_guard_link_local_destination"
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "metadata_ip",
    [
        "::ffff:169.254.169.254",  # IPv4-mapped IPv6
        "64:ff9b::a9fe:a9fe",      # NAT64-embedded 169.254.169.254
        "fd00:ec2::254",           # AWS IMDSv6
    ],
)
def test_ssrf_guard_blocks_metadata_ipv6_encodings_even_when_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
    metadata_ip: str,
) -> None:
    # IPv6 encodings that smuggle the cloud-metadata endpoint past a naive link-local check must
    # still be denied, even for an allowlisted host.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "false")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "*.evil.example")
    get_settings.cache_clear()

    def _resolver(host, *args, **kwargs):
        return [(10, 1, 6, "", (metadata_ip, 0, 0, 0))]

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.socket.getaddrinfo", _resolver
    )
    try:
        with pytest.raises(EgressPolicyDeniedError) as exc_info:
            read_url_text("https://attacker.evil.example/x")
        assert exc_info.value.decision.reason == "ssrf_guard_link_local_destination"
    finally:
        get_settings.cache_clear()


def test_read_url_text_allows_allowlisted_loopback_destination_under_permissive_outbound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "true")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "127.0.0.1")
    get_settings.cache_clear()

    captured: dict[str, object] = {}

    class _FakeHeaders:
        def get(self, _key, default=""):
            return "text/csv"

    class _FakeResponse:
        headers = _FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"id,value\n1,ok\n"

    def _capturing_urlopen(request, *args, **kwargs):
        captured["url"] = request.full_url if hasattr(request, "full_url") else str(request)
        return _FakeResponse()

    monkeypatch.setattr(
        "apps.api_server.services.data_map_sources.urllib.request.urlopen",
        _capturing_urlopen,
    )

    body, content_type = read_url_text("http://127.0.0.1:8765/fixture.csv")

    assert captured["url"] == "http://127.0.0.1:8765/fixture.csv"
    assert body == "id,value\n1,ok\n"
    assert content_type == "text/csv"
    get_settings.cache_clear()
