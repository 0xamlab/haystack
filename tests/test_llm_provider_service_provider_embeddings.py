"""Tests for test_llm_provider_service: provider_embeddings.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_provider_service_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_provider_embeddings_require_configured_api_key(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gpt-4o-mini",
        backend="openai_compatible",
        base_url="https://provider.test/v1",
        upstream_model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMAPIError, match="environment variable 'OPENAI_API_KEY' is not set"):
        await llm_provider_service.provider_embeddings(
            config=config,
            inputs=["alpha beta"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_provider_embeddings_reject_anthropic_backend(monkeypatch) -> None:
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

    with pytest.raises(LLMAPIError, match="does not support embeddings"):
        await llm_provider_service.provider_embeddings(
            config=config,
            inputs=["alpha beta"],
            dimensions=3,
        )


@pytest.mark.anyio
async def test_provider_embeddings_maps_ollama_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.ollama-embeddinggemma",
        backend="ollama",
        base_url="http://localhost:11434",
        upstream_model="embeddinggemma",
        api_key_env=None,
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "http://localhost:11434/api/embed"
            assert json == {
                "model": "embeddinggemma",
                "input": ["alpha beta", "gamma delta"],
                "dimensions": 3,
            }
            assert headers == {"Content-Type": "application/json"}
            return httpx.Response(
                200,
                json={
                    "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                    "prompt_eval_count": 8,
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)
    # loopback base_url: allow egress so this payload-mapping test isn't blocked by the SSRF guard
    monkeypatch.setattr(egress_guard, "enforce_egress", allow_egress_for_test)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 8
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].token_count == 0
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "ollama"
    assert generated[0].provider.provider_model_id == "provider.ollama-embeddinggemma"
    assert generated[1].embedding == [0.4, 0.5, 0.6]
    assert generated[1].token_count == 0


@pytest.mark.anyio
async def test_provider_embeddings_uses_capability_specific_timeout(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.ollama-embeddinggemma",
        backend="ollama",
        base_url="http://localhost:11434",
        upstream_model="embeddinggemma",
        api_key_env=None,
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
        timeout_seconds=30.0,
        embedding_timeout_seconds=6.0,
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs["timeout"] == 6.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            assert url == "http://localhost:11434/api/embed"
            assert json["model"] == "embeddinggemma"
            assert headers == {"Content-Type": "application/json"}
            return httpx.Response(
                200,
                json={
                    "embeddings": [[0.1, 0.2, 0.3]],
                    "prompt_eval_count": 4,
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)
    # loopback base_url: allow egress so this payload-mapping test isn't blocked by the SSRF guard
    monkeypatch.setattr(egress_guard, "enforce_egress", allow_egress_for_test)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta"],
        dimensions=3,
    )

    assert total_tokens == 4
    assert generated[0].embedding == [0.1, 0.2, 0.3]


@pytest.mark.anyio
async def test_provider_embeddings_maps_google_genai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gemini-embedding",
        backend="google_genai",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        upstream_model="gemini-embedding-001",
        api_key_env="GEMINI_API_KEY",
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
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
                == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
            )
            assert json == {
                "requests": [
                    {
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": "alpha beta"}]},
                        "embedContentConfig": {"outputDimensionality": 3},
                    },
                    {
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": "gamma delta"}]},
                        "embedContentConfig": {"outputDimensionality": 3},
                    },
                ]
            }
            assert headers["x-goog-api-key"] == "gm-test"
            return httpx.Response(
                200,
                json={
                    "embeddings": [
                        {"values": [0.1, 0.2, 0.3]},
                        {"values": [0.4, 0.5, 0.6]},
                    ],
                    "usageMetadata": {"promptTokenCount": 7},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 7
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].token_count == 0
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "google_genai"
    assert generated[0].provider.provider_model_id == "provider.gemini-embedding"
    assert generated[1].embedding == [0.4, 0.5, 0.6]
    assert generated[1].token_count == 0


@pytest.mark.anyio
async def test_provider_embeddings_maps_google_genai_single_input_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.gemini-embedding",
        backend="google_genai",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        upstream_model="gemini-embedding-001",
        api_key_env="GEMINI_API_KEY",
        description="Provider-backed embeddings.",
        capabilities=("embeddings",),
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
                == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            )
            assert json == {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": "alpha beta"}]},
                "embedContentConfig": {"outputDimensionality": 3},
            }
            assert headers["x-goog-api-key"] == "gm-test"
            return httpx.Response(
                200,
                json={
                    "embedding": {"values": [0.1, 0.2, 0.3]},
                    "usageMetadata": {"promptTokenCount": 3},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta"],
        dimensions=3,
    )

    assert total_tokens == 3
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].token_count == 3
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "google_genai"
    assert generated[0].provider.provider_model_id == "provider.gemini-embedding"


@pytest.mark.anyio
async def test_provider_embeddings_maps_mistral_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.mistral-embed",
        backend="mistral",
        base_url="https://api.mistral.ai/v1",
        upstream_model="mistral-embed",
        api_key_env="MISTRAL_API_KEY",
        description="Provider-backed Mistral embeddings.",
        capabilities=("embeddings",),
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
            assert url == "https://api.mistral.ai/v1/embeddings"
            assert json == {
                "model": "mistral-embed",
                "input": ["alpha beta", "gamma delta"],
                "output_dimension": 3,
            }
            assert headers["Authorization"] == "Bearer ms-test"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.1, 0.2, 0.3]},
                        {"embedding": [0.4, 0.5, 0.6]},
                    ],
                    "usage": {"prompt_tokens": 7},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 7
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "mistral"
    assert generated[0].provider.provider_model_id == "provider.mistral-embed"
    assert generated[1].embedding == [0.4, 0.5, 0.6]


@pytest.mark.anyio
async def test_provider_embeddings_maps_xai_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.xai-grok",
        backend="xai",
        base_url="https://api.x.ai/v1",
        upstream_model="grok-4.3",
        api_key_env="XAI_API_KEY",
        description="Provider-backed xAI embeddings.",
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
            assert url == "https://api.x.ai/v1/embeddings"
            assert json == {
                "model": "grok-4.3",
                "input": "hello",
                "dimensions": 3,
            }
            assert headers["Authorization"] == "Bearer xai-test"
            return httpx.Response(
                200,
                json={
                    "data": [{"embedding": [0.1, 0.2, 0.3], "token_count": 2}],
                    "usage": {"prompt_tokens": 2},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["hello"],
        dimensions=3,
    )

    assert total_tokens == 2
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "xai"
    assert generated[0].provider.provider_model_id == "provider.xai-grok"


def test_provider_embeddings_payload_uses_backend_specific_dimension_keys() -> None:
    mistral_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.mistral-embed",
        backend="mistral",
        base_url="https://api.mistral.ai/v1",
        upstream_model="mistral-embed",
        api_key_env="MISTRAL_API_KEY",
        description="Provider-backed Mistral embeddings.",
        capabilities=("embeddings",),
    )
    openai_config = llm_provider_service.ProviderModelConfig(
        model_id="provider.text-embedding-3-small",
        backend="openai",
        base_url="https://api.openai.com/v1",
        upstream_model="text-embedding-3-small",
        api_key_env="OPENAI_API_KEY",
        description="Provider-backed OpenAI embeddings.",
        capabilities=("embeddings",),
    )

    mistral_payload = llm_provider_service._provider_embeddings_payload(
        config=mistral_config,
        inputs=["alpha beta"],
        dimensions=3,
    )
    openai_payload = llm_provider_service._provider_embeddings_payload(
        config=openai_config,
        inputs=["alpha beta"],
        dimensions=3,
    )

    assert mistral_payload == {
        "model": "mistral-embed",
        "input": "alpha beta",
        "output_dimension": 3,
    }
    assert openai_payload == {
        "model": "text-embedding-3-small",
        "input": "alpha beta",
        "dimensions": 3,
    }


@pytest.mark.anyio
async def test_provider_embeddings_maps_cohere_payload(monkeypatch) -> None:
    config = llm_provider_service.ProviderModelConfig(
        model_id="provider.embed-v4",
        backend="cohere",
        base_url="https://api.cohere.com",
        upstream_model="embed-v4.0",
        api_key_env="COHERE_API_KEY",
        description="Provider-backed Cohere embeddings.",
        capabilities=("embeddings",),
        embedding_input_type="classification",
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
            assert url == "https://api.cohere.com/v2/embed"
            assert json == {
                "model": "embed-v4.0",
                "texts": ["alpha beta", "gamma delta"],
                "input_type": "classification",
                "embedding_types": ["float"],
                "output_dimension": 3,
            }
            assert headers["Authorization"] == "Bearer co-test"
            return httpx.Response(
                200,
                json={
                    "embeddings": {
                        "float": [
                            [0.1, 0.2, 0.3],
                            [0.4, 0.5, 0.6],
                        ]
                    },
                    "meta": {"billed_units": {"input_tokens": 9}},
                },
            )

    monkeypatch.setattr(llm_provider_service.httpx, "AsyncClient", _FakeClient)

    generated, total_tokens = await llm_provider_service.provider_embeddings(
        config=config,
        inputs=["alpha beta", "gamma delta"],
        dimensions=3,
    )

    assert total_tokens == 9
    assert generated[0].embedding == [0.1, 0.2, 0.3]
    assert generated[0].provider is not None
    assert generated[0].provider.provider_backend == "cohere"
    assert generated[0].provider.provider_model_id == "provider.embed-v4"
    assert generated[1].embedding == [0.4, 0.5, 0.6]


