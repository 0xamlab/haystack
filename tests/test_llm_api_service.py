from __future__ import annotations

import json
import pytest
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.services import llm_api_service
from apps.api_server.services.llm_api_service import LLMAPIError


def test_list_llm_model_descriptors_includes_runtime_backed_tokenizer_and_similarity(monkeypatch) -> None:
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/tmp/algenta-hf-cache")
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setattr(
        llm_api_service,
        "list_public_runtime_library_descriptors",
        lambda: (
            SimpleNamespace(
                name="text.tokenizer",
                engine="mojo",
                functions=("word_tokenize", "sentence_tokenize"),
            ),
            SimpleNamespace(
                name="embeddings",
                engine="mojo",
                functions=("cosine_similarity", "euclidean_distance", "manhattan_distance"),
            ),
        ),
    )
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=2,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service,
        "_detect_bridge_backends",
        lambda specs: (
            ("tiktoken", "tokenizers")
            if specs == llm_api_service._TOKENIZER_BRIDGE_SPECS
            else ("safetensors", "huggingface_hub")
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == [
        "embeddings.cosine_similarity",
        "embeddings.euclidean_distance",
        "embeddings.manhattan_distance",
        "text.hash_embedding_v1",
        "text.tokenizer",
    ]
    assert descriptors[0].similarity_metric == "cosine"
    assert descriptors[0].capabilities == ("embedding_similarity", "rerank")
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/embeddings/similarity",
        "/v1/rerank",
    )
    assert descriptors[3].capabilities == ("embeddings",)
    assert descriptors[3].supported_endpoints == ("/v1/models", "/v1/embeddings", "/v1/responses")
    assert descriptors[3].bridge_tokenizer_backends == ("tiktoken", "tokenizers")
    assert descriptors[3].bridge_artifact_backends == ("safetensors", "huggingface_hub")
    assert descriptors[3].bridge_cache_root == "/tmp/algenta-hf-cache"
    assert descriptors[3].bridge_auth_env_vars == ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")
    assert descriptors[3].bridge_auth_configured is True
    assert descriptors[4].supported_endpoints == (
        "/v1/models",
        "/v1/tokenize",
        "/v1/count_tokens",
        "/v1/chat/completions",
        "/v1/responses",
    )
    assert descriptors[4].tokenizer_kind == "word"
    assert descriptors[4].bridge_tokenizer_backends == ("tiktoken", "tokenizers")
    assert descriptors[4].bridge_artifact_backends == ("safetensors", "huggingface_hub")
    assert descriptors[4].bridge_cache_root == "/tmp/algenta-hf-cache"
    assert descriptors[4].bridge_auth_env_vars == ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")
    assert descriptors[4].bridge_auth_configured is True


def test_list_llm_model_descriptors_resolves_hf_home_cache_root(monkeypatch) -> None:
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.setenv("HF_HOME", "/tmp/algenta-hf-home")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service,
        "_detect_bridge_backends",
        lambda specs: ("huggingface_hub",) if specs == llm_api_service._ARTIFACT_BRIDGE_SPECS else (),
    )
    monkeypatch.setattr(llm_api_service.llm_provider_service, "load_provider_model_configs", lambda: ())

    assert llm_api_service.list_llm_model_descriptors() == ()
    assert (
        llm_api_service._resolve_artifact_bridge_cache_root(("safetensors", "huggingface_hub"))
        == "/tmp/algenta-hf-home/hub"
    )
    assert (
        llm_api_service._resolve_artifact_bridge_auth_env_vars(("safetensors", "huggingface_hub"))
        == ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")
    )
    assert llm_api_service._artifact_bridge_auth_configured(("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")) is False


