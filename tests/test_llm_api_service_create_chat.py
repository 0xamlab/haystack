"""Tests for test_llm_api_service: create_chat.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_create_chat_completion_returns_deterministic_token_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="text.tokenizer",
            description="Deterministic word tokenizer backed by the runtime library catalog.",
            capabilities=("tokenize", "count_tokens", "chat_completions"),
            supported_endpoints=(
                "/v1/models",
                "/v1/tokenize",
                "/v1/count_tokens",
                "/v1/chat/completions",
                "/v1/responses",
            ),
            tokenizer_kind="word",
            similarity_metric=None,
            runtime_functions=("word_tokenize",),
            available=True,
        ),
    )

    async def _fake_execute(**kwargs: object):
        token_map = {
            "Keep the last user message stable": ["Keep", "the", "last", "user", "message", "stable"],
            "alpha beta": ["alpha", "beta"],
            "ignore": ["ignore"],
            '{"model":"text.tokenizer","token_count":2,"tokens":["alpha","beta"]}': [
                "model",
                "text",
                "tokenizer",
                "token",
                "count",
                "2",
                "tokens",
                "alpha",
                "beta",
            ],
        }
        return SimpleNamespace(
            module="text.tokenizer",
            function="word_tokenize",
            result=token_map[kwargs["args"]],
            latency_ms=1.0,
            engine_used="mojo",
            request_id=None,
        )

    monkeypatch.setattr(llm_api_service, "execute_public_runtime_library", _fake_execute)

    descriptor, completion = await llm_api_service.create_chat_completion(
        model_id="text.tokenizer",
        messages=[
            {"role": "system", "content": "Keep the last user message stable"},
            {"role": "user", "content": "alpha beta"},
            {"role": "assistant", "content": "ignore"},
        ],
    )

    expected_content = '{"model":"text.tokenizer","token_count":2,"tokens":["alpha","beta"]}'
    assert descriptor.model_id == "text.tokenizer"
    assert completion == llm_api_service.ChatCompletionResult(
        completion_id=llm_api_service._deterministic_chat_completion_id(
            model_id="text.tokenizer",
            messages=[
                {"role": "system", "content": "Keep the last user message stable"},
                {"role": "user", "content": "alpha beta"},
                {"role": "assistant", "content": "ignore"},
            ],
        ),
        content=expected_content,
        prompt_tokens=9,
        completion_tokens=9,
    )


@pytest.mark.anyio
async def test_create_chat_completion_routes_provider_backed_models(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="provider.openai_compatible",
            description="Provider-backed chat model.",
            capabilities=("chat_completions",),
            supported_endpoints=("/v1/models", "/v1/chat/completions"),
            tokenizer_kind=None,
            similarity_metric=None,
            runtime_functions=(),
            available=True,
            provider_backend="openai_compatible",
        ),
    )
    provider_config = llm_api_service.llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: provider_config if model_id == "provider.gpt-4o-mini" else None,
    )

    async def _fake_provider_chat_completion(*, model_id, messages):
        assert model_id == "provider.gpt-4o-mini"
        assert messages == [{"role": "user", "content": "Summarize"}]
        return llm_api_service.ChatCompletionResult(
            completion_id="chatcmpl_provider_123",
            content="Provider response.",
            prompt_tokens=3,
            completion_tokens=2,
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="openai_compatible",
                provider_model_id="provider.gpt-4o-mini",
            ),
        )

    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "routed_provider_chat_completion",
        _fake_provider_chat_completion,
    )

    descriptor, result = await llm_api_service.create_chat_completion(
        model_id="provider.gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert descriptor.provider_backend == "openai_compatible"
    assert result.completion_id == "chatcmpl_provider_123"
    assert result.content == "Provider response."
    assert result.provider == llm_api_service.ProviderExecutionMetadata(
        provider_backend="openai_compatible",
        provider_model_id="provider.gpt-4o-mini",
    )


@pytest.mark.anyio
async def test_create_chat_completion_routes_anthropic_provider_models(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="provider.anthropic",
            description="Provider-backed chat model.",
            capabilities=("chat_completions",),
            supported_endpoints=("/v1/models", "/v1/chat/completions", "/v1/responses"),
            tokenizer_kind=None,
            similarity_metric=None,
            runtime_functions=(),
            available=True,
            provider_backend="anthropic",
        ),
    )
    provider_config = llm_api_service.llm_provider_service.ProviderModelConfig(
        model_id="provider.claude-sonnet",
        backend="anthropic",
        base_url="https://api.anthropic.com/v1",
        upstream_model="claude-3-5-sonnet-latest",
        api_key_env="ANTHROPIC_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: provider_config if model_id == "provider.claude-sonnet" else None,
    )

    async def _fake_provider_chat_completion(*, model_id, messages):
        assert model_id == "provider.claude-sonnet"
        assert messages == [{"role": "user", "content": "Summarize"}]
        return llm_api_service.ChatCompletionResult(
            completion_id="msg_provider_123",
            content="Anthropic response.",
            prompt_tokens=5,
            completion_tokens=3,
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="anthropic",
                provider_model_id="provider.claude-sonnet",
            ),
        )

    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "routed_provider_chat_completion",
        _fake_provider_chat_completion,
    )

    descriptor, result = await llm_api_service.create_chat_completion(
        model_id="provider.claude-sonnet",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert descriptor.provider_backend == "anthropic"
    assert result.completion_id == "msg_provider_123"
    assert result.content == "Anthropic response."
    assert result.provider == llm_api_service.ProviderExecutionMetadata(
        provider_backend="anthropic",
        provider_model_id="provider.claude-sonnet",
    )


@pytest.mark.anyio
async def test_create_chat_completion_routes_router_provider_models(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="provider.router",
            description="Ordered provider router alias.",
            capabilities=("chat_completions",),
            supported_endpoints=("/v1/models", "/v1/chat/completions", "/v1/responses"),
            tokenizer_kind=None,
            similarity_metric=None,
            runtime_functions=(),
            available=True,
            provider_backend="router",
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: llm_api_service.llm_provider_service.ProviderModelConfig(
            model_id=model_id,
            backend="router",
            base_url="",
            upstream_model=model_id,
            api_key_env=None,
            description="Ordered provider router alias.",
            capabilities=("chat_completions",),
            routing_targets=("provider.fast", "provider.primary"),
        ),
    )

    async def _fake_routed_provider_chat_completion(*, model_id, messages):
        assert model_id == "provider.router"
        assert messages == [{"role": "user", "content": "Summarize"}]
        return llm_api_service.ChatCompletionResult(
            completion_id="chatcmpl_router_123",
            content="Router response.",
            prompt_tokens=5,
            completion_tokens=3,
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
            provider_attempts=(
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="groq",
                    provider_model_id="provider.fast",
                    outcome="failed",
                    error_code="provider_backend_error",
                ),
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="openai",
                    provider_model_id="provider.primary",
                    outcome="selected",
                ),
            ),
        )

    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "routed_provider_chat_completion",
        _fake_routed_provider_chat_completion,
    )

    descriptor, result = await llm_api_service.create_chat_completion(
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert descriptor.provider_backend == "router"
    assert result.completion_id == "chatcmpl_router_123"
    assert result.content == "Router response."
    assert result.provider == llm_api_service.ProviderExecutionMetadata(
        provider_backend="openai",
        provider_model_id="provider.primary",
    )
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_backend_error"),
        ("openai", "provider.primary", "selected", None),
    ]


