from __future__ import annotations

import io
import json
import urllib.error

import pytest

from apps.cli import support


class _FakeStreamResponse:
    def __init__(self, *, lines: list[bytes], content_type: str = "text/event-stream") -> None:
        self.headers = {"Content-Type": content_type}
        self._lines = lines

    def __enter__(self) -> _FakeStreamResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


class _FakeJsonResponse:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self._body = body
        self.status = status

    def __enter__(self) -> _FakeJsonResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_get_base_url_private_profile_requires_explicit_origin(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.setattr(support, "load_config", lambda: {})

    with pytest.raises(ValueError, match="require an explicit self-hosted API origin"):
        support.get_base_url()


def test_get_api_key_prefers_algenta_env_then_legacy_env(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_API_KEY", "algenta-env")
    monkeypatch.setenv("DE_API_KEY", "legacy-env")
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_api_key() == "algenta-env"


def test_get_api_key_accepts_legacy_env_when_algenta_env_is_absent(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setenv("DE_API_KEY", "legacy-env")
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_api_key() == "legacy-env"


def test_get_base_url_private_profile_rejects_algenta_cloud(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.setenv("DE_BASE_URL", "https://api.algenta.ai")
    monkeypatch.setattr(support, "load_config", lambda: {})

    with pytest.raises(ValueError, match="Algenta-owned cloud URLs"):
        support.get_base_url()


def test_get_base_url_private_profile_allows_allowlisted_customer_origin(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.setenv("DE_BASE_URL", "https://api.customer.example")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "api.customer.example")
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_base_url() == "https://api.customer.example"


def test_get_dashboard_url_defaults_to_cloud_managed_dashboard(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("ALGENTA_DISABLE_CLOUD", raising=False)
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_dashboard_url() == "https://app.algenta.ai/dashboard"


def test_get_dashboard_url_private_profile_falls_back_to_self_hosted_api_origin(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_dashboard_url() == "http://localhost:8000/dashboard"


def test_get_dashboard_url_private_profile_accepts_algenta_api_url(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_API_URL", "http://localhost:8000")
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_dashboard_url() == "http://localhost:8000/dashboard"


def test_get_dashboard_url_private_profile_prefers_explicit_app_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("ALGENTA_APP_BASE_URL", "https://console.customer.internal")
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.setattr(support, "load_config", lambda: {})

    assert support.get_dashboard_url() == "https://console.customer.internal/dashboard"


def test_get_dashboard_url_private_profile_requires_explicit_origin(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.delenv("ALGENTA_APP_BASE_URL", raising=False)
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.delenv("DE_APP_BASE_URL", raising=False)
    monkeypatch.setattr(support, "load_config", lambda: {})

    with pytest.raises(ValueError, match="require an explicit self-hosted dashboard or API origin"):
        support.get_dashboard_url()


def test_api_stream_request_yields_json_objects_from_sse_payloads(monkeypatch) -> None:
    monkeypatch.setattr(support, "get_base_url", lambda: "https://example.test")
    monkeypatch.setattr(support, "get_api_key", lambda: "de_live_test")

    def _fake_urlopen(request, timeout=120):  # type: ignore[no-untyped-def]
        assert request.full_url == "https://example.test/v1/chat/completions"
        assert request.headers["Accept"] == "text/event-stream"
        assert json.loads(request.data.decode()) == {"model": "text.tokenizer", "stream": True}
        return _FakeStreamResponse(
            lines=[
                b"data: {\"type\":\"response.created\"}\n",
                b"\n",
                b"data: {\"type\":\"response.completed\"}\n",
                b"data: [DONE]\n",
            ]
        )

    monkeypatch.setattr(support.urllib.request, "urlopen", _fake_urlopen)

    payloads = list(
        support.api_stream_request(
            "POST",
            "/v1/chat/completions",
            {"model": "text.tokenizer", "stream": True},
        )
    )

    assert payloads == [{"type": "response.created"}, {"type": "response.completed"}]


def test_api_stream_request_rejects_non_sse_content_type(monkeypatch) -> None:
    monkeypatch.setattr(support, "get_base_url", lambda: "https://example.test")
    monkeypatch.setattr(support, "get_api_key", lambda: "de_live_test")
    monkeypatch.setattr(
        support.urllib.request,
        "urlopen",
        lambda request, timeout=120: _FakeStreamResponse(  # type: ignore[no-untyped-def]
            lines=[b"{\"ok\":true}"],
            content_type="application/json",
        ),
    )

    with pytest.raises(RuntimeError, match="Expected text/event-stream response"):
        list(support.api_stream_request("GET", "/v1/agent/runs/run_123/events?stream=true"))


def test_api_stream_request_raises_structured_error_on_http_failure(monkeypatch) -> None:
    monkeypatch.setattr(support, "get_base_url", lambda: "https://example.test")
    monkeypatch.setattr(support, "get_api_key", lambda: "de_live_test")

    error_body = io.BytesIO(
        json.dumps({"error": {"code": "quota_exceeded", "message": "Monthly quota exhausted"}}).encode()
    )

    def _fake_urlopen(request, timeout=120):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            hdrs=None,
            fp=error_body,
        )

    monkeypatch.setattr(support.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError) as excinfo:
        list(support.api_stream_request("GET", "/v1/agent/runs/run_123/events?stream=true"))

    payload = json.loads(str(excinfo.value))
    assert payload == {
        "status": 429,
        "body": {"error": {"code": "quota_exceeded", "message": "Monthly quota exhausted"}},
    }


def test_api_request_accepts_empty_success_body(monkeypatch) -> None:
    monkeypatch.setattr(support, "get_base_url", lambda: "https://example.test")
    monkeypatch.setattr(support, "get_api_key", lambda: "de_live_test")
    monkeypatch.setattr(
        support.urllib.request,
        "urlopen",
        lambda request, timeout=120: _FakeJsonResponse(b""),  # type: ignore[no-untyped-def]
    )

    status, payload = support.api_request("DELETE", "/v1/api-keys/key_123")

    assert status == 200
    assert payload == {}


def test_api_request_accepts_list_success_body(monkeypatch) -> None:
    monkeypatch.setattr(support, "get_base_url", lambda: "https://example.test")
    monkeypatch.setattr(support, "get_api_key", lambda: "de_live_test")
    monkeypatch.setattr(
        support.urllib.request,
        "urlopen",
        lambda request, timeout=120: _FakeJsonResponse(  # type: ignore[no-untyped-def]
            json.dumps([{"id": "key_123"}]).encode()
        ),
    )

    status, payload = support.api_request("GET", "/v1/api-keys")

    assert status == 200
    assert payload == [{"id": "key_123"}]
