"""Track C2 (real per-backend streaming): provider_chat_completion_stream end-to-end.

Same technique as test_llm_provider_service_provider_chat.py's golden-payload tests -- the ONLY
faked layer is the upstream httpx.AsyncClient -- but here it fakes `.stream(...)` (an async
context manager) instead of `.post(...)`, proving the real request-building
(payload["stream"]=True, stream_options for openai-shaped), the real egress-guarded connection
open, and the real per-backend normalizer all wire together correctly.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


class _FakeStreamResponse:
    def __init__(self, *, status_code: int, lines: list[str], body: bytes = b"") -> None:
        self.status_code = status_code
        self._lines = lines
        self._body = body

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._body


class _FakeStreamCtx:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *exc) -> bool:
        return False


class _FakeStreamingClient:
    """Captures the single `.stream(...)` call's method/url/json/headers for assertion, and
    returns a canned SSE-line response."""

    captured: dict[str, object] = {}
    response: _FakeStreamResponse | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def stream(self, method: str, url: str, *, json: dict[str, object], headers: dict[str, str]):
        type(self).captured = {"method": method, "url": url, "json": json, "headers": headers}
        return _FakeStreamCtx(type(self).response)


@pytest.mark.anyio
async def test_provider_chat_completion_stream_openai_shaped_real_incremental_chunks(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    sse_lines = [
        'data: {"id":"chatcmpl_stream_1","choices":[{"index":0,"delta":{"role":"assistant"},'
        '"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_stream_1","choices":[{"index":0,"delta":{"content":"Hel"},'
        '"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_stream_1","choices":[{"index":0,"delta":{"content":"lo"},'
        '"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_stream_1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
        "",
        'data: {"id":"chatcmpl_stream_1","choices":[],'
        '"usage":{"prompt_tokens":6,"completion_tokens":2,"total_tokens":8}}',
        "",
        "data: [DONE]",
        "",
    ]
    _FakeStreamingClient.response = _FakeStreamResponse(status_code=200, lines=sse_lines)
    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeStreamingClient)

    events = [
        event
        async for event in llm_provider_service.provider_chat_completion_stream(
            config=config,
            messages=[{"role": "user", "content": "hi"}],
        )
    ]

    assert _FakeStreamingClient.captured["method"] == "POST"
    assert _FakeStreamingClient.captured["url"] == "https://provider.test/v1/chat/completions"
    sent_payload = _FakeStreamingClient.captured["json"]
    assert sent_payload["stream"] is True
    assert sent_payload["stream_options"] == {"include_usage": True}
    assert sent_payload["messages"] == [{"role": "user", "content": "hi"}]

    assert events == [
        {"id": "chatcmpl_stream_1"},
        {"id": "chatcmpl_stream_1", "content": "Hel"},
        {"id": "chatcmpl_stream_1", "content": "lo"},
        {"id": "chatcmpl_stream_1", "finish_reason": "stop"},
        {
            "id": "chatcmpl_stream_1",
            "usage": {
                "prompt_tokens": 6,
                "completion_tokens": 2,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        },
    ]


@pytest.mark.anyio
async def test_provider_chat_completion_stream_anthropic_real_incremental_chunks(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.claude-sonnet",
        backend="anthropic",
        base_url="https://api.anthropic.com/v1",
        upstream_model="claude-3-5-sonnet-latest",
        api_key_env="ANTHROPIC_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak-test")

    sse_lines = [
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_stream_1","usage":'
        '{"input_tokens":7,"output_tokens":1}}}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi"}}',
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},'
        '"usage":{"output_tokens":4}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    ]
    _FakeStreamingClient.response = _FakeStreamResponse(status_code=200, lines=sse_lines)
    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeStreamingClient)

    events = [
        event
        async for event in llm_provider_service.provider_chat_completion_stream(
            config=config,
            messages=[{"role": "user", "content": "hi"}],
        )
    ]

    assert _FakeStreamingClient.captured["method"] == "POST"
    assert _FakeStreamingClient.captured["url"] == "https://api.anthropic.com/v1/messages"
    sent_payload = _FakeStreamingClient.captured["json"]
    assert sent_payload["stream"] is True
    assert "stream_options" not in sent_payload
    assert _FakeStreamingClient.captured["headers"]["x-api-key"] == "ak-test"

    assert events == [
        {"id": "msg_stream_1"},
        {"content": "Hi"},
        {
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 4,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        },
    ]


@pytest.mark.anyio
async def test_provider_chat_completion_stream_maps_error_status_before_any_chunk(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _FakeStreamingClient.response = _FakeStreamResponse(
        status_code=429, lines=[], body=b'{"error": {"message": "rate limited"}}'
    )
    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeStreamingClient)

    with pytest.raises(LLMAPIError) as exc_info:
        async for _ in llm_provider_service.provider_chat_completion_stream(
            config=config,
            messages=[{"role": "user", "content": "hi"}],
        ):
            pass
    assert exc_info.value.code == "provider_rate_limited"


@pytest.mark.anyio
async def test_provider_chat_completion_stream_meters_usage_on_completion(monkeypatch) -> None:
    """The usage from the terminal event is what gets metered -- proves the finally-block
    relocation (vs the non-streaming path's post-await metering) carries the real numbers."""
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    sse_lines = [
        'data: {"id":"c1","choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":"stop"}]}',
        "",
        'data: {"id":"c1","choices":[],"usage":{"prompt_tokens":9,"completion_tokens":3,'
        '"total_tokens":12}}',
        "",
        "data: [DONE]",
        "",
    ]
    _FakeStreamingClient.response = _FakeStreamResponse(status_code=200, lines=sse_lines)
    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeStreamingClient)

    metered: dict[str, object] = {}

    async def _fake_meter(**kwargs):
        metered.update(kwargs)

    async def _fake_gate(**kwargs):
        del kwargs

    from apps.api_server.services import llm_spend_service

    monkeypatch.setattr(llm_spend_service, "meter_managed_llm_call", _fake_meter)
    monkeypatch.setattr(llm_spend_service, "gate_managed_llm_call", _fake_gate)

    events = [
        event
        async for event in llm_provider_service.provider_chat_completion_stream(
            config=config,
            messages=[{"role": "user", "content": "hi"}],
        )
    ]
    assert events  # sanity: the stream actually produced something

    assert metered["backend"] == "openai_compatible"
    assert metered["model"] == "provider.gpt-4o-mini"
    assert metered["prompt_tokens"] == 9
    assert metered["completion_tokens"] == 3
