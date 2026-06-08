"""Tests for test_llm_api_service: create_utility.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_create_utility_response_for_tokenizer_returns_deterministic_response_id(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="text.tokenizer",
            description="Deterministic word tokenizer backed by the runtime library catalog.",
            capabilities=("tokenize", "count_tokens"),
            supported_endpoints=("/v1/models", "/v1/tokenize", "/v1/count_tokens", "/v1/responses"),
            tokenizer_kind="word",
            similarity_metric=None,
            runtime_functions=("word_tokenize",),
            available=True,
        ),
    )

    async def _fake_execute(**kwargs: object):
        return SimpleNamespace(
            module="text.tokenizer",
            function="word_tokenize",
            result=["alpha", "beta"],
            latency_ms=1.0,
            engine_used="mojo",
            request_id=None,
        )

    monkeypatch.setattr(llm_api_service, "execute_public_runtime_library", _fake_execute)

    descriptor, response_id, outputs, total_tokens = await llm_api_service.create_utility_response(
        model_id="text.tokenizer",
        inputs=["alpha beta"],
        dimensions=64,
    )

    assert descriptor.model_id == "text.tokenizer"
    assert response_id == llm_api_service._deterministic_response_id(
        model_id="text.tokenizer",
        inputs=["alpha beta"],
        dimensions=None,
    )
    assert total_tokens == 2
    assert outputs == [
        llm_api_service.UtilityResponseOutputItem(
            index=0,
            item_type="tokenization",
            text="alpha beta",
            tokens=["alpha", "beta"],
            token_count=2,
            embedding=None,
        )
    ]


@pytest.mark.anyio
async def test_create_utility_response_for_embeddings_returns_embedding_items(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="text.tokenizer",
            description="Deterministic lexical hash embeddings generated from runtime tokenization and stable feature hashing.",
            capabilities=("embeddings",),
            supported_endpoints=("/v1/models", "/v1/embeddings", "/v1/responses"),
            tokenizer_kind="word",
            similarity_metric=None,
            runtime_functions=("word_tokenize",),
            available=True,
        ),
    )

    async def _fake_create_embeddings(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "text.hash_embedding_v1"
        assert inputs == ["alpha beta", "gamma"]
        assert dimensions == 2
        return (
            llm_api_service.LLMModelDescriptor(
                model_id=model_id,
                runtime_module="text.tokenizer",
                description="Deterministic lexical hash embeddings generated from runtime tokenization and stable feature hashing.",
                capabilities=("embeddings",),
                supported_endpoints=("/v1/models", "/v1/embeddings", "/v1/responses"),
                tokenizer_kind="word",
                similarity_metric=None,
                runtime_functions=("word_tokenize",),
                available=True,
            ),
            [
                llm_api_service.GeneratedEmbedding(
                    index=0,
                    embedding=[1.0, 0.0],
                    token_count=2,
                    provider=llm_api_service.ProviderExecutionMetadata(
                        provider_backend="openai",
                        provider_model_id="provider.primary",
                    ),
                    provider_attempts=(
                        llm_api_service.ProviderAttemptRecord(
                            provider_backend="groq",
                            provider_model_id="provider.fast",
                            outcome="failed",
                            error_code="provider_rate_limited",
                        ),
                        llm_api_service.ProviderAttemptRecord(
                            provider_backend="openai",
                            provider_model_id="provider.primary",
                            outcome="selected",
                        ),
                    ),
                ),
                llm_api_service.GeneratedEmbedding(
                    index=1,
                    embedding=[0.0, 1.0],
                    token_count=1,
                    provider=llm_api_service.ProviderExecutionMetadata(
                        provider_backend="openai",
                        provider_model_id="provider.primary",
                    ),
                    provider_attempts=(
                        llm_api_service.ProviderAttemptRecord(
                            provider_backend="openai",
                            provider_model_id="provider.primary",
                            outcome="selected",
                        ),
                    ),
                ),
            ],
            3,
        )

    monkeypatch.setattr(llm_api_service, "create_text_embeddings", _fake_create_embeddings)

    descriptor, response_id, outputs, total_tokens = await llm_api_service.create_utility_response(
        model_id="text.hash_embedding_v1",
        inputs=["alpha beta", "gamma"],
        dimensions=2,
    )

    assert descriptor.model_id == "text.hash_embedding_v1"
    assert response_id == llm_api_service._deterministic_response_id(
        model_id="text.hash_embedding_v1",
        inputs=["alpha beta", "gamma"],
        dimensions=2,
    )
    assert total_tokens == 3
    assert outputs == [
        llm_api_service.UtilityResponseOutputItem(
            index=0,
            item_type="embedding",
            text="alpha beta",
            tokens=None,
            token_count=2,
            embedding=[1.0, 0.0],
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
            provider_attempts=(
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="groq",
                    provider_model_id="provider.fast",
                    outcome="failed",
                    error_code="provider_rate_limited",
                ),
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="openai",
                    provider_model_id="provider.primary",
                    outcome="selected",
                ),
            ),
        ),
        llm_api_service.UtilityResponseOutputItem(
            index=1,
            item_type="embedding",
            text="gamma",
            tokens=None,
            token_count=1,
            embedding=[0.0, 1.0],
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
            provider_attempts=(
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="openai",
                    provider_model_id="provider.primary",
                    outcome="selected",
                ),
            ),
        ),
    ]


@pytest.mark.anyio
async def test_create_utility_response_for_provider_chat_returns_text_items(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
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
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: object(),
    )

    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        prompt = messages[0]["content"]
        completion_id = "chatcmpl_provider_alpha" if prompt == "alpha" else "chatcmpl_provider_beta"
        return (
            llm_api_service.get_llm_model_descriptor(model_id),
            llm_api_service.ChatCompletionResult(
                completion_id=completion_id,
                content=f"provider:{prompt}",
                prompt_tokens=2,
                completion_tokens=3,
                provider=llm_api_service.ProviderExecutionMetadata(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                ),
                provider_attempts=(
                    llm_api_service.ProviderAttemptRecord(
                        provider_backend="groq",
                        provider_model_id="provider.fast",
                        outcome="failed",
                        error_code="provider_rate_limited",
                    ),
                    llm_api_service.ProviderAttemptRecord(
                        provider_backend="openai_compatible",
                        provider_model_id="provider.gpt-4o-mini",
                        outcome="selected",
                    ),
                ),
            ),
        )

    monkeypatch.setattr(llm_api_service, "create_chat_completion", _fake_chat_completion)

    descriptor, response_id, outputs, total_tokens = await llm_api_service.create_utility_response(
        model_id="provider.gpt-4o-mini",
        inputs=["alpha", "beta"],
        dimensions=64,
    )

    assert descriptor.model_id == "provider.gpt-4o-mini"
    assert response_id == llm_api_service._response_id_from_chat_completion_ids(
        model_id="provider.gpt-4o-mini",
        completion_ids=["chatcmpl_provider_alpha", "chatcmpl_provider_beta"],
    )
    assert total_tokens == 10
    assert outputs == [
        llm_api_service.UtilityResponseOutputItem(
            index=0,
            item_type="text",
            text="provider:alpha",
            tokens=None,
            token_count=3,
            embedding=None,
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="openai_compatible",
                provider_model_id="provider.gpt-4o-mini",
            ),
            provider_attempts=(
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="groq",
                    provider_model_id="provider.fast",
                    outcome="failed",
                    error_code="provider_rate_limited",
                ),
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                    outcome="selected",
                ),
            ),
        ),
        llm_api_service.UtilityResponseOutputItem(
            index=1,
            item_type="text",
            text="provider:beta",
            tokens=None,
            token_count=3,
            embedding=None,
            provider=llm_api_service.ProviderExecutionMetadata(
                provider_backend="openai_compatible",
                provider_model_id="provider.gpt-4o-mini",
            ),
            provider_attempts=(
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="groq",
                    provider_model_id="provider.fast",
                    outcome="failed",
                    error_code="provider_rate_limited",
                ),
                llm_api_service.ProviderAttemptRecord(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                    outcome="selected",
                ),
            ),
        ),
    ]


