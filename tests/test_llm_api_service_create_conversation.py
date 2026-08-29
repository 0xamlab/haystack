"""Tests for llm_api_service.create_utility_conversation_response (Track C1a: responses protocol
core -- the typed OpenResponses-shaped input-array path, a real multi-turn conversation, as
opposed to create_utility_response's per-string independent completions)."""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


def _provider_chat_descriptor(model_id: str = "provider.gpt-4o-mini"):
    return llm_api_service.LLMModelDescriptor(
        model_id=model_id,
        runtime_module="provider.openai_compatible",
        description="Provider-backed chat model.",
        capabilities=("chat_completions", "embeddings"),
        supported_endpoints=(
            "/v1/models",
            "/v1/chat/completions",
            "/v1/embeddings",
            "/v1/responses",
        ),
        tokenizer_kind=None,
        similarity_metric=None,
        runtime_functions=(),
        available=True,
        provider_backend="openai_compatible",
    )


def test_messages_from_typed_input_items_maps_each_item_type() -> None:
    messages = llm_api_service._messages_from_typed_input_items(
        [
            {"type": "message", "role": "user", "content": "What is the weather in Paris?"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "get_weather",
                "arguments": '{"location":"Paris"}',
            },
            {"type": "function_call_output", "call_id": "call_1", "output": "15C, sunny"},
        ]
    )

    assert messages == [
        {"role": "user", "content": "What is the weather in Paris?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"location":"Paris"}'},
                }
            ],
        },
        {"role": "tool", "content": "15C, sunny", "tool_call_id": "call_1"},
    ]


def test_messages_from_typed_input_items_joins_input_text_parts() -> None:
    messages = llm_api_service._messages_from_typed_input_items(
        [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Part one. "},
                    {"type": "input_text", "text": "Part two."},
                ],
            }
        ]
    )

    assert messages == [{"role": "user", "content": "Part one. Part two."}]


def test_messages_from_typed_input_items_rejects_unknown_type() -> None:
    with pytest.raises(LLMAPIError) as exc_info:
        llm_api_service._messages_from_typed_input_items([{"type": "not_real"}])
    assert exc_info.value.code == "invalid_provider_request"


@pytest.mark.anyio
async def test_create_utility_conversation_response_requires_chat_completions_capability(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="text.tokenizer",
            description="Tokenizer only.",
            capabilities=("tokenize",),
            supported_endpoints=("/v1/models", "/v1/tokenize"),
            tokenizer_kind="word",
            similarity_metric=None,
            runtime_functions=("word_tokenize",),
            available=True,
        ),
    )

    with pytest.raises(LLMAPIError) as exc_info:
        await llm_api_service.create_utility_conversation_response(
            model_id="text.tokenizer",
            items=[{"type": "message", "role": "user", "content": "hi"}],
        )
    assert exc_info.value.code == "model_capability_unsupported"