def test_resolve_artifact_bridge_returns_not_cached_for_local_only_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LocalEntryNotFoundError(Exception):
        pass

    monkeypatch.setattr(
        llm_api_service,
        "_detect_bridge_backends",
        lambda specs: ("safetensors", "huggingface_hub")
        if specs == llm_api_service._ARTIFACT_BRIDGE_SPECS
        else (),
    )
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/tmp/algenta-hf-cache")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(
        llm_api_service,
        "_hf_hub_download",
        lambda **kwargs: (_ for _ in ()).throw(LocalEntryNotFoundError(kwargs["filename"])),
    )

    resolved = llm_api_service.resolve_artifact_bridge(
        repo_id="org/model",
        filename="weights.safetensors",
        revision="main",
        local_files_only=True,
    )

    assert resolved.status == "not_cached"
    assert resolved.backend == "huggingface_hub"
    assert resolved.artifact_backend == "safetensors"
    assert resolved.cache_root == "/tmp/algenta-hf-cache"
    assert resolved.auth_env_var_used is None
    assert resolved.resolved_path is None


def test_resolve_artifact_bridge_passes_auth_and_returns_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "_detect_bridge_backends",
        lambda specs: ("safetensors", "huggingface_hub")
        if specs == llm_api_service._ARTIFACT_BRIDGE_SPECS
        else (),
    )
    monkeypatch.setenv("HF_TOKEN", "hf_test")

    def _fake_download(**kwargs: object) -> str:
        assert kwargs == {
            "repo_id": "org/model",
            "filename": "tokenizer.json",
            "revision": "main",
            "cache_root": str(Path.home() / ".cache" / "huggingface" / "hub"),
            "local_files_only": False,
            "auth_token": "hf_test",
        }
        return "/tmp/algenta-hf-cache/models--org--model/tokenizer.json"

    monkeypatch.setattr(llm_api_service, "_hf_hub_download", _fake_download)

    resolved = llm_api_service.resolve_artifact_bridge(
        repo_id="org/model",
        filename="tokenizer.json",
        revision="main",
        local_files_only=False,
    )

    assert resolved.status == "resolved"
    assert resolved.auth_configured is True
    assert resolved.auth_env_var_used == "HF_TOKEN"
    assert resolved.resolved_path == "/tmp/algenta-hf-cache/models--org--model/tokenizer.json"


def test_resolve_artifact_bridge_fails_closed_without_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_api_service, "_detect_bridge_backends", lambda specs: ())

    with pytest.raises(LLMAPIError, match="artifact bridge backend is not available"):
        llm_api_service.resolve_artifact_bridge(
            repo_id="org/model",
            filename="weights.safetensors",
        )


