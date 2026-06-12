"""B10 PR2: the remote PR/MR creation (token-bearing write to the customer git host) routes
through the egress guard, so the self_hosted/air_gapped fail-closed policy + SSRF check apply to
the customer-configured api_base_url. Deny raises a typed RepositoryIntelligenceError before any
socket; the existing >=400 mapping is preserved."""

from __future__ import annotations

import pytest

from apps.api_server.config import get_settings
from apps.api_server.services import egress_guard
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_execution_workflow import (
    _create_pull_request,
)


class _Resp:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body

    @property
    def text(self) -> str:
        return str(self._body)


class _RaisingAsyncClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("httpx.AsyncClient must not be constructed when egress is denied")


async def _create(*, api_base_url: str) -> str:
    return await _create_pull_request(
        connector_type="github_repo",
        config={"api_base_url": api_base_url, "access_token": "ghp_test"},
        repository_url="https://github.com/acme/widget",
        source_branch="algenta/fix",
        target_branch="main",
        title="Fix",
        body="body",
        repo_access_token=lambda config: config.get("access_token"),
    )


async def test_pr_creation_routes_through_egress_guard(monkeypatch):
    captured = {}

    async def _fake_async_http_request(**kwargs):
        captured.update(kwargs)
        return _Resp(201, {"html_url": "https://github.com/acme/widget/pull/7"})

    monkeypatch.setattr(egress_guard, "async_http_request", _fake_async_http_request)

    url = await _create(api_base_url="https://api.github.example")

    assert url == "https://github.com/acme/widget/pull/7"
    assert captured["method"] == "POST"
    assert captured["surface"] == "repository_remote_pull_request"
    assert captured["egress_class"] == "customer_connector"
    assert captured["explicit_configured"] is True
    assert captured["url"].endswith("/repos/acme/widget/pulls")


async def test_pr_creation_deny_raises_before_socket(monkeypatch):
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()
    monkeypatch.setattr(egress_guard.httpx, "AsyncClient", _RaisingAsyncClient)
    try:
        with pytest.raises(RepositoryIntelligenceError) as excinfo:
            await _create(api_base_url="https://api.unallowlisted-public.example")
        assert excinfo.value.code == "remote_pull_request_egress_denied"
        assert excinfo.value.status_code == 502
    finally:
        get_settings.cache_clear()


async def test_pr_creation_preserves_4xx_mapping(monkeypatch):
    async def _fake_async_http_request(**kwargs):
        return _Resp(422, {"message": "validation failed"})

    monkeypatch.setattr(egress_guard, "async_http_request", _fake_async_http_request)
    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        await _create(api_base_url="https://api.github.example")
    assert excinfo.value.code == "remote_pull_request_failed"
    assert excinfo.value.status_code == 502
