"""Real per-backend chat-completions stream normalizers (Track C2, 2026-08).

Each function here takes the RAW upstream SSE line stream (an ``AsyncIterator[str]``, e.g.
``httpx.Response.aiter_lines()``) for one specific provider family and yields our own internal,
provider-agnostic stream-event dicts as the upstream generates them -- never buffering the full
body. Each yielded dict has exactly these keys, present only when this event actually carries
that piece of information (a dict with everything empty is never yielded):

    {
        "id": str | None,             # the upstream's own completion id, when this event has one
        "content": str | None,        # an incremental text delta
        "tool_calls": list[dict] | None,  # OpenAI-shaped incremental tool_calls deltas: each
                                       # item is {"index": int, "id"?: str, "type"?: "function",
                                       #  "function": {"name"?: str, "arguments"?: str}} --
                                       # matching OpenAI's real streaming tool-call wire format
                                       # exactly, so a real OpenAI SDK client can accumulate it
                                       # unchanged.
        "finish_reason": str | None,  # one of "stop"/"tool_calls"/"length"/"content_filter"
        "usage": dict | None,         # {"prompt_tokens", "completion_tokens", "cache_read_tokens",
                                       #  "cache_write_tokens"} -- present only on the terminal
                                       # event(s) that actually carry usage.
    }

Callers (apps/api_server/services/llm_provider_service/_http_layer.py's
_provider_post_json_stream) pick the right normalizer per config.backend and forward these dicts
upward unchanged; the router assembles them into our own `chat.completion.chunk` SSE frames.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from apps.api_server.services.llm_provider_service._response_parsing import (
    _anthropic_finish_reason,
    _normalize_openai_shaped_finish_reason,
)

# ─── openai-shaped family: openai, openai_compatible, groq, xai, mistral ──────────────────────
#
# All five speak the identical Chat Completions streaming wire format: `data: {...}\n\n` SSE
# lines, each a full `chat.completion.chunk`-shaped JSON object, terminated by a literal
# `data: [DONE]` line. Usage arrives as one extra terminal chunk with an EMPTY `choices` array
# when the request set `stream_options: {"include_usage": true}` (see _chat_api.py).


def _openai_usage_from_payload(raw_usage: dict[str, Any]) -> dict[str, int]:
    prompt_tokens = int(raw_usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(raw_usage.get("completion_tokens", 0) or 0)
    # Some openai-compatible backends surface Anthropic-style prompt-cache accounting under a
    # `prompt_tokens_details` object; degrade to 0 (never fail the stream) when absent/malformed.
    details = raw_usage.get("prompt_tokens_details")
    cache_read_tokens = 0
    if isinstance(details, dict):
        cache_read_tokens = int(details.get("cached_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": 0,
    }


async def parse_openai_shaped_stream(
    lines: AsyncIterator[str],
) -> AsyncIterator[dict[str, Any]]:
    """Normalize an openai-shaped Chat Completions SSE stream (openai / openai_compatible /
    groq / xai / mistral) into our internal stream-event dicts."""
    async for raw_line in lines:
        line = raw_line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        try:
            payload = json.loads(data)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue

        event: dict[str, Any] = {}
        completion_id = payload.get("id")
        if isinstance(completion_id, str) and completion_id:
            event["id"] = completion_id

        raw_usage = payload.get("usage")
        if isinstance(raw_usage, dict):
            event["usage"] = _openai_usage_from_payload(raw_usage)

        choices = payload.get("choices") or []
        if choices:
            choice = choices[0]
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str) and content:
                event["content"] = content

            raw_tool_calls = delta.get("tool_calls")
            if raw_tool_calls:
                tool_calls: list[dict[str, Any]] = []
                for item in raw_tool_calls:
                    function = item.get("function") or {}
                    tool_call: dict[str, Any] = {"index": item.get("index", 0)}
                    if item.get("id"):
                        tool_call["id"] = item["id"]
                    if item.get("type"):
                        tool_call["type"] = item["type"]
                    function_delta: dict[str, Any] = {}
                    if function.get("name"):
                        function_delta["name"] = function["name"]
                    if "arguments" in function:
                        function_delta["arguments"] = function.get("arguments") or ""
                    if function_delta:
                        tool_call["function"] = function_delta
                    tool_calls.append(tool_call)
                event["tool_calls"] = tool_calls

            raw_finish_reason = choice.get("finish_reason")
            if raw_finish_reason:
                event["finish_reason"] = _normalize_openai_shaped_finish_reason(raw_finish_reason)

        if event:
            yield event


# ─── anthropic ─────────────────────────────────────────────────────────────────────────────────
#
# Verified 2026-08-30 against the live Messages API streaming docs
# (https://platform.claude.com/docs/en/build-with-claude/streaming, redirected from
# docs.claude.com/en/api/messages-streaming) via a direct fetch during this change -- NOT from
# training-data recall. Confirmed event flow + exact field names used below:
#   message_start       -> data.message.id, data.message.usage.{input_tokens,output_tokens,
#                           cache_creation_input_tokens?,cache_read_input_tokens?}
#   content_block_start -> data.index, data.content_block.type ("text"|"tool_use"|"thinking"|...),
#                           and for "tool_use": data.content_block.{id,name}
#   content_block_delta -> data.index, data.delta.type ("text_delta"|"input_json_delta"|
#                           "thinking_delta"|"signature_delta"), with data.delta.text /
#                           data.delta.partial_json respectively
#   content_block_stop  -> data.index
#   message_delta       -> data.delta.stop_reason, data.usage.output_tokens (CUMULATIVE; the docs
#                           explicitly warn of this), optionally input_tokens/cache_*_input_tokens
#   message_stop        -> no payload of interest
#   ping                -> ignored
#   error               -> data.error.message
# "thinking"/"signature_delta" blocks have no OpenAI-compatible equivalent and are intentionally
# not surfaced (this normalizer only fills the OpenAI-compatible content/tool_calls shape).


async def parse_anthropic_stream(
    lines: AsyncIterator[str],
) -> AsyncIterator[dict[str, Any]]:
    """Normalize an Anthropic Messages API SSE stream into our internal stream-event dicts."""
    from apps.api_server.services.llm_api_service import LLMAPIError

    current_event: str | None = None
    tool_call_index_by_block_index: dict[int, int] = {}
    next_tool_call_index = 0
    saw_tool_use = False
    baseline_prompt_tokens = 0
    baseline_cache_read_tokens = 0
    baseline_cache_write_tokens = 0

    async for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
            continue
        if not line.startswith("data:"):
            continue
        raw = line[len("data:") :].strip()
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue

        if current_event == "message_start":
            message = payload.get("message") or {}
            usage = message.get("usage") or {}
            baseline_prompt_tokens = int(usage.get("input_tokens", 0) or 0)
            baseline_cache_read_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
            baseline_cache_write_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
            message_id = message.get("id")
            if isinstance(message_id, str) and message_id:
                yield {"id": message_id}
            continue

        if current_event == "content_block_start":
            block = payload.get("content_block") or {}
            if block.get("type") == "tool_use":
                saw_tool_use = True
                block_index = payload.get("index", 0)
                tool_index = next_tool_call_index
                next_tool_call_index += 1
                tool_call_index_by_block_index[block_index] = tool_index
                yield {
                    "tool_calls": [
                        {
                            "index": tool_index,
                            "id": block.get("id"),
                            "type": "function",
                            "function": {"name": block.get("name"), "arguments": ""},
                        }
                    ]
                }
            continue

        if current_event == "content_block_delta":
            delta = payload.get("delta") or {}
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                text = delta.get("text")
                if text:
                    yield {"content": text}
            elif delta_type == "input_json_delta":
                block_index = payload.get("index", 0)
                tool_index = tool_call_index_by_block_index.get(block_index, 0)
                partial_json = delta.get("partial_json", "")
                yield {
                    "tool_calls": [
                        {"index": tool_index, "function": {"arguments": partial_json}}
                    ]
                }
            # thinking_delta / signature_delta / anything future: no OpenAI-compatible
            # equivalent -- intentionally dropped rather than guessed at.
            continue

        if current_event == "content_block_stop":
            continue

        if current_event == "message_delta":
            delta = payload.get("delta") or {}
            usage = payload.get("usage") or {}
            event: dict[str, Any] = {}
            stop_reason = delta.get("stop_reason")
            if stop_reason is not None:
                event["finish_reason"] = (
                    "tool_calls" if saw_tool_use else _anthropic_finish_reason(stop_reason)
                )
            if usage:
                event["usage"] = {
                    "prompt_tokens": int(usage.get("input_tokens", baseline_prompt_tokens) or 0),
                    "completion_tokens": int(usage.get("output_tokens", 0) or 0),
                    "cache_read_tokens": int(
                        usage.get("cache_read_input_tokens", baseline_cache_read_tokens) or 0
                    ),
                    "cache_write_tokens": int(
                        usage.get("cache_creation_input_tokens", baseline_cache_write_tokens) or 0
                    ),
                }
            if event:
                yield event
            continue

        if current_event == "message_stop":
            return

        if current_event == "error":
            error = payload.get("error") or {}
            message = error.get("message") or "Anthropic streaming error."
            raise LLMAPIError(
                "provider_backend_error",
                f"Provider backend returned a streaming error: {message}",
                {"backend": "anthropic", "provider_error": error},
            )

        # ping / any other/future named event: ignored.
        continue