def test_list_llm_model_descriptors_merges_configured_provider_models(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.gpt-4o-mini",
                backend="openai_compatible",
                base_url="https://provider.test/v1",
                upstream_model="gpt-4o-mini",
                api_key_env="OPENAI_API_KEY",
                description="Provider-backed OpenAI-compatible chat model.",
                capabilities=("chat_completions", "embeddings"),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.gpt-4o-mini"]
    assert descriptors[0].runtime_module == "provider.openai_compatible"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "openai_compatible"


def test_list_llm_model_descriptors_supports_anthropic_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.claude-sonnet",
                backend="anthropic",
                base_url="https://api.anthropic.com/v1",
                upstream_model="claude-3-5-sonnet-latest",
                api_key_env="ANTHROPIC_API_KEY",
                description="Provider-backed Anthropic chat model.",
                capabilities=("chat_completions",),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.claude-sonnet"]
    assert descriptors[0].runtime_module == "provider.anthropic"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "anthropic"


def test_list_llm_model_descriptors_supports_openai_backend(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_ORG_ID", "org_test")
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.openai-gpt-4o-mini",
                backend="openai",
                base_url="https://api.openai.com/v1",
                upstream_model="gpt-4o-mini",
                api_key_env="OPENAI_API_KEY",
                description="Provider-backed OpenAI chat model.",
                capabilities=("chat_completions", "embeddings"),
                header_envs=(("OpenAI-Organization", "OPENAI_ORG_ID"),),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.openai-gpt-4o-mini"]
    assert descriptors[0].runtime_module == "provider.openai"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "openai"
    assert descriptors[0].resolved_routing_targets == ()
    assert descriptors[0].resolved_chat_routing_targets == ()
    assert descriptors[0].resolved_embedding_routing_targets == ()
    assert descriptors[0].required_provider_headers == ("OpenAI-Organization",)
    assert descriptors[0].provider_auth_env_vars == ("OPENAI_API_KEY", "OPENAI_ORG_ID")
    assert descriptors[0].provider_auth_configured is True


def test_list_llm_model_descriptors_supports_ollama_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.ollama-gemma3",
                backend="ollama",
                base_url="http://localhost:11434",
                upstream_model="gemma3",
                api_key_env=None,
                description="Provider-backed Ollama model.",
                capabilities=("chat_completions", "embeddings"),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.ollama-gemma3"]
    assert descriptors[0].runtime_module == "provider.ollama"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "ollama"


def test_list_llm_model_descriptors_supports_google_genai_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.gemini-flash",
                backend="google_genai",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                upstream_model="gemini-2.5-flash",
                api_key_env="GEMINI_API_KEY",
                description="Provider-backed Gemini model.",
                capabilities=("chat_completions", "embeddings"),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.gemini-flash"]
    assert descriptors[0].runtime_module == "provider.google_genai"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "google_genai"


def test_list_llm_model_descriptors_supports_mistral_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.mistral-small",
                backend="mistral",
                base_url="https://api.mistral.ai/v1",
                upstream_model="mistral-small-latest",
                api_key_env="MISTRAL_API_KEY",
                description="Provider-backed Mistral model.",
                capabilities=("chat_completions", "embeddings"),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.mistral-small"]
    assert descriptors[0].runtime_module == "provider.mistral"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "mistral"


def test_list_llm_model_descriptors_supports_cohere_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.command-a",
                backend="cohere",
                base_url="https://api.cohere.com",
                upstream_model="command-a-03-2025",
                api_key_env="COHERE_API_KEY",
                description="Provider-backed Cohere model.",
                capabilities=("chat_completions", "embeddings"),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.command-a"]
    assert descriptors[0].runtime_module == "provider.cohere"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "cohere"


def test_list_llm_model_descriptors_supports_groq_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.groq-llama",
                backend="groq",
                base_url="https://api.groq.com/openai/v1",
                upstream_model="llama-3.3-70b-versatile",
                api_key_env="GROQ_API_KEY",
                description="Provider-backed Groq model.",
                capabilities=("chat_completions",),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.groq-llama"]
    assert descriptors[0].runtime_module == "provider.groq"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "groq"


def test_list_llm_model_descriptors_supports_xai_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.xai-grok",
                backend="xai",
                base_url="https://api.x.ai/v1",
                upstream_model="grok-4.3",
                api_key_env="XAI_API_KEY",
                description="Provider-backed xAI model.",
                capabilities=("chat_completions", "embeddings"),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.xai-grok"]
    assert descriptors[0].runtime_module == "provider.xai"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "xai"


def test_list_llm_model_descriptors_supports_router_backend(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.router",
                backend="router",
                base_url="",
                upstream_model="provider.router",
                api_key_env=None,
                description="Ordered provider router alias.",
                capabilities=("chat_completions", "embeddings"),
                routing_targets=("provider.fast", "provider.primary"),
                routing_fallback_policy="disabled",
                chat_routing_fallback_policy="retryable_only",
                embedding_routing_fallback_policy="disabled",
                routing_fallback_on=("provider_timeout",),
                chat_routing_fallback_on=("provider_rate_limited",),
                embedding_routing_fallback_on=("provider_backend_error",),
                routing_max_attempts=2,
                chat_routing_max_attempts=1,
                embedding_routing_max_attempts=2,
                timeout_seconds=18.0,
                chat_timeout_seconds=12.5,
                embedding_timeout_seconds=9.0,
            ),
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_required_header_names",
        lambda *, model_id: ("OpenAI-Organization",)
        if model_id == "provider.router"
        else (),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_required_header_names_for_capability",
        lambda *, model_id, capability: (
            ("OpenAI-Organization",)
            if model_id == "provider.router" and capability == "embeddings"
            else ("X-Groq-Team",)
            if model_id == "provider.router" and capability == "chat_completions"
            else ()
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_required_auth_env_vars",
        lambda *, model_id: ("GROQ_API_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID")
        if model_id == "provider.router"
        else (),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_required_auth_env_vars_for_capability",
        lambda *, model_id, capability: (
            ("GROQ_API_KEY", "GROQ_TEAM_ID")
            if model_id == "provider.router" and capability == "chat_completions"
            else ("OPENAI_API_KEY", "OPENAI_ORG_ID")
            if model_id == "provider.router" and capability == "embeddings"
            else ()
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "provider_auth_configured",
        lambda *, model_id: model_id == "provider.router",
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "provider_auth_configured_for_capability",
        lambda *, model_id, capability: (
            model_id == "provider.router" and capability == "chat_completions"
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_resolved_route_targets",
        lambda *, model_id: ("provider.fast", "provider.primary")
        if model_id == "provider.router"
        else (),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_resolved_chat_route_targets",
        lambda *, model_id: ("provider.fast", "provider.primary")
        if model_id == "provider.router"
        else (),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "get_provider_resolved_embedding_route_targets",
        lambda *, model_id: ("provider.primary",)
        if model_id == "provider.router"
        else (),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert [descriptor.model_id for descriptor in descriptors] == ["provider.router"]
    assert descriptors[0].runtime_module == "provider.router"
    assert descriptors[0].supported_endpoints == (
        "/v1/models",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/responses",
    )
    assert descriptors[0].provider_backend == "router"
    assert descriptors[0].routing_targets == ("provider.fast", "provider.primary")
    assert descriptors[0].resolved_routing_targets == ("provider.fast", "provider.primary")
    assert descriptors[0].chat_routing_targets == ()
    assert descriptors[0].resolved_chat_routing_targets == ("provider.fast", "provider.primary")
    assert descriptors[0].embedding_routing_targets == ()
    assert descriptors[0].resolved_embedding_routing_targets == ("provider.primary",)
    assert descriptors[0].routing_fallback_policy == "disabled"
    assert descriptors[0].chat_routing_fallback_policy == "retryable_only"
    assert descriptors[0].embedding_routing_fallback_policy == "disabled"
    assert descriptors[0].routing_fallback_on == ("provider_timeout",)
    assert descriptors[0].chat_routing_fallback_on == ("provider_rate_limited",)
    assert descriptors[0].embedding_routing_fallback_on == ("provider_backend_error",)
    assert descriptors[0].routing_max_attempts == 2
    assert descriptors[0].chat_routing_max_attempts == 1
    assert descriptors[0].embedding_routing_max_attempts == 2
    assert descriptors[0].timeout_seconds == 18.0
    assert descriptors[0].chat_timeout_seconds == 12.5
    assert descriptors[0].embedding_timeout_seconds == 9.0
    assert descriptors[0].required_provider_headers == ("OpenAI-Organization",)
    assert descriptors[0].chat_required_provider_headers == ("X-Groq-Team",)
    assert descriptors[0].embedding_required_provider_headers == ("OpenAI-Organization",)
    assert descriptors[0].provider_auth_env_vars == (
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
    )
    assert descriptors[0].chat_provider_auth_env_vars == ("GROQ_API_KEY", "GROQ_TEAM_ID")
    assert descriptors[0].embedding_provider_auth_env_vars == (
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
    )
    assert descriptors[0].provider_auth_configured is True
    assert descriptors[0].chat_provider_auth_configured is True
    assert descriptors[0].embedding_provider_auth_configured is False


def test_list_llm_model_descriptors_respects_router_max_attempts_in_resolved_metadata(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.primary",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.backup",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "gpt-4.1-mini",
                    "api_key_env": "BACKUP_API_KEY",
                    "header_envs": {"X-Provider-Tenant": "BACKUP_TENANT_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary", "provider.backup"],
                    "max_attempts": 1,
                },
            ]
        ),
    )
    llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        descriptors = llm_api_service.list_llm_model_descriptors()
    finally:
        llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()

    router_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.model_id == "provider.router"
    )
    assert router_descriptor.routing_targets == ("provider.primary", "provider.backup")
    assert router_descriptor.resolved_routing_targets == ("provider.primary",)
    assert router_descriptor.resolved_chat_routing_targets == ("provider.primary",)
    assert router_descriptor.required_provider_headers == ("OpenAI-Organization",)
    assert router_descriptor.provider_auth_env_vars == ("OPENAI_API_KEY", "OPENAI_ORG_ID")


def test_list_llm_model_descriptors_max_attempts_skip_incapable_targets(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"X-Provider-Tenant": "OPENAI_TENANT_ID"},
                    "capabilities": ["embeddings"],
                },
                {
                    "id": "provider.primary",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.embedder", "provider.primary"],
                    "max_attempts": 1,
                },
            ]
        ),
    )
    llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        descriptors = llm_api_service.list_llm_model_descriptors()
    finally:
        llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()

    router_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.model_id == "provider.router"
    )
    assert router_descriptor.routing_targets == ("provider.embedder", "provider.primary")
    assert router_descriptor.resolved_routing_targets == ("provider.primary",)
    assert router_descriptor.resolved_chat_routing_targets == ("provider.primary",)
    assert router_descriptor.required_provider_headers == ("OpenAI-Organization",)
    assert router_descriptor.provider_auth_env_vars == ("OPENAI_API_KEY", "OPENAI_ORG_ID")


