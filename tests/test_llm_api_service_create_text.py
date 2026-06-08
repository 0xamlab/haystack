"""Tests for test_llm_api_service: create_text.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_create_text_embeddings_generates_deterministic_hash_vectors(monkeypatch) -> None:
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

    async def _fake_execute(**kwargs: object):
        assert kwargs["module"] == "text.tokenizer"
        assert kwargs["function"] == "word_tokenize"
        token_map = {
            "alpha beta alpha": ["alpha", "beta", "alpha"],
            "beta gamma": ["beta", "gamma"],
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

    descriptor, generated, total_tokens = await llm_api_service.create_text_embeddings(
        model_id="text.hash_embedding_v1",
        inputs=["alpha beta alpha", "beta gamma"],
        dimensions=8,
    )

    assert descriptor.model_id == "text.hash_embedding_v1"
    assert total_tokens == 5
    assert [item.index for item in generated] == [0, 1]
    assert [item.token_count for item in generated] == [3, 2]
    assert all(len(item.embedding) == 8 for item in generated)
    assert generated[0].embedding == llm_api_service._stable_hash_embedding(
        tokens=["alpha", "beta", "alpha"],
        dimensions=8,
    )
    assert generated[1].embedding == llm_api_service._stable_hash_embedding(
        tokens=["beta", "gamma"],
        dimensions=8,
    )
    assert generated[0].embedding != generated[1].embedding


@pytest.mark.anyio
async def test_create_text_embeddings_routes_provider_backed_models(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="provider.openai_compatible",
            description="Provider-backed embeddings.",
            capabilities=("embeddings",),
            supported_endpoints=("/v1/models", "/v1/embeddings"),
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
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: provider_config if model_id == "provider.gpt-4o-mini" else None,
    )

    async def _fake_provider_embeddings(*, model_id, inputs, dimensions):
        assert model_id == "provider.gpt-4o-mini"
        assert inputs == ["expand sales coverage"]
        assert dimensions == 3
        return (
            [
                llm_api_service.GeneratedEmbedding(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=5,
                    provider=llm_api_service.ProviderExecutionMetadata(
                        provider_backend="openai_compatible",
                        provider_model_id="provider.gpt-4o-mini",
                    ),
                )
            ],
            5,
        )

    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "routed_provider_embeddings",
        _fake_provider_embeddings,
    )

    descriptor, generated, total_tokens = await llm_api_service.create_text_embeddings(
        model_id="provider.gpt-4o-mini",
        inputs=["expand sales coverage"],
        dimensions=3,
    )

    assert descriptor.provider_backend == "openai_compatible"
    assert total_tokens == 5
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider == llm_api_service.ProviderExecutionMetadata(
        provider_backend="openai_compatible",
        provider_model_id="provider.gpt-4o-mini",
    )


@pytest.mark.anyio
async def test_create_text_embeddings_routes_router_provider_models(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="provider.router",
            description="Ordered provider router alias.",
            capabilities=("embeddings",),
            supported_endpoints=("/v1/models", "/v1/embeddings", "/v1/responses"),
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
            capabilities=("embeddings",),
            routing_targets=("provider.primary",),
        ),
    )

    async def _fake_routed_provider_embeddings(*, model_id, inputs, dimensions):
        assert model_id == "provider.router"
        assert inputs == ["hello"]
        assert dimensions == 3
        return (
            [
                llm_api_service.GeneratedEmbedding(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
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
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "routed_provider_embeddings",
        _fake_routed_provider_embeddings,
    )

    descriptor, generated, total_tokens = await llm_api_service.create_text_embeddings(
        model_id="provider.router",
        inputs=["hello"],
        dimensions=3,
    )

    assert descriptor.provider_backend == "router"
    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider == llm_api_service.ProviderExecutionMetadata(
        provider_backend="openai",
        provider_model_id="provider.primary",
    )
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai", "provider.primary", "selected", None),
    ]