@pytest.mark.anyio
async def test_create_utility_conversation_response_returns_single_item_with_tool_call(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        llm_api_service, "get_llm_model_descriptor", lambda model_id: _provider_chat_descriptor(model_id)
    )

    captured: dict[str, object] = {}

    async def _fake_create_chat_completion(*, model_id: str, messages: list[dict], **tool_kwargs):
        captured["messages"] = messages
        captured["tool_kwargs"] = tool_kwargs
        return (
            _provider_chat_descriptor(model_id),
            llm_api_service.ChatCompletionResult(
                completion_id="chatcmpl_conv_1",
                content=None,
                prompt_tokens=12,
                completion_tokens=6,
                provider=llm_api_service.ProviderExecutionMetadata(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                ),
                tool_calls=(
                    llm_api_service.ChatCompletionToolCall(
                        id="call_1",
                        function=llm_api_service.ChatCompletionToolCallFunction(
                            name="get_weather", arguments='{"location":"Paris"}'
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
        )

    monkeypatch.setattr(llm_api_service, "create_chat_completion", _fake_create_chat_completion)

    descriptor, response_id, outputs, total_tokens = (
        await llm_api_service.create_utility_conversation_response(
            model_id="provider.gpt-4o-mini",
            items=[
                {"type": "message", "role": "user", "content": "What is the weather in Paris?"}
            ],
            tools=[{"type": "function", "function": {"name": "get_weather"}}],
            tool_choice="auto",
        )
    )

    assert descriptor.model_id == "provider.gpt-4o-mini"
    assert response_id.startswith("resp_")
    assert total_tokens == 18
    assert len(outputs) == 1
    item = outputs[0]
    assert item.index == 0
    assert item.text is None
    assert item.finish_reason == "tool_calls"
    assert item.tool_calls[0].function.name == "get_weather"
    assert captured["messages"] == [
        {"role": "user", "content": "What is the weather in Paris?"},
    ]
    assert captured["tool_kwargs"] == {
        "tools": [{"type": "function", "function": {"name": "get_weather"}}],
        "tool_choice": "auto",
    }


@pytest.mark.anyio
async def test_create_utility_conversation_response_continues_previous_response_id(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        llm_api_service, "get_llm_model_descriptor", lambda model_id: _provider_chat_descriptor(model_id)
    )

    calls: list[list[dict]] = []

    async def _fake_create_chat_completion(*, model_id: str, messages: list[dict]):
        calls.append(messages)
        if len(calls) == 1:
            content = None
        else:
            content = "It is 15C and sunny in Paris."
        return (
            _provider_chat_descriptor(model_id),
            llm_api_service.ChatCompletionResult(
                completion_id=f"chatcmpl_conv_{len(calls)}",
                content=content,
                prompt_tokens=10,
                completion_tokens=5,
                tool_calls=(
                    (
                        llm_api_service.ChatCompletionToolCall(
                            id="call_1",
                            function=llm_api_service.ChatCompletionToolCallFunction(
                                name="get_weather", arguments='{"location":"Paris"}'
                            ),
                        ),
                    )
                    if len(calls) == 1
                    else None
                ),
                finish_reason="tool_calls" if len(calls) == 1 else "stop",
            ),
        )

    monkeypatch.setattr(llm_api_service, "create_chat_completion", _fake_create_chat_completion)

    # Turn 1: no previous_response_id -- model calls a tool.
    descriptor, response_id_1, outputs_1, _ = (
        await llm_api_service.create_utility_conversation_response(
            model_id="provider.gpt-4o-mini",
            items=[
                {"type": "message", "role": "user", "content": "What is the weather in Paris?"}
            ],
        )
    )
    assert outputs_1[0].finish_reason == "tool_calls"

    # Turn 2: continue with previous_response_id -- only the NEW function_call_output item is
    # sent as fresh input; the prior user turn + assistant tool call must be prepended from the
    # in-memory store, not repeated by the caller.
    descriptor, response_id_2, outputs_2, _ = (
        await llm_api_service.create_utility_conversation_response(
            model_id="provider.gpt-4o-mini",
            items=[{"type": "function_call_output", "call_id": "call_1", "output": "15C, sunny"}],
            previous_response_id=response_id_1,
        )
    )

    assert response_id_2 != response_id_1
    assert outputs_2[0].text == "It is 15C and sunny in Paris."
    # The second create_chat_completion call must have received the FULL prepended history:
    # the original user message, the assistant's tool call, and now the tool's output.
    assert calls[1] == [
        {"role": "user", "content": "What is the weather in Paris?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"location":"Paris"}'},
                }
            ],
        },
        {"role": "tool", "content": "15C, sunny", "tool_call_id": "call_1"},
    ]


@pytest.mark.anyio
async def test_create_utility_conversation_response_raises_for_unknown_previous_response_id(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        llm_api_service, "get_llm_model_descriptor", lambda model_id: _provider_chat_descriptor(model_id)
    )

    with pytest.raises(LLMAPIError) as exc_info:
        await llm_api_service.create_utility_conversation_response(
            model_id="provider.gpt-4o-mini",
            items=[{"type": "function_call_output", "call_id": "call_1", "output": "15C"}],
            previous_response_id="resp_does_not_exist_anywhere",
        )
    assert exc_info.value.code == "previous_response_id_not_found"