def test_list_llm_model_descriptors_respects_disabled_router_fallback_in_resolved_metadata(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setenv(
        "ALGENTA_LLM_PROVIDER_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "provider.primary",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.backup",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "gpt-4.1-mini",
                    "api_key_env": "BACKUP_API_KEY",
                    "header_envs": {"X-Provider-Tenant": "BACKUP_TENANT_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.router",
                    "backend": "router",
                    "capabilities": ["chat_completions"],
                    "targets": ["provider.primary", "provider.backup"],
                    "fallback_policy": "disabled",
                },
            ]
        ),
    )
    llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        descriptors = llm_api_service.list_llm_model_descriptors()
    finally:
        llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()

    router_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.model_id == "provider.router"
    )
    assert router_descriptor.routing_targets == ("provider.primary", "provider.backup")
    assert router_descriptor.resolved_routing_targets == ("provider.primary",)
    assert router_descriptor.resolved_chat_routing_targets == ("provider.primary",)
    assert router_descriptor.required_provider_headers == ("OpenAI-Organization",)
    assert router_descriptor.provider_auth_env_vars == ("OPENAI_API_KEY", "OPENAI_ORG_ID")


def test_list_llm_model_descriptors_disabled_fallback_skips_incapable_targets(
    monkeypatch,
) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
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
                    "header_envs": {"X-Groq-Team": "GROQ_TEAM_ID"},
                    "capabilities": ["chat_completions"],
                },
                {
                    "id": "provider.embedder",
                    "backend": "openai_compatible",
                    "base_url": "https://provider.test/v1",
                    "model_name": "text-embedding-3-small",
                    "api_key_env": "OPENAI_API_KEY",
                    "header_envs": {"X-Provider-Tenant": "OPENAI_TENANT_ID"},
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
    llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        descriptors = llm_api_service.list_llm_model_descriptors()
    finally:
        llm_api_service.llm_provider_service.load_provider_model_configs.cache_clear()

    router_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.model_id == "provider.router"
    )
    assert router_descriptor.routing_targets == ("provider.fast", "provider.embedder")
    assert router_descriptor.resolved_routing_targets == ("provider.fast", "provider.embedder")
    assert router_descriptor.resolved_chat_routing_targets == ("provider.fast",)
    assert router_descriptor.resolved_embedding_routing_targets == ("provider.embedder",)
    assert router_descriptor.required_provider_headers == (
        "X-Groq-Team",
        "X-Provider-Tenant",
    )
    assert router_descriptor.chat_required_provider_headers == ("X-Groq-Team",)
    assert router_descriptor.embedding_required_provider_headers == ("X-Provider-Tenant",)
    assert router_descriptor.provider_auth_env_vars == (
        "GROQ_API_KEY",
        "GROQ_TEAM_ID",
        "OPENAI_API_KEY",
        "OPENAI_TENANT_ID",
    )
    assert router_descriptor.chat_provider_auth_env_vars == ("GROQ_API_KEY", "GROQ_TEAM_ID")
    assert router_descriptor.embedding_provider_auth_env_vars == (
        "OPENAI_API_KEY",
        "OPENAI_TENANT_ID",
    )
    assert router_descriptor.chat_provider_auth_configured is False
    assert router_descriptor.embedding_provider_auth_configured is False


