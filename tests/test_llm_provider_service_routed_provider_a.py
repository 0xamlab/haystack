"""Tests for test_llm_provider_service: routed_provider_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_routed_provider_chat_completion_fails_over_retryable_errors(monkeypatch) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
        chat_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_backend_error",
                "transient upstream error",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
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
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_fallback_123"
    assert result.content == "Fallback response."
    assert result.provider.provider_backend == "openai"
    assert result.provider.provider_model_id == "provider.primary"
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_backend_error"),
        ("openai", "provider.primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_fails_over_rate_limited_errors(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
        chat_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_rate_limited",
                "provider quota exhausted",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
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
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_rate_limited"),
        ("openai", "provider.primary", "selected", None),
    ]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_respects_capability_specific_fallback_on(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        chat_routing_fallback_policy="retryable_only",
        chat_routing_fallback_on=("provider_rate_limited",),
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_backend_error",
                "transient upstream error",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
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

    with pytest.raises(LLMAPIError, match="transient upstream error"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_routed_provider_chat_completion_does_not_fallback_without_explicit_policy(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_backend_error",
                "transient upstream error",
                {"model": config.model_id},
            )
        return SimpleNamespace(
            completion_id="chatcmpl_fallback_123",
            content="Fallback response.",
            prompt_tokens=4,
            completion_tokens=3,
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="transient upstream error"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_routed_provider_chat_completion_does_not_fallback_on_invalid_provider_request(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="disabled",
        chat_routing_fallback_policy="retryable_only",
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds is None
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "invalid_provider_request",
                "provider rejected payload",
                {"model": config.model_id},
            )
        pytest.fail("fallback target should not execute for invalid provider requests")

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="provider rejected payload"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_routed_provider_chat_completion_respects_shared_max_attempts(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        routing_fallback_policy="retryable_only",
        routing_max_attempts=1,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        del messages
        assert timeout_seconds is None
        seen_targets.append(config.model_id)
        raise LLMAPIError(
            "provider_rate_limited",
            "provider quota exhausted",
            {"model": config.model_id},
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    with pytest.raises(LLMAPIError, match="All configured provider targets failed"):
        await llm_provider_service.routed_provider_chat_completion(
            model_id="provider.router",
            messages=[{"role": "user", "content": "Summarize"}],
        )

    assert seen_targets == ["provider.fast"]


@pytest.mark.anyio
async def test_routed_provider_chat_completion_uses_router_timeout_override(
    monkeypatch,
) -> None:
    router_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.router",
        backend="router",
        base_url="",
        upstream_model="provider.router",
        api_key_env=None,
        description="Router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        chat_timeout_seconds=7.5,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
        chat_timeout_seconds=15.0,
    )
    fallback = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions", "embeddings"),
        chat_timeout_seconds=20.0,
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

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        assert timeout_seconds == 7.5
        return SimpleNamespace(
            completion_id="chatcmpl_router_123",
            content="Router response.",
            prompt_tokens=4,
            completion_tokens=3,
            provider=SimpleNamespace(
                provider_backend=config.backend,
                provider_model_id=config.model_id,
            ),
        )

    monkeypatch.setattr(
        llm_provider_service,
        "provider_chat_completion",
        _fake_provider_chat_completion,
    )

    result = await llm_provider_service.routed_provider_chat_completion(
        model_id="provider.router",
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_router_123"


@pytest.mark.anyio
async def test_routed_provider_chat_completion_honors_nested_router_policy(
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
        routing_targets=("provider.router.inner", "provider.primary"),
        routing_fallback_policy="disabled",
    )
    inner_router = llm_provider_service.ProviderModelConfig(
        model_id="provider.router.inner",
        backend="router",
        base_url="",
        upstream_model="provider.router.inner",
        api_key_env=None,
        description="Inner router alias",
        capabilities=("chat_completions",),
        routing_targets=("provider.fast", "provider.primary"),
        chat_routing_fallback_policy="retryable_only",
        chat_timeout_seconds=9.5,
    )
    fast = llm_provider_service.ProviderModelConfig(
        model_id="provider.fast",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Fast route",
        capabilities=("chat_completions",),
        chat_timeout_seconds=30.0,
    )
    primary = llm_provider_service.ProviderModelConfig(
        model_id="provider.primary",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Primary route",
        capabilities=("chat_completions",),
        chat_timeout_seconds=20.0,
    )
    configs = {
        item.model_id: item
        for item in (outer_router, inner_router, fast, primary)
    }
    monkeypatch.setattr(
        llm_provider_service,
        "get_configured_provider_model",
        lambda model_id: configs.get(model_id),
    )

    seen_calls: list[tuple[str, float | None]] = []

    async def _fake_provider_chat_completion(
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ):
        assert messages == [{"role": "user", "content": "Summarize"}]
        seen_calls.append((config.model_id, timeout_seconds))
        if config.model_id == "provider.fast":
            raise LLMAPIError(
                "provider_rate_limited",
                "provider quota exhausted",
                {"model": config.model_id},
            )
        assert config.model_id == "provider.primary"
        return SimpleNamespace(
            completion_id="chatcmpl_nested_router_123",
            content="Nested router response.",
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

    assert result.completion_id == "chatcmpl_nested_router_123"
    assert seen_calls == [("provider.fast", 9.5), ("provider.primary", 9.5)]
    assert [
        (item.provider_backend, item.provider_model_id, item.outcome, item.error_code)
        for item in result.provider_attempts
    ] == [
        ("groq", "provider.fast", "failed", "provider_rate_limited"),
        ("openai", "provider.primary", "selected", None),
    ]


