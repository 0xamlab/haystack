"""Track C2 (tool calling): a real contract test.

Every other tool-calling test in this repo asserts against OUR OWN JSON expectations. This file
drives the exact same /v1/chat/completions endpoint with the actual `openai` Python SDK (not a
hand-rolled httpx call), wired straight into the real ASGI app via httpx.ASGITransport -- no
network, no live server. If our response ever drifted from something the real SDK can parse into
ChatCompletion/ChatCompletionMessageToolCall, this is what would catch it: the master plan's own
stated verification bar for this track ("does a real OpenAI client library actually work against
this").

The only thing faked is the upstream provider HTTP call (monkeypatched httpx.AsyncClient, the same
technique test_llm_provider_service_provider_chat.py uses) -- everything else (auth override, rate
limit noop, router, create_chat_completion, routed_provider_chat_completion, provider_chat_completion,
payload building, response parsing, response schema construction) is the real code path.
"""
from __future__ import annotations

import json

import httpx
import pytest
from openai import AsyncOpenAI

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import llm as llm_router
from apps.api_server.services import llm_provider_service

from tests._test_llm_api_router_helpers import _fake_auth, _noop_rate_limit

# Captured before any monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", ...) --
# that patch replaces the GLOBAL httpx.AsyncClient (llm_provider_service.httpx IS the shared
# httpx module), so the test's OWN outer client -- which drives the real ASGI app over
# httpx.ASGITransport -- must keep a reference to the real class from before the patch.
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
    """Stands in for the real provider's httpx.AsyncClient (same technique as the golden-payload
    tests in test_llm_provider_service_provider_chat.py) -- the ONLY faked layer."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
        assert url == "https://provider.test/v1/chat/completions"
        assert json["tools"][0]["function"]["name"] == "get_weather"
        assert json["tool_choice"] == "auto"
        del headers
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_contract_test_1",
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
                                    "id": "call_contract_1",
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
                "usage": {"prompt_tokens": 18, "completion_tokens": 9, "total_tokens": 27},
            },
        )


@pytest.mark.anyio
async def test_openai_sdk_tool_calling_round_trip_through_router(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LLM_PROVIDER_MODELS_JSON", _PROVIDER_CONFIG_JSON)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm_provider_service.load_provider_model_configs.cache_clear()
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()

    transport = httpx.ASGITransport(app=app)
    async with _RealAsyncClient(transport=transport, base_url="http://testserver") as http_client:
        # Construct the real SDK client BEFORE patching llm_provider_service.httpx.AsyncClient --
        # openai's own __init__ does `isinstance(http_client, httpx.AsyncClient)`, which resolves
        # against the (then-patched) global httpx module attribute, so the patch must land after.
        client = AsyncOpenAI(
            api_key="sk-test-client-side-unused",
            base_url="http://testserver/v1",
            http_client=http_client,
        )
        monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeUpstreamClient)
        try:
            response = await client.chat.completions.create(
                model="provider.gpt-4o-mini",
                messages=[{"role": "user", "content": "What's the weather in Paris?"}],
                tools=[
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
                tool_choice="auto",
            )
        finally:
            app.dependency_overrides.clear()
            llm_provider_service.load_provider_model_configs.cache_clear()

    # The real `openai` package's own typed response models -- ChatCompletion, Choice,
    # ChatCompletionMessage, ChatCompletionMessageToolCall -- parsed our JSON without complaint.
    assert response.id == "chatcmpl_contract_test_1"
    assert len(response.choices) == 1
    choice = response.choices[0]
    assert choice.finish_reason == "tool_calls"
    message = choice.message
    assert message.content is None
    assert message.tool_calls is not None
    assert len(message.tool_calls) == 1
    tool_call = message.tool_calls[0]
    assert tool_call.type == "function"
    assert tool_call.function.name == "get_weather"
    assert json.loads(tool_call.function.arguments) == {"location": "Paris"}
    assert response.usage.prompt_tokens == 18
    assert response.usage.completion_tokens == 9
    assert response.usage.total_tokens == 27
