"""Track C2 (real streaming): golden-fixture tests for _streaming.py's normalizers.

Each test feeds a real-shaped SSE fixture (byte-for-byte modeled on the provider's own published
wire format) through the normalizer and asserts the EXACT sequence of internal stream-event dicts
it produces, including tool-call argument accumulation across chunks.
"""
from __future__ import annotations

import pytest

from apps.api_server.services.llm_api_service import LLMAPIError
from apps.api_server.services.llm_provider_service._streaming import (
    parse_anthropic_stream,
    parse_openai_shaped_stream,
)


async def _lines(*raw: str):
    for line in raw:
        yield line


# ─── openai-shaped family ──────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_parse_openai_shaped_stream_text_deltas_and_final_usage() -> None:
    stream = _lines(
        'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":'
        '[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":'
        '[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":'
        '[{"index":0,"delta":{"content":" there"},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":'
        '[{"index":0,"delta":{},"finish_reason":"stop"}]}',
        "",
        'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":[],'
        '"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}',
        "",
        "data: [DONE]",
        "",
    )
    events = [event async for event in parse_openai_shaped_stream(stream)]
    assert events == [
        {"id": "chatcmpl_1"},
        {"id": "chatcmpl_1", "content": "Hello"},
        {"id": "chatcmpl_1", "content": " there"},
        {"id": "chatcmpl_1", "finish_reason": "stop"},
        {
            "id": "chatcmpl_1",
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        },
    ]


@pytest.mark.anyio
async def test_parse_openai_shaped_stream_accumulates_tool_call_argument_chunks() -> None:
    stream = _lines(
        'data: {"id":"chatcmpl_2","choices":[{"index":0,"delta":{"tool_calls":'
        '[{"index":0,"id":"call_abc","type":"function","function":{"name":"get_weather",'
        '"arguments":""}}]},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_2","choices":[{"index":0,"delta":{"tool_calls":'
        '[{"index":0,"function":{"arguments":"{\\"location\\":"}}]},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_2","choices":[{"index":0,"delta":{"tool_calls":'
        '[{"index":0,"function":{"arguments":"\\"Paris\\"}"}}]},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_2","choices":[{"index":0,"delta":{},'
        '"finish_reason":"tool_calls"}]}',
        "",
        "data: [DONE]",
        "",
    )
    events = [event async for event in parse_openai_shaped_stream(stream)]
    assert events == [
        {
            "id": "chatcmpl_2",
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_abc",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": ""},
                }
            ],
        },
        {
            "id": "chatcmpl_2",
            "tool_calls": [{"index": 0, "function": {"arguments": '{"location":'}}],
        },
        {
            "id": "chatcmpl_2",
            "tool_calls": [{"index": 0, "function": {"arguments": '"Paris"}'}}],
        },
        {"id": "chatcmpl_2", "finish_reason": "tool_calls"},
    ]
    # Reassembling the accumulated argument chunks in order recovers valid, complete JSON --
    # exactly what a real OpenAI SDK client does client-side.
    accumulated = "".join(
        tc["function"]["arguments"]
        for event in events
        for tc in event.get("tool_calls", [])
        if "arguments" in tc.get("function", {})
    )
    assert accumulated == '{"location":"Paris"}'


@pytest.mark.anyio
async def test_parse_openai_shaped_stream_ignores_malformed_json_line() -> None:
    stream = _lines("data: {not json", "", "data: [DONE]", "")
    events = [event async for event in parse_openai_shaped_stream(stream)]
    assert events == []


@pytest.mark.anyio
async def test_parse_openai_shaped_stream_stops_at_done_even_with_trailing_lines() -> None:
    stream = _lines(
        "data: [DONE]",
        "",
        'data: {"id":"chatcmpl_after_done","choices":[{"index":0,"delta":{"content":"late"}}]}',
        "",
    )
    events = [event async for event in parse_openai_shaped_stream(stream)]
    assert events == []


# ─── anthropic ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_parse_anthropic_stream_text_only_matches_live_docs_example() -> None:
    """Byte-for-byte modeled on the live Messages API streaming docs' own basic-text example."""
    stream = _lines(
        "event: message_start",
        'data: {"type": "message_start", "message": {"id": "msg_1nZdL29xx5MUA1yADyHTEsnR8uuvGzszyY", '
        '"type": "message", "role": "assistant", "content": [], "model": "claude-opus-5", '
        '"stop_reason": null, "stop_sequence": null, "usage": {"input_tokens": 25, "output_tokens": 1}}}',
        "",
        "event: content_block_start",
        'data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}',
        "",
        "event: ping",
        'data: {"type": "ping"}',
        "",
        "event: content_block_delta",
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}',
        "",
        "event: content_block_delta",
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "!"}}',
        "",
        "event: content_block_stop",
        'data: {"type": "content_block_stop", "index": 0}',
        "",
        "event: message_delta",
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence":null}, '
        '"usage": {"output_tokens": 15}}',
        "",
        "event: message_stop",
        'data: {"type": "message_stop"}',
        "",
    )
    events = [event async for event in parse_anthropic_stream(stream)]
    assert events == [
        {"id": "msg_1nZdL29xx5MUA1yADyHTEsnR8uuvGzszyY"},
        {"content": "Hello"},
        {"content": "!"},
        {
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 15,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        },
    ]


