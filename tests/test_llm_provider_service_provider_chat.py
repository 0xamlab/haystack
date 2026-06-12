"""Tests for test_llm_provider_service: provider_chat.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_provider_chat_completion_maps_groq_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.groq.com/openai/v1/chat/completions"
            assert json == {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer gq-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_groq_123",
                    "choices": [{"message": {"content": "Groq response."}}],
                    "usage": {"prompt_tokens": 6, "completion_tokens": 4},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_groq_123"
    assert result.content == "Groq response."
    assert result.prompt_tokens == 6
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "groq"
    assert result.provider.provider_model_id == "provider.groq-llama"
    assert [(item.provider_backend, item.provider_model_id, item.outcome, item.error_code) for item in result.provider_attempts] == [
        ("groq", "provider.groq-llama", "selected", None)
    ]


@pytest.mark.anyio
async def test_provider_chat_completion_maps_xai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.xai-grok",
        backend="xai",
        base_url="https://api.x.ai/v1",
        upstream_model="grok-4.3",
        api_key_env="XAI_API_KEY",
        description="Provider-backed xAI chat model.",
        capabilities=("chat_completions", "embeddings"),
    )
    monkeypatch.setenv("XAI_API_KEY", "xai-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.x.ai/v1/chat/completions"
            assert json == {
                "model": "grok-4.3",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer xai-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_xai_123",
                    "choices": [{"message": {"content": "xAI response."}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 4},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_xai_123"
    assert result.content == "xAI response."
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "xai"
    assert result.provider.provider_model_id == "provider.xai-grok"
    assert [(item.provider_backend, item.provider_model_id, item.outcome, item.error_code) for item in result.provider_attempts] == [
        ("xai", "provider.xai-grok", "selected", None)
    ]


@pytest.mark.anyio
async def test_provider_chat_completion_maps_rate_limit_status_to_retryable_error(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            del url, json, headers
            return httpx.Response(429, json={"error": {"message": "rate limited"}})

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(LLMAPIError, match="rate limited model") as exc_info:
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )
    assert exc_info.value.code == "provider_rate_limited"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_auth_failure_status_to_non_retryable_error(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            del url, json, headers
            return httpx.Response(401, json={"error": {"message": "bad key"}})

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(LLMAPIError, match="rejected credentials") as exc_info:
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )
    assert exc_info.value.code == "provider_authentication_failed"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_invalid_request_status_to_non_retryable_error(
    monkeypatch,
) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.groq-llama",
        backend="groq",
        base_url="https://api.groq.com/openai/v1",
        upstream_model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        description="Provider-backed Groq chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            del url, json, headers
            return httpx.Response(400, json={"error": {"message": "bad payload"}})

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(LLMAPIError, match="rejected the request") as exc_info:
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )
    assert exc_info.value.code == "invalid_provider_request"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_openai_compatible_payload(monkeypatch) -> None:
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

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://provider.test/v1/chat/completions"
            assert json == {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer sk-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_provider_123",
                    "choices": [{"message": {"content": "Provider response."}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_provider_123"
    assert result.content == "Provider response."
    assert result.prompt_tokens == 3
    assert result.completion_tokens == 2
    assert result.provider is not None
    assert result.provider.provider_backend == "openai_compatible"
    assert result.provider.provider_model_id == "provider.gpt-4o-mini"


@pytest.mark.anyio
async def test_provider_chat_completion_includes_required_header_envs(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
        header_envs=(("OpenAI-Organization", "OPENAI_ORG_ID"),),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_ORG_ID", "org_test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://provider.test/v1/chat/completions"
            assert headers["Authorization"] == "Bearer sk-test"
            assert headers["OpenAI-Organization"] == "org_test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_provider_123",
                    "choices": [{"message": {"content": "Provider response."}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.provider is not None
    assert result.provider.provider_model_id == "provider.gpt-4o-mini"


@pytest.mark.anyio
async def test_provider_chat_completion_requires_configured_header_env(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
        header_envs=(("OpenAI-Organization", "OPENAI_ORG_ID"),),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_ORG_ID", raising=False)

    with pytest.raises(LLMAPIError, match="requires header 'OpenAI-Organization'"):
        await llm_provider_service.provider_chat_completion(
            config=config,
            messages=[{"role": "user", "content": "Summarize"}],
        )


@pytest.mark.anyio
async def test_provider_chat_completion_uses_capability_specific_timeout(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions", "embeddings"),
        timeout_seconds=30.0,
        chat_timeout_seconds=12.5,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs["timeout"] == 12.5

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://provider.test/v1/chat/completions"
            assert json["model"] == "gpt-4o-mini"
            assert headers["Authorization"] == "Bearer sk-test"
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_provider_123",
                    "choices": [{"message": {"content": "Provider response."}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chatcmpl_provider_123"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_anthropic_payload(monkeypatch) -> None:
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

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.anthropic.com/v1/messages"
            # AR-OPT-1: the system prompt is emitted as a cacheable content block so
            # Anthropic prompt-caching can reuse a stable prefix across repeated calls.
            assert json == {
                "model": "claude-3-5-sonnet-latest",
                "messages": [{"role": "user", "content": "Summarize"}],
                "max_tokens": 512,
                "system": [
                    {
                        "type": "text",
                        "text": "Keep it terse.",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
            assert headers["x-api-key"] == "ak-test"
            assert headers["anthropic-version"] == "2023-06-01"
            return httpx.Response(
                200,
                json={
                    "id": "msg_123",
                    "content": [{"type": "text", "text": "Anthropic response."}],
                    "usage": {
                        "input_tokens": 7,
                        "output_tokens": 4,
                        "cache_read_input_tokens": 11,
                        "cache_creation_input_tokens": 5,
                    },
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[
            {"role": "system", "content": "Keep it terse."},
            {"role": "user", "content": "Summarize"},
        ],
    )

    assert result.completion_id == "msg_123"
    assert result.content == "Anthropic response."
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 4
    # AR-OPT-1: Anthropic prompt-cache usage is surfaced on the result.
    assert result.cache_read_tokens == 11
    assert result.cache_write_tokens == 5
    assert result.provider is not None
    assert result.provider.provider_backend == "anthropic"
    assert result.provider.provider_model_id == "provider.claude-sonnet"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_ollama_payload_without_auth(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.ollama-gemma3",
        backend="ollama",
        base_url="http://localhost:11434",
        upstream_model="gemma3",
        api_key_env=None,
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "http://localhost:11434/api/chat"
            assert json == {
                "model": "gemma3",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers == {"Content-Type": "application/json"}
            return httpx.Response(
                200,
                json={
                    "id": "chat_ollama_123",
                    "message": {"content": "Ollama response."},
                    "prompt_eval_count": 6,
                    "eval_count": 4,
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)
    # loopback base_url: allow egress so this payload-mapping test isn't blocked by the SSRF guard
    monkeypatch.setattr(egress_guard, "enforce_egress", allow_egress_for_test)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "chat_ollama_123"
    assert result.content == "Ollama response."
    assert result.prompt_tokens == 6
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "ollama"
    assert result.provider.provider_model_id == "provider.ollama-gemma3"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_google_genai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gemini-flash",
        backend="google_genai",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        upstream_model="gemini-2.5-flash",
        api_key_env="GEMINI_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert (
                url
                == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            )
            assert json == {
                "contents": [{"role": "user", "parts": [{"text": "Summarize"}]}],
                "systemInstruction": {"parts": [{"text": "Keep it terse."}]},
            }
            assert headers["x-goog-api-key"] == "gm-test"
            return httpx.Response(
                200,
                json={
                    "responseId": "gemini-response-123",
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "Gemini response."}],
                            }
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 8,
                        "candidatesTokenCount": 5,
                    },
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[
            {"role": "system", "content": "Keep it terse."},
            {"role": "user", "content": "Summarize"},
        ],
    )

    assert result.completion_id == "gemini-response-123"
    assert result.content == "Gemini response."
    assert result.prompt_tokens == 8
    assert result.completion_tokens == 5
    assert result.provider is not None
    assert result.provider.provider_backend == "google_genai"
    assert result.provider.provider_model_id == "provider.gemini-flash"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_mistral_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.mistral-small",
        backend="mistral",
        base_url="https://api.mistral.ai/v1",
        upstream_model="mistral-small-latest",
        api_key_env="MISTRAL_API_KEY",
        description="Provider-backed Mistral chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("MISTRAL_API_KEY", "ms-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.mistral.ai/v1/chat/completions"
            assert json == {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer ms-test"
            return httpx.Response(
                200,
                json={
                    "id": "cmpl_mistral_123",
                    "choices": [{"message": {"content": "Mistral response."}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "cmpl_mistral_123"
    assert result.content == "Mistral response."
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 3
    assert result.provider is not None
    assert result.provider.provider_backend == "mistral"
    assert result.provider.provider_model_id == "provider.mistral-small"


@pytest.mark.anyio
async def test_provider_chat_completion_maps_cohere_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.command-a",
        backend="cohere",
        base_url="https://api.cohere.com",
        upstream_model="command-a-03-2025",
        api_key_env="COHERE_API_KEY",
        description="Provider-backed Cohere chat model.",
        capabilities=("chat_completions",),
    )
    monkeypatch.setenv("COHERE_API_KEY", "co-test")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "https://api.cohere.com/v2/chat"
            assert json == {
                "model": "command-a-03-2025",
                "messages": [{"role": "user", "content": "Summarize"}],
                "stream": False,
            }
            assert headers["Authorization"] == "Bearer co-test"
            return httpx.Response(
                200,
                json={
                    "id": "cohere-chat-123",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Cohere response."}],
                    },
                    "meta": {
                        "tokens": {"input_tokens": 11, "output_tokens": 4},
                    },
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    result = await llm_provider_service.provider_chat_completion(
        config=config,
        messages=[{"role": "user", "content": "Summarize"}],
    )

    assert result.completion_id == "cohere-chat-123"
    assert result.content == "Cohere response."
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 4
    assert result.provider is not None
    assert result.provider.provider_backend == "cohere"
    assert result.provider.provider_model_id == "provider.command-a"


