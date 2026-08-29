"""Track C1a (responses protocol core): a real contract test for /v1/responses' new typed-array
tool-calling path.

This drives the REAL ASGI app end-to-end over httpx.ASGITransport -- no network, no live server,
and (unlike every other /v1/responses test in this repo) no monkeypatching of our own router or
service layer. Only the upstream provider's HTTP call is faked (the same technique
test_llm_provider_service_provider_chat.py and test_llm_chat_completions_tool_calling_contract.py
use), so auth override, rate limit noop, router content-negotiation, create_utility_conversation_
response, create_chat_completion, provider payload building, and response parsing are all the
real code path.

Unlike test_llm_chat_completions_tool_calling_contract.py, this file does NOT drive the request
through the real `openai` Python SDK's `.responses.create()`. Our /v1/responses wire shape is
deliberately "OpenResponses-style" (see ResponsesRequest/ResponseOutputContent docstrings), a
distinct convention from OpenAI's actual Responses API -- our envelope uses different field names
(provider_backend/provider_attempts, usage.prompt_tokens/total_tokens with no completion_tokens,
etc.) that the real SDK's typed `Response`/`ResponseUsage` models would reject. A raw JSON round
trip through the real app is the honest version of this contract test for this endpoint.
"""
from __future__ import annotations

import json

import httpx
import pytest

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import llm as llm_router
from apps.api_server.services import llm_provider_service

from tests._test_llm_api_router_helpers import _fake_auth, _noop_rate_limit

# Captured before any monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", ...) --
# that patch replaces the GLOBAL httpx.AsyncClient, so the test's OWN outer client -- which
# drives the real ASGI app over httpx.ASGITransport -- must keep a reference to the real class.
_RealAsyncClient = httpx.AsyncClient

_PROVIDER_CONFIG_JSON = json.dumps(
    [
        {
            "id": "provider.gpt-4o-mini",
            "backend": "openai_compatible",
            "base_url": "https://provider.test/v1",
            "model_name": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "capabilities": ["chat_completions"],
        }
    ]
)


class _FakeUpstreamClient:
    """Stands in for the real provider's httpx.AsyncClient -- the ONLY faked layer. Answers the
    FIRST call with a tool call, and the SECOND (continuation) call with a plain text answer,
    asserting the second call actually received the full prepended conversation history."""

    _call_count = 0

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
        assert url == "https://provider.test/v1/chat/completions"
        del headers
        type(self)._call_count += 1
        if type(self)._call_count == 1:
            assert json["messages"] == [
                {"role": "user", "content": "What is the weather in Paris?"}
            ]
            assert json["tools"][0]["function"]["name"] == "get_weather"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_contract_responses_1",
                    "object": "chat.completion",
                    "model": "gpt-4o-mini",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "tool_calls",
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_responses_contract_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_weather",
                                            "arguments": '{"location":"Paris"}',
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
                },
            )
        # Second call: the continuation. Assert the full history (user turn + assistant tool
        # call + tool result) was prepended by create_utility_conversation_response's
        # previous_response_id handling -- not just the new function_call_output item.
        assert json["messages"] == [
            {"role": "user", "content": "What is the weather in Paris?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_responses_contract_1",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"location":"Paris"}'},
                    }
                ],
            },
            {
                "role": "tool",
                "content": "15C, partly cloudy",
                "tool_call_id": "call_responses_contract_1",
            },
        ]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_contract_responses_2",
                "object": "chat.completion",
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "It is 15C and partly cloudy in Paris.",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 32, "completion_tokens": 10, "total_tokens": 42},
            },
        )


@pytest.mark.anyio
async def test_responses_typed_array_tool_call_and_continuation_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LLM_PROVIDER_MODELS_JSON", _PROVIDER_CONFIG_JSON)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm_provider_service.load_provider_model_configs.cache_clear()
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    _FakeUpstreamClient._call_count = 0

    transport = httpx.ASGITransport(app=app)
    async with _RealAsyncClient(transport=transport, base_url="http://testserver") as http_client:
        monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeUpstreamClient)
        try:
            first = await http_client.post(
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
                                "description": "Get the current weather for a location.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"location": {"type": "string"}},
                                    "required": ["location"],
                                },
                            },
                        }
                    ],
                    "tool_choice": "auto",
                },
            )
            assert first.status_code == 200
            first_body = first.json()
            assert first_body["object"] == "response"
            assert first_body["status"] == "completed"
            first_content = first_body["output"][0]["content"][0]
            assert first_content["text"] is None
            assert first_content["finish_reason"] == "tool_calls"
            assert first_content["tool_calls"] == [
                {
                    "id": "call_responses_contract_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"location":"Paris"}'},
                }
            ]
            response_id = first_body["id"]

            second = await http_client.post(
                "/v1/responses",
                json={
                    "model": "provider.gpt-4o-mini",
                    "input": [
                        {
                            "type": "function_call_output",
                            "call_id": "call_responses_contract_1",
                            "output": "15C, partly cloudy",
                        }
                    ],
                    "previous_response_id": response_id,
                },
            )
        finally:
            app.dependency_overrides.clear()
            llm_provider_service.load_provider_model_configs.cache_clear()

    assert second.status_code == 200
    second_body = second.json()
    second_content = second_body["output"][0]["content"][0]
    assert second_content["text"] == "It is 15C and partly cloudy in Paris."
    assert second_content["finish_reason"] == "stop"
    assert second_content["tool_calls"] is None
    assert second_body["usage"]["total_tokens"] == 42
