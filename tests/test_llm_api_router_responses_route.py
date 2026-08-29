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
                        "tool_calls": None,
                        "finish_reason": None,
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
                        "tool_calls": None,
                        "finish_reason": None,
                    }
                ],
            }
        ],
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }


def test_responses_route_legacy_list_input_stays_independent_completions(monkeypatch) -> None:
    """Regression guard (Track C1a): a list[str] input MUST keep meaning N independent
    single-turn requests via create_utility_response -- it must never get reinterpreted as the
    new typed multi-turn conversation path (create_utility_conversation_response). These are
    semantically incompatible shapes and the content-negotiation must route strictly on whether
    the list's items are dicts, never on anything else about a list[str] payload."""

    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert inputs == ["alpha", "beta"]
        return _tokenizer_model_descriptor(), "resp_legacy_list", [
            SimpleNamespace(
                index=0,
                item_type="tokenization",
                text="alpha",
                tokens=["alpha"],
                token_count=1,
                embedding=None,
                provider=None,
                provider_attempts=(),
            ),
            SimpleNamespace(
                index=1,
                item_type="tokenization",
                text="beta",
                tokens=["beta"],
                token_count=1,
                embedding=None,
                provider=None,
                provider_attempts=(),
            ),
        ], 2

    async def _fail_if_called(**kwargs):
        raise AssertionError(
            "create_utility_conversation_response must not be called for a list[str] input"
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    monkeypatch.setattr(llm_router, "create_utility_conversation_response", _fail_if_called)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "text.tokenizer", "input": ["alpha", "beta"]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["output"]) == 2
    assert body["output"][0]["content"][0]["text"] == "alpha"
    assert body["output"][1]["content"][0]["text"] == "beta"


def test_responses_route_typed_input_array_dispatches_to_conversation_path(monkeypatch) -> None:
    """A typed OpenResponses-shaped input array (items carrying a "type" key) must dispatch to
    create_utility_conversation_response, carry tools/tool_choice through, and support a
    tool-call-only turn (null text, tool_calls populated, finish_reason == "tool_calls")."""
    captured: dict[str, object] = {}

    async def _fake_conversation_response(
        *,
        model_id: str,
        items: list[dict],
        previous_response_id: str | None,
        tools=None,
        tool_choice=None,
        parallel_tool_calls=None,
    ):
        captured["model_id"] = model_id
        captured["items"] = items
        captured["previous_response_id"] = previous_response_id
        captured["tools"] = tools
        captured["tool_choice"] = tool_choice
        return _provider_chat_model_descriptor(), "resp_conv_1", [
            SimpleNamespace(
                index=0,
                item_type="text",
                text=None,
                tokens=None,
                token_count=0,
                embedding=None,
                provider=SimpleNamespace(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                ),
                provider_attempts=(),
                tool_calls=(
                    SimpleNamespace(
                        id="call_1",
                        function=SimpleNamespace(
                            name="get_weather", arguments='{"location":"Paris"}'
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            )
        ], 10

    async def _fail_if_called(**kwargs):
        raise AssertionError("create_utility_response must not be called for a typed input array")

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fail_if_called)
    monkeypatch.setattr(
        llm_router, "create_utility_conversation_response", _fake_conversation_response
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={
                    "model": "provider.gpt-4o-mini",
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": "What is the weather in Paris?",
                        }
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"location": {"type": "string"}},
                                },
                            },
                        }
                    ],
                    "tool_choice": "auto",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    content = body["output"][0]["content"][0]
    assert content["text"] is None
    assert content["finish_reason"] == "tool_calls"
    assert content["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"location":"Paris"}'},
        }
    ]
    assert captured["items"] == [
        {"type": "message", "role": "user", "content": "What is the weather in Paris?"}
    ]
    assert captured["previous_response_id"] is None
    assert captured["tool_choice"] == "auto"
    assert captured["tools"][0]["function"]["name"] == "get_weather"


def test_responses_route_forwards_previous_response_id_to_conversation_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_conversation_response(
        *, model_id: str, items: list[dict], previous_response_id: str | None, **_ignored
    ):
        captured["previous_response_id"] = previous_response_id
        captured["items"] = items
        return _provider_chat_model_descriptor(), "resp_conv_2", [
            SimpleNamespace(
                index=0,
                item_type="text",
                text="Sunny in Paris.",
                tokens=None,
                token_count=4,
                embedding=None,
                provider=None,
                provider_attempts=(),
                tool_calls=None,
                finish_reason="stop",
            )
        ], 8

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router, "create_utility_conversation_response", _fake_conversation_response
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={
                    "model": "provider.gpt-4o-mini",
                    "input": [
                        {
                            "type": "function_call_output",
                            "call_id": "call_1",
                            "output": "15C, sunny",
                        }
                    ],
                    "previous_response_id": "resp_conv_1",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["previous_response_id"] == "resp_conv_1"
    assert captured["items"] == [
        {"type": "function_call_output", "call_id": "call_1", "output": "15C, sunny"}
    ]
    assert response.json()["output"][0]["content"][0]["text"] == "Sunny in Paris."


def test_responses_route_rejects_previous_response_id_with_legacy_shape(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={
                    "model": "text.tokenizer",
                    "input": "hello",
                    "previous_response_id": "resp_whatever",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_provider_request"


def test_responses_route_rejects_streaming_with_tool_calls(monkeypatch) -> None:
    async def _fake_conversation_response(
        *, model_id: str, items: list[dict], previous_response_id: str | None, **_ignored
    ):
        return _provider_chat_model_descriptor(), "resp_conv_3", [
            SimpleNamespace(
                index=0,
                item_type="text",
                text=None,
                tokens=None,
                token_count=0,
                embedding=None,
                provider=None,
                provider_attempts=(),
                tool_calls=(
                    SimpleNamespace(
                        id="call_1", function=SimpleNamespace(name="get_weather", arguments="{}")
                    ),
                ),
                finish_reason="tool_calls",
            )
        ], 5

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router, "create_utility_conversation_response", _fake_conversation_response
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={
                    "model": "provider.gpt-4o-mini",
                    "input": [{"type": "message", "role": "user", "content": "weather?"}],
                    "tools": [{"type": "function", "function": {"name": "get_weather"}}],
                    "stream": True,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "model_capability_unsupported"
    assert body["error"]["details"]["required_capability"] == "streaming_tool_calls"


def test_responses_route_typed_input_malformed_item_returns_422(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={
                    "model": "provider.gpt-4o-mini",
                    "input": [{"type": "not_a_real_type", "foo": "bar"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert any("input" in detail["field"] for detail in body["error"]["details"])