@pytest.mark.anyio
async def test_parse_anthropic_stream_tool_use_matches_live_docs_example() -> None:
    """Byte-for-byte modeled on the live Messages API streaming docs' own tool-use example
    (text block index 0 followed by a tool_use block index 1)."""
    stream = _lines(
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_014p7gG3wDgGV9EUtLvnow3U","type":"message",'
        '"role":"assistant","model":"claude-opus-5","stop_sequence":null,'
        '"usage":{"input_tokens":472,"output_tokens":2},"content":[],"stop_reason":null}}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Okay,"}}',
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use",'
        '"id":"toolu_01T1x1fJ34qAmk2tNTrN7Up6","name":"get_weather","input":{}}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":""}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta",'
        '"partial_json":"{\\"location\\":"}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta",'
        '"partial_json":" \\"San Francisco, CA\\"}"}}',
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":1}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},'
        '"usage":{"output_tokens":89}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    )
    events = [event async for event in parse_anthropic_stream(stream)]
    assert events == [
        {"id": "msg_014p7gG3wDgGV9EUtLvnow3U"},
        {"content": "Okay,"},
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "toolu_01T1x1fJ34qAmk2tNTrN7Up6",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": ""},
                }
            ]
        },
        {"tool_calls": [{"index": 0, "function": {"arguments": ""}}]},
        {"tool_calls": [{"index": 0, "function": {"arguments": '{"location":'}}]},
        {"tool_calls": [{"index": 0, "function": {"arguments": ' "San Francisco, CA"}'}}]},
        {
            # A tool_use block was opened this turn, so finish_reason normalizes to
            # "tool_calls" even though Anthropic's own stop_reason says "tool_use".
            "finish_reason": "tool_calls",
            "usage": {
                "prompt_tokens": 472,
                "completion_tokens": 89,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        },
    ]
    accumulated = "".join(
        tc["function"]["arguments"]
        for event in events
        for tc in event.get("tool_calls", [])
        if "arguments" in tc.get("function", {})
    )
    assert accumulated == '{"location": "San Francisco, CA"}'


@pytest.mark.anyio
async def test_parse_anthropic_stream_prompt_cache_usage_from_message_start() -> None:
    """Cache-read/write token counts live on message_start's usage, not message_delta's --
    message_delta only repeats output_tokens (cumulative) in the common case."""
    stream = _lines(
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_cache_1","usage":'
        '{"input_tokens":7,"output_tokens":1,"cache_read_input_tokens":11,'
        '"cache_creation_input_tokens":5}}}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hi"}}',
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
    )
    events = [event async for event in parse_anthropic_stream(stream)]
    assert events[-1] == {
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 7,
            "completion_tokens": 4,
            "cache_read_tokens": 11,
            "cache_write_tokens": 5,
        },
    }


@pytest.mark.anyio
async def test_parse_anthropic_stream_error_event_raises_llm_api_error() -> None:
    stream = _lines(
        "event: error",
        'data: {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}',
        "",
    )

    with pytest.raises(LLMAPIError) as exc_info:
        async for _ in parse_anthropic_stream(stream):
            pass
    assert exc_info.value.code == "provider_backend_error"
    assert "Overloaded" in exc_info.value.message


@pytest.mark.anyio
async def test_parse_anthropic_stream_ignores_thinking_and_ping_events() -> None:
    stream = _lines(
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_think_1","usage":'
        '{"input_tokens":3,"output_tokens":1}}}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking",'
        '"thinking":"","signature":""}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta",'
        '"thinking":"reasoning..."}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta",'
        '"signature":"sig"}}',
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":0}',
        "",
        "event: content_block_start",
        'data: {"type":"content_block_start","index":1,"content_block":{"type":"text","text":""}}',
        "",
        "event: ping",
        'data: {"type": "ping"}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"answer"}}',
        "",
        "event: content_block_stop",
        'data: {"type":"content_block_stop","index":1}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},'
        '"usage":{"output_tokens":9}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    )
    events = [event async for event in parse_anthropic_stream(stream)]
    assert events == [
        {"id": "msg_think_1"},
        {"content": "answer"},
        {
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 9,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            },
        },
    ]