def test_list_llm_model_descriptors_fails_closed_for_invalid_provider_config(monkeypatch) -> None:
    monkeypatch.setattr(llm_api_service, "list_public_runtime_library_descriptors", lambda: ())
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(
            status="ok",
            engine="mojo",
            module_count=0,
            runtime_available=True,
        ),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (_ for _ in ()).throw(ValueError("bad provider config")),
    )

    with pytest.raises(LLMAPIError, match="Provider model configuration is invalid."):
        llm_api_service.list_llm_model_descriptors()


@pytest.mark.anyio
async def test_embedding_similarity_score_rejects_mismatched_dimensions(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="embeddings",
            description="Cosine similarity over caller-supplied embedding vectors.",
            capabilities=("embedding_similarity", "rerank"),
            supported_endpoints=("/v1/models", "/v1/embeddings/similarity", "/v1/rerank"),
            tokenizer_kind=None,
            similarity_metric="cosine",
            runtime_functions=("cosine_similarity",),
            available=True,
        ),
    )

    async def _unexpected_execute(**kwargs: object) -> object:
        raise AssertionError(f"runtime execution should not occur: {kwargs}")

    monkeypatch.setattr(llm_api_service, "execute_public_runtime_library", _unexpected_execute)

    with pytest.raises(LLMAPIError, match="Embedding vectors must have identical dimensions."):
        await llm_api_service.embedding_similarity_score(
            model_id="embeddings.cosine_similarity",
            left=[1.0, 0.0, 0.0],
            right=[1.0, 0.0],
        )


@pytest.mark.anyio
async def test_embedding_similarity_score_returns_float(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="embeddings",
            description="Cosine similarity over caller-supplied embedding vectors.",
            capabilities=("embedding_similarity", "rerank"),
            supported_endpoints=("/v1/models", "/v1/embeddings/similarity", "/v1/rerank"),
            tokenizer_kind=None,
            similarity_metric="cosine",
            runtime_functions=("cosine_similarity",),
            available=True,
        ),
    )

    async def _fake_execute(**kwargs: object):
        assert kwargs == {
            "module": "embeddings",
            "function": "cosine_similarity",
            "args": [[1.0, 0.0], [1.0, 0.0]],
        }
        return SimpleNamespace(
            module="embeddings",
            function="cosine_similarity",
            result=1,
            latency_ms=1.25,
            engine_used="mojo",
            request_id=None,
        )

    monkeypatch.setattr(llm_api_service, "execute_public_runtime_library", _fake_execute)

    descriptor, score = await llm_api_service.embedding_similarity_score(
        model_id="embeddings.cosine_similarity",
        left=[1.0, 0.0],
        right=[1.0, 0.0],
    )

    assert descriptor.similarity_metric == "cosine"
    assert score == 1.0


@pytest.mark.anyio
async def test_rerank_embeddings_returns_deterministic_rank_order(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="embeddings",
            description="Cosine similarity over caller-supplied embedding vectors.",
            capabilities=("embedding_similarity", "rerank"),
            supported_endpoints=("/v1/models", "/v1/embeddings/similarity", "/v1/rerank"),
            tokenizer_kind=None,
            similarity_metric="cosine",
            runtime_functions=("cosine_similarity",),
            available=True,
        ),
    )

    execution_args: list[dict[str, object]] = []

    async def _fake_execute(**kwargs: object):
        execution_args.append(kwargs)
        right = kwargs["args"][1]
        score_map = {
            (1.0, 0.0): 1.0,
            (0.8, 0.2): 1.0,
            (0.2, 0.8): 0.2,
        }
        return SimpleNamespace(
            module="embeddings",
            function="cosine_similarity",
            result=score_map[tuple(right)],
            latency_ms=1.0,
            engine_used="mojo",
            request_id=None,
        )

    monkeypatch.setattr(llm_api_service, "execute_public_runtime_library", _fake_execute)

    descriptor, ranked = await llm_api_service.rerank_embeddings(
        model_id="embeddings.cosine_similarity",
        query_embedding=[1.0, 0.0],
        documents=[
            {"id": "doc_a", "embedding": [0.8, 0.2], "text": "alpha", "metadata": {"tier": 2}},
            {"id": "doc_b", "embedding": [1.0, 0.0], "text": "beta", "metadata": {"tier": 1}},
            {"id": "doc_c", "embedding": [0.2, 0.8]},
        ],
        top_n=2,
    )

    assert descriptor.model_id == "embeddings.cosine_similarity"
    assert execution_args == [
        {"module": "embeddings", "function": "cosine_similarity", "args": [[1.0, 0.0], [0.8, 0.2]]},
        {"module": "embeddings", "function": "cosine_similarity", "args": [[1.0, 0.0], [1.0, 0.0]]},
        {"module": "embeddings", "function": "cosine_similarity", "args": [[1.0, 0.0], [0.2, 0.8]]},
    ]
    assert ranked == [
        llm_api_service.RerankDocumentResult(
            document_id="doc_a",
            index=0,
            rank=1,
            score=1.0,
            text="alpha",
            metadata={"tier": 2},
        ),
        llm_api_service.RerankDocumentResult(
            document_id="doc_b",
            index=1,
            rank=2,
            score=1.0,
            text="beta",
            metadata={"tier": 1},
        ),
    ]


@pytest.mark.anyio
async def test_rerank_embeddings_rejects_mismatched_dimensions(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "get_llm_model_descriptor",
        lambda model_id: llm_api_service.LLMModelDescriptor(
            model_id=model_id,
            runtime_module="embeddings",
            description="Cosine similarity over caller-supplied embedding vectors.",
            capabilities=("embedding_similarity", "rerank"),
            supported_endpoints=("/v1/models", "/v1/embeddings/similarity", "/v1/rerank"),
            tokenizer_kind=None,
            similarity_metric="cosine",
            runtime_functions=("cosine_similarity",),
            available=True,
        ),
    )

    async def _unexpected_execute(**kwargs: object) -> object:
        raise AssertionError(f"runtime execution should not occur: {kwargs}")

    monkeypatch.setattr(llm_api_service, "execute_public_runtime_library", _unexpected_execute)

    with pytest.raises(LLMAPIError, match="Embedding vectors must have identical dimensions."):
        await llm_api_service.rerank_embeddings(
            model_id="embeddings.cosine_similarity",
            query_embedding=[1.0, 0.0, 0.0],
            documents=[
                {"id": "doc_a", "embedding": [1.0, 0.0]},
            ],
            top_n=None,
        )


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
