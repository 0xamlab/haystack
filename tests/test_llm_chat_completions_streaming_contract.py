"""Track C2 (real per-backend streaming): a real contract test for the streaming path.

Same technique as test_llm_chat_completions_tool_calling_contract.py: drives the actual
/v1/chat/completions endpoint with the real `openai` Python SDK (not a hand-rolled httpx call),
wired into the real ASGI app via httpx.ASGITransport -- no network, no live server. The only
faked layer is the upstream provider's HTTP connection (its `.stream(...)` call, monkeypatched
the same way the non-streaming contract test fakes `.post(...)`) -- everything else (auth
override, rate limit noop, router resolution, egress-guarded connection open, the real SSE
normalizer, the real chunk-assembly/SSE-framing code) is the real code path.

Asserts MULTIPLE chunks arrive over the SDK's async stream (proving this is real incremental
delivery, not one buffered response sliced after the fact) and that the accumulated text matches
the upstream's real per-chunk deltas exactly.
"""
from __future__ import annotations

import json

import httpx
import pytest

AsyncOpenAI = pytest.importorskip("openai").AsyncOpenAI

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import llm as llm_router
from apps.api_server.services import llm_provider_service

from tests._test_llm_api_router_helpers import _fake_auth, _noop_rate_limit

# Captured before any monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", ...) -- see
# test_llm_chat_completions_tool_calling_contract.py for why this must be captured up front.
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

_SSE_LINES = [
    'data: {"id":"chatcmpl_contract_stream_1","object":"chat.completion.chunk","choices":'
    '[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
    "",
    'data: {"id":"chatcmpl_contract_stream_1","object":"chat.completion.chunk","choices":'
    '[{"index":0,"delta":{"content":"The weather "},"finish_reason":null}]}',
    "",
    'data: {"id":"chatcmpl_contract_stream_1","object":"chat.completion.chunk","choices":'
    '[{"index":0,"delta":{"content":"in Paris "},"finish_reason":null}]}',
    "",
    'data: {"id":"chatcmpl_contract_stream_1","object":"chat.completion.chunk","choices":'
    '[{"index":0,"delta":{"content":"is sunny."},"finish_reason":null}]}',
    "",
    'data: {"id":"chatcmpl_contract_stream_1","object":"chat.completion.chunk","choices":'
    '[{"index":0,"delta":{},"finish_reason":"stop"}]}',
    "",
    'data: {"id":"chatcmpl_contract_stream_1","object":"chat.completion.chunk","choices":[],'
    '"usage":{"prompt_tokens":9,"completion_tokens":6,"total_tokens":15}}',
    "",
    "data: [DONE]",
    "",
]


class _FakeStreamResponse:
    status_code = 200

    async def aiter_lines(self):
        for line in _SSE_LINES:
            yield line

    async def aread(self) -> bytes:
        return b"{}"


class _FakeStreamCtx:
    async def __aenter__(self) -> _FakeStreamResponse:
        return _FakeStreamResponse()

    async def __aexit__(self, *exc) -> bool:
        return False


class _FakeUpstreamClient:
    """Stands in for the real provider's httpx.AsyncClient -- the ONLY faked layer."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def stream(self, method: str, url: str, *, json: dict[str, object], headers: dict[str, str]):
        assert method == "POST"
        assert url == "https://provider.test/v1/chat/completions"
        assert json["stream"] is True
        assert json["stream_options"] == {"include_usage": True}
        del headers
        return _FakeStreamCtx()


@pytest.mark.anyio
async def test_openai_sdk_streaming_round_trip_delivers_multiple_real_chunks(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LLM_PROVIDER_MODELS_JSON", _PROVIDER_CONFIG_JSON)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm_provider_service.load_provider_model_configs.cache_clear()
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()

    transport = httpx.ASGITransport(app=app)
    async with _RealAsyncClient(transport=transport, base_url="http://testserver") as http_client:
        client = AsyncOpenAI(
            api_key="sk-test-client-side-unused",
            base_url="http://testserver/v1",
            http_client=http_client,
        )
        monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeUpstreamClient)
        try:
            stream = await client.chat.completions.create(
                model="provider.gpt-4o-mini",
                messages=[{"role": "user", "content": "What's the weather in Paris?"}],
                stream=True,
            )
            chunks = [chunk async for chunk in stream]
        finally:
            app.dependency_overrides.clear()
            llm_provider_service.load_provider_model_configs.cache_clear()

    # Real incremental delivery: more than one chunk, each parsed by the real openai SDK's own
    # ChatCompletionChunk model -- proves this is NOT one buffered response sliced after the fact.
    assert len(chunks) > 3
    for chunk in chunks:
        assert chunk.id == "chatcmpl_contract_stream_1"
        assert chunk.object == "chat.completion.chunk"

    content_deltas = [
        chunk.choices[0].delta.content
        for chunk in chunks
        if chunk.choices and chunk.choices[0].delta.content
    ]
    assert content_deltas == ["The weather ", "in Paris ", "is sunny."]
    assert "".join(content_deltas) == "The weather in Paris is sunny."

    finish_reasons = [
        chunk.choices[0].finish_reason
        for chunk in chunks
        if chunk.choices and chunk.choices[0].finish_reason
    ]
    assert finish_reasons == ["stop"]


@pytest.mark.anyio
async def test_streaming_contract_raw_sse_frames_preserve_existing_shape(monkeypatch) -> None:
    """Byte-level check (below the SDK's own parsing) that the SSE framing contract -- role
    chunk, content-delta chunks, terminal finish_reason chunk, [DONE] -- is unchanged."""
    monkeypatch.setenv("ALGENTA_LLM_PROVIDER_MODELS_JSON", _PROVIDER_CONFIG_JSON)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm_provider_service.load_provider_model_configs.cache_clear()
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeUpstreamClient)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()

    transport = httpx.ASGITransport(app=app)
    try:
        async with _RealAsyncClient(transport=transport, base_url="http://testserver") as http_client:
            async with http_client.stream(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                body = b"".join([chunk async for chunk in response.aiter_bytes()]).decode("utf-8")
    finally:
        app.dependency_overrides.clear()
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert '"role":"assistant"' in body
    assert '"content":"The weather "' in body
    assert '"finish_reason":"stop"' in body
    assert body.strip().endswith("data: [DONE]")
    # Real streaming, not the synthetic fixed-size slicer: the fixed-size chunker never emits a
    # bare content delta shorter than _STREAM_CHUNK_SIZE except as its last piece, whereas here
    # each upstream-sized delta ("The weather ", "in Paris ", "is sunny.") appears verbatim.
    assert '"content":"is sunny."' in body
