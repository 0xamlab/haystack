"""Tests for test_llm_api_router: responses_route.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-4/tests/test_llm_api_router.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_router_helpers import *  # noqa: F401,F403


def test_responses_route_returns_tokenization_envelope(monkeypatch) -> None:
    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "text.tokenizer"
        assert inputs == ["alpha beta"]
        assert dimensions == 64
        return _tokenizer_model_descriptor(), "resp_test_tokenizer", [
            SimpleNamespace(
                index=0,
                item_type="tokenization",
                text="alpha beta",
                tokens=["alpha", "beta"],
                token_count=2,
                embedding=None,
                provider=None,
            )
        ], 2

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "text.tokenizer", "input": "alpha beta"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "resp_test_tokenizer",
        "object": "response",
        "status": "completed",
        "model": "text.tokenizer",
        "provider_backend": None,
        "provider_model_id": None,
        "provider_attempts": [],
        "output": [
            {
                "id": "resp_test_tokenizer_item_0",
                "object": "response.output",
                "index": 0,
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
                "content": [
                    {
                        "type": "tokenization",
                        "text": "alpha beta",
                        "tokens": ["alpha", "beta"],
                        "token_count": 2,
                        "embedding": None,
                    }
                ],
            }
        ],
        "usage": {"prompt_tokens": 2, "total_tokens": 2},
    }


def test_responses_route_streams_sse_output_events(monkeypatch) -> None:
    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "text.tokenizer"
        assert inputs == ["alpha beta"]
        assert dimensions == 64
        return _tokenizer_model_descriptor(), "resp_stream_123", [
            SimpleNamespace(
                index=0,
                item_type="tokenization",
                text="alpha beta",
                tokens=["alpha", "beta"],
                token_count=2,
                embedding=None,
                provider=None,
            )
        ], 2

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "text.tokenizer", "input": "alpha beta", "stream": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"type":"response.created"' in response.text
    assert '"provider_backend":null' in response.text
    assert '"provider_model_id":null' in response.text
    assert '"provider_attempts":[]' in response.text
    assert '"type":"response.output_item.done"' in response.text
    assert '"type":"response.completed"' in response.text
    assert "data: [DONE]" in response.text


def test_responses_route_returns_provider_text_envelope(monkeypatch) -> None:
    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "provider.gpt-4o-mini"
        assert inputs == ["alpha beta"]
        assert dimensions == 64
        return _provider_chat_model_descriptor(), "resp_provider_text", [
            SimpleNamespace(
                index=0,
                item_type="text",
                text="Provider response.",
                tokens=None,
                token_count=3,
                embedding=None,
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
        ], 5

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "provider.gpt-4o-mini", "input": "alpha beta"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "resp_provider_text",
        "object": "response",
        "status": "completed",
        "model": "provider.gpt-4o-mini",
        "provider_backend": "openai_compatible",
        "provider_model_id": "provider.gpt-4o-mini",
        "provider_attempts": [
            {
                "provider_backend": "openai_compatible",
                "provider_model_id": "provider.gpt-4o-mini",
                "outcome": "selected",
                "error_code": None,
            }
        ],
        "output": [
            {
                "id": "resp_provider_text_item_0",
                "object": "response.output",
                "index": 0,
                "provider_backend": "openai_compatible",
                "provider_model_id": "provider.gpt-4o-mini",
                "provider_attempts": [
                    {
                        "provider_backend": "openai_compatible",
                        "provider_model_id": "provider.gpt-4o-mini",
                        "outcome": "selected",
                        "error_code": None,
                    }
                ],
                "content": [
                    {
                        "type": "text",
                        "text": "Provider response.",
                        "tokens": None,
                        "token_count": 3,
                        "embedding": None,
                    }
                ],
            }
        ],
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }


