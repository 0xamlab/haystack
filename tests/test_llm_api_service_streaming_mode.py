"""Track C2 (real per-backend streaming): GET /v1/models must truthfully report streaming_mode.

Exercises the real list_llm_model_descriptors() -> _features.py wiring (not a hand-mocked
descriptor) for a passthrough-capable backend, a deferred-synthetic backend, and a router model
that resolves to a passthrough leaf target.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


def _runtime_stub(monkeypatch) -> None:
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


def test_streaming_mode_passthrough_for_openai_backend(monkeypatch) -> None:
    _runtime_stub(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
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
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert descriptors[0].model_id == "provider.openai-gpt-4o-mini"
    assert descriptors[0].streaming_mode == "passthrough"
    assert "stream" in descriptors[0].supported_parameters
    assert "tools" in descriptors[0].supported_parameters


def test_streaming_mode_passthrough_for_anthropic_backend(monkeypatch) -> None:
    _runtime_stub(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak-test")
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
                description="Provider-backed chat model.",
                capabilities=("chat_completions",),
            ),
        ),
    )

    descriptors = llm_api_service.list_llm_model_descriptors()

    assert descriptors[0].streaming_mode == "passthrough"


def test_streaming_mode_synthetic_for_each_deferred_backend(monkeypatch) -> None:
    _runtime_stub(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    monkeypatch.setenv("COHERE_API_KEY", "co-test")
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
                description="Provider-backed chat model.",
                capabilities=("chat_completions",),
            ),
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.command-a",
                backend="cohere",
                base_url="https://api.cohere.com",
                upstream_model="command-a-03-2025",
                api_key_env="COHERE_API_KEY",
                description="Provider-backed Cohere chat model.",
                capabilities=("chat_completions",),
            ),
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.ollama-gemma3",
                backend="ollama",
                base_url="http://localhost:11434",
                upstream_model="gemma3",
                api_key_env=None,
                description="Provider-backed Ollama model.",
                capabilities=("chat_completions",),
            ),
        ),
    )

    descriptors = {d.model_id: d for d in llm_api_service.list_llm_model_descriptors()}

    assert descriptors["provider.gemini-flash"].streaming_mode == "synthetic"
    assert descriptors["provider.command-a"].streaming_mode == "synthetic"
    assert descriptors["provider.ollama-gemma3"].streaming_mode == "synthetic"


def test_streaming_mode_synthetic_for_non_provider_tokenizer_model(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "list_public_runtime_library_descriptors",
        lambda: (SimpleNamespace(name="text.tokenizer", functions=("word_tokenize",)),),
    )
    monkeypatch.setattr(
        llm_api_service,
        "get_public_runtime_library_health",
        lambda: SimpleNamespace(status="ok", engine="mojo", module_count=1, runtime_available=True),
    )
    monkeypatch.setattr(
        llm_api_service.llm_provider_service, "load_provider_model_configs", lambda: ()
    )

    descriptors = {d.model_id: d for d in llm_api_service.list_llm_model_descriptors()}

    assert descriptors["text.tokenizer"].streaming_mode == "synthetic"


def test_streaming_mode_router_resolves_to_passthrough_leaf_target(monkeypatch) -> None:
    _runtime_stub(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gq-test")
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.router",
                backend="router",
                base_url="",
                upstream_model="",
                api_key_env=None,
                description="Ordered provider router alias.",
                capabilities=("chat_completions",),
                chat_routing_targets=("provider.groq-llama",),
            ),
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.groq-llama",
                backend="groq",
                base_url="https://api.groq.com/openai/v1",
                upstream_model="llama-3.3-70b-versatile",
                api_key_env="GROQ_API_KEY",
                description="Provider-backed Groq chat model.",
                capabilities=("chat_completions",),
            ),
        ),
    )

    descriptors = {d.model_id: d for d in llm_api_service.list_llm_model_descriptors()}

    assert descriptors["provider.router"].streaming_mode == "passthrough"
    assert descriptors["provider.groq-llama"].streaming_mode == "passthrough"


def test_streaming_mode_router_resolves_to_synthetic_leaf_target(monkeypatch) -> None:
    _runtime_stub(monkeypatch)
    monkeypatch.setattr(
        llm_api_service.llm_provider_service,
        "load_provider_model_configs",
        lambda: (
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.router",
                backend="router",
                base_url="",
                upstream_model="",
                api_key_env=None,
                description="Ordered provider router alias.",
                capabilities=("chat_completions",),
                chat_routing_targets=("provider.ollama-gemma3",),
            ),
            llm_api_service.llm_provider_service.ProviderModelConfig(
                model_id="provider.ollama-gemma3",
                backend="ollama",
                base_url="http://localhost:11434",
                upstream_model="gemma3",
                api_key_env=None,
                description="Provider-backed Ollama model.",
                capabilities=("chat_completions",),
            ),
        ),
    )

    descriptors = {d.model_id: d for d in llm_api_service.list_llm_model_descriptors()}

    assert descriptors["provider.router"].streaming_mode == "synthetic"
