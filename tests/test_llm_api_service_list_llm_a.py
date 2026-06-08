"""Tests for test_llm_api_service: list_llm_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


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


