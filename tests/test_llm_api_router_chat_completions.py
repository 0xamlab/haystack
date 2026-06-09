"""Tests for test_llm_api_router: chat_completions.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-4/tests/test_llm_api_router.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_router_helpers import *  # noqa: F401,F403


def test_chat_completions_route_surfaces_provider_backend_unavailable(monkeypatch) -> None:
    async def _fake_chat(*, model_id: str, messages: list[dict[str, str]]):
        del model_id, messages
        raise LLMAPIError(
            "backend_unavailable",
            "Provider-backed model 'provider.gpt-4o-mini' is configured, but environment variable 'OPENAI_API_KEY' is not set.",
            {"model": "provider.gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "backend_unavailable"
    assert error["details"] == {
        "model": "provider.gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    }
    assert isinstance(error["request_id"], str)


def test_chat_completions_route_surfaces_provider_rate_limit(monkeypatch) -> None:
    async def _fake_chat(*, model_id: str, messages: list[dict[str, str]]):
        del model_id, messages
        raise LLMAPIError(
            "provider_rate_limited",
            "Provider backend rate limited model 'provider.gpt-4o-mini'.",
            {"model": "provider.gpt-4o-mini", "status_code": 429},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "provider_rate_limited"
    assert error["details"] == {"model": "provider.gpt-4o-mini", "status_code": 429}
    assert isinstance(error["request_id"], str)


def test_chat_completions_route_surfaces_invalid_provider_request(monkeypatch) -> None:
    async def _fake_chat(*, model_id: str, messages: list[dict[str, str]]):
        del model_id, messages
        raise LLMAPIError(
            "invalid_provider_request",
            "Provider backend rejected the request for model 'provider.gpt-4o-mini'.",
            {"model": "provider.gpt-4o-mini", "status_code": 400},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_provider_request"
    assert error["details"] == {"model": "provider.gpt-4o-mini", "status_code": 400}
    assert isinstance(error["request_id"], str)


def test_chat_completions_route_returns_deterministic_assistant_message(monkeypatch) -> None:
    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        assert model_id == "text.tokenizer"
        assert messages == [
            {"role": "system", "content": "Keep output deterministic"},
            {"role": "user", "content": "alpha beta"},
        ]
        return _tokenizer_model_descriptor(), SimpleNamespace(
            completion_id="chatcmpl_test_123",
            content='{"model":"text.tokenizer","token_count":2,"tokens":["alpha","beta"]}',
            prompt_tokens=5,
            completion_tokens=9,
            provider=None,
            provider_attempts=[],
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat_completion)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "text.tokenizer",
                    "messages": [
                        {"role": "system", "content": "Keep output deterministic"},
                        {"role": "user", "content": "alpha beta"},
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "chatcmpl_test_123",
        "object": "chat.completion",
        "model": "text.tokenizer",
        "provider_backend": None,
        "provider_model_id": None,
        "provider_attempts": [],
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": '{"model":"text.tokenizer","token_count":2,"tokens":["alpha","beta"]}',
                },
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 9,
            "total_tokens": 14,
        },
    }


def test_chat_completions_route_surfaces_provider_execution_metadata(monkeypatch) -> None:
    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        assert model_id == "provider.gpt-4o-mini"
        assert messages == [{"role": "user", "content": "Summarize"}]
        return _provider_chat_model_descriptor(), SimpleNamespace(
            completion_id="chatcmpl_provider_123",
            content="Provider response.",
            prompt_tokens=3,
            completion_tokens=2,
            provider=SimpleNamespace(
                provider_backend="openai_compatible",
                provider_model_id="provider.gpt-4o-mini",
            ),
            provider_attempts=[
                SimpleNamespace(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                    outcome="selected",
                    error_code=None,
                )
            ],
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat_completion)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Summarize"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["provider_backend"] == "openai_compatible"
    assert response.json()["provider_model_id"] == "provider.gpt-4o-mini"
    assert response.json()["provider_attempts"] == [
        {
            "provider_backend": "openai_compatible",
            "provider_model_id": "provider.gpt-4o-mini",
            "outcome": "selected",
            "error_code": None,
        }
    ]


def test_chat_completions_route_streams_sse_chunks(monkeypatch) -> None:
    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        assert model_id == "text.tokenizer"
        assert messages == [{"role": "user", "content": "alpha beta"}]
        return _tokenizer_model_descriptor(), SimpleNamespace(
            completion_id="chatcmpl_stream_123",
            content="deterministic utility response",
            prompt_tokens=2,
            completion_tokens=3,
            provider=None,
            provider_attempts=[],
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat_completion)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "text.tokenizer",
                    "messages": [{"role": "user", "content": "alpha beta"}],
                    "stream": True,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"object":"chat.completion.chunk"' in response.text
    assert '"provider_backend":null' in response.text
    assert '"provider_model_id":null' in response.text
    assert '"provider_attempts":[]' in response.text
    assert '"role":"assistant"' in response.text
    assert '"content":"deterministic utility' in response.text
    assert "data: [DONE]" in response.text


