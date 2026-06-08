"""Tests for test_llm_provider_service: routed_provider_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_routed_provider_chat_completion_nested_router_skips_incapable_targets_under_max_attempts(
    monkeypatch,
) -> None:
    outer_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.outer",
        backend="router",
        base_url="",
        upstream_model="provider.router.outer",
        api_key_env=None,
        description="Outer router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.embedder", "provider.router.inner"),
        routing_fallback_policy="disabled",
        routing_max_attempts=1,
    )
    inner_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.inner",
        backend="router",
        base_url="",
        upstream_model="provider.router.inner",
        api_key_env=None,
        description="Inner router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.primary",),
        routing_fallback_policy="disabled",
    )
    embedder = llm_provider_service.ProviderModelConfig(
        model_id="provider.embedder",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Embeddings-only route",
        capabilities=("embeddings",),
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
    )
    configs = {
        item.model_id: item
        for item in (outer_router, inner_router, embedder, primary)
    }
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: configs.get(model_id),
    )

    seen_calls: list[str] = []

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        seen_calls.append(config.model_id)
        return SimpleNamespace(
            completion_id="chatcmpl_capability_aware_router_123",
            content="Capability-aware nested router response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend="openai",
                provider_model_id="provider.primary",
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router.outer",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_capability_aware_router_123"
    assert seen_calls == ["provider.primary"]
    assert getattr(result, "provider_attempts", ()) == ()


@pytest.mark.anyio
async def test_routed_provider_embeddings_fails_over_retryable_errors(monkeypatch) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="disabled",
        embedding_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [
                SimpleNamespace(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
                    provider=SimpleNamespace(
                        provider_backend="openai",
                        provider_model_id="provider.embed-primary",
                    ),
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
        model_id="provider.router",
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider.provider_backend == "openai"
    assert generated[0].provider.provider_model_id == "provider.embed-primary"
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai_compatible", "provider.embed-fast", "failed", "provider_timeout"),
        ("openai", "provider.embed-primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_embeddings_disabled_fallback_skips_incapable_targets(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.fast",
                    "backend": "groq",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_name": "llama-3.3-70b-versatile",
                    "api_key_env": "GROQ_API_KEY",
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "capabilities": ["embeddings"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions", "embeddings"],
                    "targets": ["provider.fast", "provider.embedder"],
                    "fallback_policy": "disabled",
                },
            ]
        ),
    )
    llm_provider_service.load_provider_model_configs.cache_clear()

    seen_calls: list[str] = []

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        seen_calls.append(config.model_id)
        return (
            [
                SimpleNamespace(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
                    provider=SimpleNamespace(
                        provider_backend="openai_compatible",
                        provider_model_id=config.model_id,
                    ),
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    try:
        generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )
    finally:
        llm_provider_service.load_provider_model_configs.cache_clear()

    assert total_tokens == 2
    assert seen_calls == ["provider.embedder"]
    assert generated[0].provider.provider_model_id == "provider.embedder"
    assert getattr(generated[0], "provider_attempts", ()) == ()


@pytest.mark.anyio
async def test_routed_provider_embeddings_does_not_fallback_without_explicit_policy(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="disabled",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3], token_count=2)],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    with pytest.raises(LLMAPIError, match="transient upstream timeout"):
        await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_routed_provider_embeddings_uses_shared_fallback_policy_when_capability_override_missing(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions", "embeddings"),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3], token_count=2)],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
        model_id="provider.router",
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai_compatible", "provider.embed-fast", "failed", "provider_timeout"),
        ("openai", "provider.embed-primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_embeddings_respects_shared_fallback_on(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions", "embeddings"),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="retryable_only",
        routing_fallback_on=("provider_rate_limited",),
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        assert timeout_seconds is None
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        return (
            [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3], token_count=2)],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    with pytest.raises(LLMAPIError, match="transient upstream timeout"):
        await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_routed_provider_embeddings_respects_capability_specific_max_attempts(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions", "embeddings"),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        routing_fallback_policy="retryable_only",
        embedding_routing_max_attempts=1,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_provider_route_targets",
        lambda **kwargs: (primary, fallback),
    )
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: router_config if model_id == "provider.router" else None,
    )

    seen_targets: list[str] = []

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        del inputs, dimensions
        assert timeout_seconds is None
        seen_targets.append(config.model_id)
        raise LLMAPIError(
            "provider_timeout",
            "transient upstream timeout",
            {"model": config.model_id},
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    with pytest.raises(LLMAPIError, match="All configured provider targets failed"):
        await llm_provider_service.routed_provider_embeddings(
            model_id="provider.router",
            inputs=["hello"],
            dimensions=3,
        )

    assert seen_targets == ["provider.embed-fast"]


@pytest.mark.anyio
async def test_routed_provider_embeddings_honor_nested_router_policy(
    monkeypatch,
) -> None:
    outer_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.outer",
        backend="router",
        base_url="",
        upstream_model="provider.router.outer",
        api_key_env=None,
        description="Outer router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.router.inner", "provider.embed-backup"),
        routing_fallback_policy="disabled",
    )
    inner_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.inner",
        backend="router",
        base_url="",
        upstream_model="provider.router.inner",
        api_key_env=None,
        description="Inner router alias",
        capabilities=("embeddings",),
        routing_targets=("provider.embed-fast", "provider.embed-primary"),
        embedding_routing_fallback_policy="retryable_only",
        embedding_timeout_seconds=6.25,
    )
    fast = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-fast",
        backend="openai_compatible",
        base_url="https://provider-fast.test/v1",
        upstream_model="text-embedding-fast",
        api_key_env="OPENAI_API_KEY",
        description="Fast embed route",
        capabilities=("embeddings",),
        embedding_timeout_seconds=18.0,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Primary embed route",
        capabilities=("embeddings",),
        embedding_timeout_seconds=22.0,
    )
    backup = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-backup",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Backup embed route",
        capabilities=("embeddings",),
    )
    configs = {
        item.model_id: item
        for item in (outer_router, inner_router, fast, primary, backup)
    }
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: configs.get(model_id),
    )

    seen_calls: list[tuple[str, float | None]] = []

    async def _fake_provider_embeddings(
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ):
        assert inputs == ["hello"]
        assert dimensions == 3
        seen_calls.append((config.model_id, timeout_seconds))
        if config.model_id == "provider.embed-fast":
            raise LLMAPIError(
                "provider_timeout",
                "transient upstream timeout",
                {"model": config.model_id},
            )
        assert config.model_id == "provider.embed-primary"
        return (
            [
                SimpleNamespace(
                    index=0,
                    embedding=[0.1, 0.2, 0.3],
                    token_count=2,
                    provider=SimpleNamespace(
                        provider_backend="openai",
                        provider_model_id="provider.embed-primary",
                    ),
                )
            ],
            2,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_embeddings",
        _fake_provider_embeddings,
    )

    generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
        model_id="provider.router.outer",
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert seen_calls == [
        ("provider.embed-fast", 6.25),
        ("provider.embed-primary", 6.25),
    ]
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in generated[0].provider_attempts
    ] == [
        ("openai_compatible", "provider.embed-fast", "failed", "provider_timeout"),
        ("openai", "provider.embed-primary", "selected", None),
    ]


