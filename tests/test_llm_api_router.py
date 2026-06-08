from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.main import app
from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import llm as llm_router
from apps.api_server.services.llm_api_service import LLMAPIError, LLMModelDescriptor
from apps.runtime.mojo_library_runner import MojoLibraryError
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]


async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_llm_api",
        "key_id": "key_llm_api",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


def _tokenizer_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="text.tokenizer",
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
        runtime_functions=("word_tokenize", "sentence_tokenize"),
        bridge_cache_root="/tmp/algenta-hf-cache",
        bridge_auth_env_vars=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
        bridge_auth_configured=True,
        bridge_tokenizer_backends=("tiktoken", "sentencepiece"),
        bridge_artifact_backends=("safetensors", "huggingface_hub"),
        available=available,
    )


def _embedding_generation_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="text.hash_embedding_v1",
        runtime_module="text.tokenizer",
        description="Deterministic lexical hash embeddings generated from runtime tokenization and stable feature hashing.",
        capabilities=("embeddings",),
        supported_endpoints=("/v1/models", "/v1/embeddings", "/v1/responses"),
        tokenizer_kind="word",
        similarity_metric=None,
        runtime_functions=("word_tokenize",),
        bridge_cache_root="/tmp/algenta-hf-cache",
        bridge_auth_env_vars=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
        bridge_auth_configured=True,
        bridge_tokenizer_backends=("tiktoken", "sentencepiece"),
        bridge_artifact_backends=("safetensors", "huggingface_hub"),
        available=available,
    )


def _embedding_similarity_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="embeddings.cosine_similarity",
        runtime_module="embeddings",
        description="Cosine similarity over caller-supplied embedding vectors.",
        capabilities=("embedding_similarity", "rerank"),
        supported_endpoints=("/v1/models", "/v1/embeddings/similarity", "/v1/rerank"),
        tokenizer_kind=None,
        similarity_metric="cosine",
        runtime_functions=("cosine_similarity",),
        bridge_cache_root=None,
        bridge_auth_env_vars=(),
        bridge_auth_configured=False,
        bridge_tokenizer_backends=(),
        bridge_artifact_backends=(),
        available=available,
    )


def _provider_chat_model_descriptor(*, available: bool = True) -> LLMModelDescriptor:
    return LLMModelDescriptor(
        model_id="provider.gpt-4o-mini",
        runtime_module="provider.openai_compatible",
        description="Provider-backed OpenAI-compatible chat model.",
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
        provider_backend="openai_compatible",
        bridge_cache_root=None,
        bridge_auth_env_vars=(),
        bridge_auth_configured=False,
        bridge_tokenizer_backends=(),
        bridge_artifact_backends=(),
        available=available,
    )


async def _noop_rate_limit(*, request: object, auth: object, redis_client: object) -> None:
    del request, auth, redis_client


def test_llm_models_route_requires_authentication() -> None:
    async def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_llm_models_route_lists_truthful_tokenizer_catalog(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router,
        "list_llm_model_descriptors",
        lambda: (_tokenizer_model_descriptor(),),
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "list"
    assert payload["data"] == [
        {
            "id": "text.tokenizer",
            "object": "model",
            "owned_by": "algenta",
            "runtime_module": "text.tokenizer",
            "description": "Deterministic word tokenizer backed by the runtime library catalog.",
            "capabilities": ["tokenize", "count_tokens", "chat_completions"],
            "supported_endpoints": [
                "/v1/models",
                "/v1/tokenize",
                "/v1/count_tokens",
                "/v1/chat/completions",
                "/v1/responses",
            ],
            "runtime_functions": ["word_tokenize", "sentence_tokenize"],
            "tokenizer_kind": "word",
            "similarity_metric": None,
            "provider_backend": None,
            "routing_targets": [],
            "resolved_routing_targets": [],
            "chat_routing_targets": [],
            "resolved_chat_routing_targets": [],
            "embedding_routing_targets": [],
            "resolved_embedding_routing_targets": [],
            "routing_fallback_policy": None,
            "chat_routing_fallback_policy": None,
            "embedding_routing_fallback_policy": None,
            "routing_fallback_on": [],
            "chat_routing_fallback_on": [],
            "embedding_routing_fallback_on": [],
            "routing_max_attempts": None,
            "chat_routing_max_attempts": None,
            "embedding_routing_max_attempts": None,
            "timeout_seconds": None,
            "chat_timeout_seconds": None,
            "embedding_timeout_seconds": None,
            "required_provider_headers": [],
            "chat_required_provider_headers": [],
            "embedding_required_provider_headers": [],
            "provider_auth_env_vars": [],
            "chat_provider_auth_env_vars": [],
            "embedding_provider_auth_env_vars": [],
            "provider_auth_configured": False,
            "chat_provider_auth_configured": False,
            "embedding_provider_auth_configured": False,
            "bridge_cache_root": "/tmp/algenta-hf-cache",
            "bridge_auth_env_vars": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
            "bridge_auth_configured": True,
            "bridge_tokenizer_backends": ["tiktoken", "sentencepiece"],
            "bridge_artifact_backends": ["safetensors", "huggingface_hub"],
            "available": True,
        }
    ]


def test_llm_models_route_surfaces_router_target_metadata(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router,
        "list_llm_model_descriptors",
        lambda: (
            LLMModelDescriptor(
                model_id="provider.router",
                runtime_module="provider.router",
                description="Ordered provider router alias.",
                capabilities=("chat_completions", "embeddings"),
                supported_endpoints=(
                    "/v1/models",
                    "/v1/chat/completions",
                    "/v1/embeddings",
                    "/v1/responses",
                ),
                runtime_functions=(),
                tokenizer_kind=None,
                similarity_metric=None,
                provider_backend="router",
                routing_targets=(),
                resolved_routing_targets=(),
                chat_routing_targets=("provider.fast", "provider.primary"),
                resolved_chat_routing_targets=("provider.fast", "provider.primary"),
                embedding_routing_targets=("provider.embedder", "provider.primary"),
                resolved_embedding_routing_targets=("provider.embedder", "provider.primary"),
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
                required_provider_headers=("OpenAI-Organization",),
                chat_required_provider_headers=("X-Groq-Team",),
                embedding_required_provider_headers=("OpenAI-Organization",),
                provider_auth_env_vars=("GROQ_API_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID"),
                chat_provider_auth_env_vars=("GROQ_API_KEY", "GROQ_TEAM_ID"),
                embedding_provider_auth_env_vars=("OPENAI_API_KEY", "OPENAI_ORG_ID"),
                provider_auth_configured=True,
                chat_provider_auth_configured=True,
                embedding_provider_auth_configured=False,
                bridge_cache_root=None,
                bridge_auth_env_vars=(),
                bridge_auth_configured=False,
                bridge_tokenizer_backends=(),
                bridge_artifact_backends=(),
                available=True,
            ),
        ),
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["provider_backend"] == "router"
    assert payload["data"][0]["routing_targets"] == []
    assert payload["data"][0]["resolved_routing_targets"] == []
    assert payload["data"][0]["chat_routing_targets"] == ["provider.fast", "provider.primary"]
    assert payload["data"][0]["resolved_chat_routing_targets"] == [
        "provider.fast",
        "provider.primary",
    ]
    assert payload["data"][0]["embedding_routing_targets"] == [
        "provider.embedder",
        "provider.primary",
    ]
    assert payload["data"][0]["resolved_embedding_routing_targets"] == [
        "provider.embedder",
        "provider.primary",
    ]
    assert payload["data"][0]["routing_fallback_policy"] == "disabled"
    assert payload["data"][0]["chat_routing_fallback_policy"] == "retryable_only"
    assert payload["data"][0]["embedding_routing_fallback_policy"] == "disabled"
    assert payload["data"][0]["routing_fallback_on"] == ["provider_timeout"]
    assert payload["data"][0]["chat_routing_fallback_on"] == ["provider_rate_limited"]
    assert payload["data"][0]["embedding_routing_fallback_on"] == ["provider_backend_error"]
    assert payload["data"][0]["routing_max_attempts"] == 2
    assert payload["data"][0]["chat_routing_max_attempts"] == 1
    assert payload["data"][0]["embedding_routing_max_attempts"] == 2
    assert payload["data"][0]["timeout_seconds"] == 18.0
    assert payload["data"][0]["chat_timeout_seconds"] == 12.5
    assert payload["data"][0]["embedding_timeout_seconds"] == 9.0
    assert payload["data"][0]["required_provider_headers"] == ["OpenAI-Organization"]
    assert payload["data"][0]["chat_required_provider_headers"] == ["X-Groq-Team"]
    assert payload["data"][0]["embedding_required_provider_headers"] == [
        "OpenAI-Organization"
    ]
    assert payload["data"][0]["provider_auth_env_vars"] == [
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
    ]
    assert payload["data"][0]["chat_provider_auth_env_vars"] == [
        "GROQ_API_KEY",
        "GROQ_TEAM_ID",
    ]
    assert payload["data"][0]["embedding_provider_auth_env_vars"] == [
        "OPENAI_API_KEY",
        "OPENAI_ORG_ID",
    ]
    assert payload["data"][0]["provider_auth_configured"] is True
    assert payload["data"][0]["chat_provider_auth_configured"] is True
    assert payload["data"][0]["embedding_provider_auth_configured"] is False


def test_artifact_bridge_route_returns_resolution_payload(monkeypatch) -> None:
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(
        llm_router,
        "resolve_artifact_bridge",
        lambda **kwargs: SimpleNamespace(
            backend="huggingface_hub",
            artifact_backend="safetensors",
            repo_id=kwargs["repo_id"],
            filename=kwargs["filename"],
            revision=kwargs["revision"],
            local_files_only=kwargs["local_files_only"],
            status="resolved",
            cache_root="/tmp/algenta-hf-cache",
            auth_env_vars=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
            auth_configured=True,
            auth_env_var_used="HF_TOKEN",
            resolved_path="/tmp/algenta-hf-cache/model.safetensors",
        ),
    )
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/artifacts/resolve",
                json={
                    "repo_id": "org/model",
                    "filename": "model.safetensors",
                    "revision": "main",
                    "local_files_only": False,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "object": "artifact_bridge_resolution",
        "backend": "huggingface_hub",
        "artifact_backend": "safetensors",
        "repo_id": "org/model",
        "filename": "model.safetensors",
        "revision": "main",
        "local_files_only": False,
        "status": "resolved",
        "cache_root": "/tmp/algenta-hf-cache",
        "auth_env_vars": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
        "auth_configured": True,
        "auth_env_var_used": "HF_TOKEN",
        "resolved_path": "/tmp/algenta-hf-cache/model.safetensors",
    }


def test_artifact_bridge_route_maps_backend_unavailable_to_503(monkeypatch) -> None:
    def _fail(**_: object) -> object:
        raise LLMAPIError(
            "artifact_bridge_backend_unavailable",
            "The Hugging Face artifact bridge backend is not available in the current checkout.",
            {"required_backend": "huggingface_hub"},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "resolve_artifact_bridge", _fail)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/artifacts/resolve",
                json={"repo_id": "org/model", "filename": "weights.safetensors"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "artifact_bridge_backend_unavailable"


def test_tokenize_route_returns_tokens_and_count(monkeypatch) -> None:
    async def _fake_tokenize(*, model_id: str, text: str) -> tuple[LLMModelDescriptor, list[str]]:
        assert model_id == "text.tokenizer"
        assert text == "alpha beta gamma"
        return _tokenizer_model_descriptor(), ["alpha", "beta", "gamma"]

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "tokenize_text", _fake_tokenize)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/tokenize",
                json={"model": "text.tokenizer", "input": "alpha beta gamma"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "object": "tokenization",
        "model": "text.tokenizer",
        "tokenizer_kind": "word",
        "tokens": ["alpha", "beta", "gamma"],
        "token_count": 3,
    }


def test_count_tokens_route_rejects_unknown_model(monkeypatch) -> None:
    async def _fake_count(*, model_id: str, text: str) -> tuple[LLMModelDescriptor, int]:
        del text
        raise LLMAPIError(
            "model_not_supported",
            f"Model '{model_id}' is not available on the current Algenta LLM API surface.",
            {"model": model_id},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "count_text_tokens", _fake_count)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/count_tokens",
                json={"model": "does.not.exist", "input": "alpha beta"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "model_not_supported"
    assert (
        error["message"]
        == "Model 'does.not.exist' is not available on the current Algenta LLM API surface."
    )
    assert error["details"] == {"model": "does.not.exist"}
    assert isinstance(error["request_id"], str)


def test_tokenize_route_surfaces_runtime_unavailable(monkeypatch) -> None:
    async def _fake_tokenize(*, model_id: str, text: str) -> tuple[LLMModelDescriptor, list[str]]:
        del model_id, text
        raise MojoLibraryError(
            "compute_runtime_unavailable",
            "Compiled Mojo worker execution is unavailable for text.tokenizer.word_tokenize.",
            {"module": "text.tokenizer", "function": "word_tokenize"},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "tokenize_text", _fake_tokenize)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/tokenize",
                json={"model": "text.tokenizer", "input": "alpha beta"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "compute_runtime_unavailable"
    assert (
        error["message"]
        == "Compiled Mojo worker execution is unavailable for text.tokenizer.word_tokenize."
    )
    assert error["details"] == {"module": "text.tokenizer", "function": "word_tokenize"}
    assert isinstance(error["request_id"], str)


def test_chat_completions_route_surfaces_provider_backend_unavailable(monkeypatch) -> None:
    async def _fake_chat(*, model_id: str, messages: list[dict[str, str]]):
        del model_id, messages
        raise LLMAPIError(
            "backend_unavailable",
            "Provider-backed model 'provider.gpt-4o-mini' is configured, but environment variable 'OPENAI_API_KEY' is not set.",
            {"model": "provider.gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "backend_unavailable"
    assert error["details"] == {
        "model": "provider.gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    }
    assert isinstance(error["request_id"], str)


def test_chat_completions_route_surfaces_provider_rate_limit(monkeypatch) -> None:
    async def _fake_chat(*, model_id: str, messages: list[dict[str, str]]):
        del model_id, messages
        raise LLMAPIError(
            "provider_rate_limited",
            "Provider backend rate limited model 'provider.gpt-4o-mini'.",
            {"model": "provider.gpt-4o-mini", "status_code": 429},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "provider_rate_limited"
    assert error["details"] == {"model": "provider.gpt-4o-mini", "status_code": 429}
    assert isinstance(error["request_id"], str)


def test_chat_completions_route_surfaces_invalid_provider_request(monkeypatch) -> None:
    async def _fake_chat(*, model_id: str, messages: list[dict[str, str]]):
        del model_id, messages
        raise LLMAPIError(
            "invalid_provider_request",
            "Provider backend rejected the request for model 'provider.gpt-4o-mini'.",
            {"model": "provider.gpt-4o-mini", "status_code": 400},
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_provider_request"
    assert error["details"] == {"model": "provider.gpt-4o-mini", "status_code": 400}
    assert isinstance(error["request_id"], str)


def test_openapi_declares_llm_api_routes_with_protected_security() -> None:
    with SyncASGIClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paths"]["/v1/models"]["get"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert payload["paths"]["/v1/chat/completions"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        "text/event-stream"
        in payload["paths"]["/v1/chat/completions"]["post"]["responses"]["200"]["content"]
    )
    assert payload["paths"]["/v1/tokenize"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert payload["paths"]["/v1/count_tokens"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert payload["paths"]["/v1/responses"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        "text/event-stream"
        in payload["paths"]["/v1/responses"]["post"]["responses"]["200"]["content"]
    )
    assert payload["paths"]["/v1/embeddings"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        payload["paths"]["/v1/embeddings/similarity"]["post"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert payload["paths"]["/v1/rerank"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY


def test_embeddings_route_returns_deterministic_vectors(monkeypatch) -> None:
    async def _fake_create_embeddings(
        *,
        model_id: str,
        inputs: list[str],
        dimensions: int,
    ):
        assert model_id == "text.hash_embedding_v1"
        assert inputs == ["alpha beta", "gamma"]
        assert dimensions == 8
        return _embedding_generation_model_descriptor(), [
            SimpleNamespace(
                index=0,
                embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                token_count=2,
                provider=None,
            ),
            SimpleNamespace(
                index=1,
                embedding=[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                token_count=1,
                provider=None,
            ),
        ], 3

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_text_embeddings", _fake_create_embeddings)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/embeddings",
                json={
                    "model": "text.hash_embedding_v1",
                    "input": ["alpha beta", "gamma"],
                    "dimensions": 8,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "model": "text.hash_embedding_v1",
        "dimensions": 8,
        "provider_backend": None,
        "provider_model_id": None,
        "provider_attempts": [],
        "data": [
            {
                "object": "embedding",
                "index": 0,
                "embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "token_count": 2,
            },
            {
                "object": "embedding",
                "index": 1,
                "embedding": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "token_count": 1,
            },
        ],
        "usage": {
            "prompt_tokens": 3,
            "total_tokens": 3,
        },
    }


def test_chat_completions_route_returns_deterministic_assistant_message(monkeypatch) -> None:
    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        assert model_id == "text.tokenizer"
        assert messages == [
            {"role": "system", "content": "Keep output deterministic"},
            {"role": "user", "content": "alpha beta"},
        ]
        return _tokenizer_model_descriptor(), SimpleNamespace(
            completion_id="chatcmpl_test_123",
            content='{"model":"text.tokenizer","token_count":2,"tokens":["alpha","beta"]}',
            prompt_tokens=5,
            completion_tokens=9,
            provider=None,
            provider_attempts=[],
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat_completion)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "text.tokenizer",
                    "messages": [
                        {"role": "system", "content": "Keep output deterministic"},
                        {"role": "user", "content": "alpha beta"},
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "chatcmpl_test_123",
        "object": "chat.completion",
        "model": "text.tokenizer",
        "provider_backend": None,
        "provider_model_id": None,
        "provider_attempts": [],
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": '{"model":"text.tokenizer","token_count":2,"tokens":["alpha","beta"]}',
                },
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 9,
            "total_tokens": 14,
        },
    }


def test_chat_completions_route_surfaces_provider_execution_metadata(monkeypatch) -> None:
    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        assert model_id == "provider.gpt-4o-mini"
        assert messages == [{"role": "user", "content": "Summarize"}]
        return _provider_chat_model_descriptor(), SimpleNamespace(
            completion_id="chatcmpl_provider_123",
            content="Provider response.",
            prompt_tokens=3,
            completion_tokens=2,
            provider=SimpleNamespace(
                provider_backend="openai_compatible",
                provider_model_id="provider.gpt-4o-mini",
            ),
            provider_attempts=[
                SimpleNamespace(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                    outcome="selected",
                    error_code=None,
                )
            ],
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat_completion)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "provider.gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Summarize"}],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["provider_backend"] == "openai_compatible"
    assert response.json()["provider_model_id"] == "provider.gpt-4o-mini"
    assert response.json()["provider_attempts"] == [
        {
            "provider_backend": "openai_compatible",
            "provider_model_id": "provider.gpt-4o-mini",
            "outcome": "selected",
            "error_code": None,
        }
    ]


def test_chat_completions_route_streams_sse_chunks(monkeypatch) -> None:
    async def _fake_chat_completion(*, model_id: str, messages: list[dict[str, str]]):
        assert model_id == "text.tokenizer"
        assert messages == [{"role": "user", "content": "alpha beta"}]
        return _tokenizer_model_descriptor(), SimpleNamespace(
            completion_id="chatcmpl_stream_123",
            content="deterministic utility response",
            prompt_tokens=2,
            completion_tokens=3,
            provider=None,
            provider_attempts=[],
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_chat_completion", _fake_chat_completion)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "text.tokenizer",
                    "messages": [{"role": "user", "content": "alpha beta"}],
                    "stream": True,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"object":"chat.completion.chunk"' in response.text
    assert '"provider_backend":null' in response.text
    assert '"provider_model_id":null' in response.text
    assert '"provider_attempts":[]' in response.text
    assert '"role":"assistant"' in response.text
    assert '"content":"deterministic utility' in response.text
    assert "data: [DONE]" in response.text


def test_embeddings_route_surfaces_provider_execution_metadata(monkeypatch) -> None:
    async def _fake_create_embeddings(
        *,
        model_id: str,
        inputs: list[str],
        dimensions: int,
    ):
        assert model_id == "provider.gpt-4o-mini"
        assert inputs == ["alpha beta"]
        assert dimensions == 3
        return _provider_chat_model_descriptor(), [
            SimpleNamespace(
                index=0,
                embedding=[0.1, 0.2, 0.3],
                token_count=3,
                provider=SimpleNamespace(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                ),
                provider_attempts=[
                    SimpleNamespace(
                        provider_backend="openai_compatible",
                        provider_model_id="provider.gpt-4o-mini",
                        outcome="selected",
                        error_code=None,
                    )
                ],
            )
        ], 3

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_text_embeddings", _fake_create_embeddings)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/embeddings",
                json={
                    "model": "provider.gpt-4o-mini",
                    "input": "alpha beta",
                    "dimensions": 3,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["provider_backend"] == "openai_compatible"
    assert response.json()["provider_model_id"] == "provider.gpt-4o-mini"
    assert response.json()["provider_attempts"] == [
        {
            "provider_backend": "openai_compatible",
            "provider_model_id": "provider.gpt-4o-mini",
            "outcome": "selected",
            "error_code": None,
        }
    ]


def test_responses_route_returns_tokenization_envelope(monkeypatch) -> None:
    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "text.tokenizer"
        assert inputs == ["alpha beta"]
        assert dimensions == 64
        return _tokenizer_model_descriptor(), "resp_test_tokenizer", [
            SimpleNamespace(
                index=0,
                item_type="tokenization",
                text="alpha beta",
                tokens=["alpha", "beta"],
                token_count=2,
                embedding=None,
                provider=None,
            )
        ], 2

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "text.tokenizer", "input": "alpha beta"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "resp_test_tokenizer",
        "object": "response",
        "status": "completed",
        "model": "text.tokenizer",
        "provider_backend": None,
        "provider_model_id": None,
        "provider_attempts": [],
        "output": [
            {
                "id": "resp_test_tokenizer_item_0",
                "object": "response.output",
                "index": 0,
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
                "content": [
                    {
                        "type": "tokenization",
                        "text": "alpha beta",
                        "tokens": ["alpha", "beta"],
                        "token_count": 2,
                        "embedding": None,
                    }
                ],
            }
        ],
        "usage": {"prompt_tokens": 2, "total_tokens": 2},
    }


def test_responses_route_streams_sse_output_events(monkeypatch) -> None:
    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "text.tokenizer"
        assert inputs == ["alpha beta"]
        assert dimensions == 64
        return _tokenizer_model_descriptor(), "resp_stream_123", [
            SimpleNamespace(
                index=0,
                item_type="tokenization",
                text="alpha beta",
                tokens=["alpha", "beta"],
                token_count=2,
                embedding=None,
                provider=None,
            )
        ], 2

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "text.tokenizer", "input": "alpha beta", "stream": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"type":"response.created"' in response.text
    assert '"provider_backend":null' in response.text
    assert '"provider_model_id":null' in response.text
    assert '"provider_attempts":[]' in response.text
    assert '"type":"response.output_item.done"' in response.text
    assert '"type":"response.completed"' in response.text
    assert "data: [DONE]" in response.text


def test_responses_route_returns_provider_text_envelope(monkeypatch) -> None:
    async def _fake_create_response(*, model_id: str, inputs: list[str], dimensions: int):
        assert model_id == "provider.gpt-4o-mini"
        assert inputs == ["alpha beta"]
        assert dimensions == 64
        return _provider_chat_model_descriptor(), "resp_provider_text", [
            SimpleNamespace(
                index=0,
                item_type="text",
                text="Provider response.",
                tokens=None,
                token_count=3,
                embedding=None,
                provider=SimpleNamespace(
                    provider_backend="openai_compatible",
                    provider_model_id="provider.gpt-4o-mini",
                ),
                provider_attempts=[
                    SimpleNamespace(
                        provider_backend="openai_compatible",
                        provider_model_id="provider.gpt-4o-mini",
                        outcome="selected",
                        error_code=None,
                    )
                ],
            )
        ], 5

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "create_utility_response", _fake_create_response)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/responses",
                json={"model": "provider.gpt-4o-mini", "input": "alpha beta"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "resp_provider_text",
        "object": "response",
        "status": "completed",
        "model": "provider.gpt-4o-mini",
        "provider_backend": "openai_compatible",
        "provider_model_id": "provider.gpt-4o-mini",
        "provider_attempts": [
            {
                "provider_backend": "openai_compatible",
                "provider_model_id": "provider.gpt-4o-mini",
                "outcome": "selected",
                "error_code": None,
            }
        ],
        "output": [
            {
                "id": "resp_provider_text_item_0",
                "object": "response.output",
                "index": 0,
                "provider_backend": "openai_compatible",
                "provider_model_id": "provider.gpt-4o-mini",
                "provider_attempts": [
                    {
                        "provider_backend": "openai_compatible",
                        "provider_model_id": "provider.gpt-4o-mini",
                        "outcome": "selected",
                        "error_code": None,
                    }
                ],
                "content": [
                    {
                        "type": "text",
                        "text": "Provider response.",
                        "tokens": None,
                        "token_count": 3,
                        "embedding": None,
                    }
                ],
            }
        ],
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }


def test_embedding_similarity_route_returns_metric_score(monkeypatch) -> None:
    async def _fake_similarity(
        *,
        model_id: str,
        left: list[float],
        right: list[float],
    ) -> tuple[LLMModelDescriptor, float]:
        assert model_id == "embeddings.cosine_similarity"
        assert left == [1.0, 0.0]
        assert right == [0.5, 0.5]
        return _embedding_similarity_model_descriptor(), 0.70710678

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "embedding_similarity_score", _fake_similarity)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/embeddings/similarity",
                json={
                    "model": "embeddings.cosine_similarity",
                    "left": [1.0, 0.0],
                    "right": [0.5, 0.5],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "object": "embedding_similarity",
        "model": "embeddings.cosine_similarity",
        "similarity_metric": "cosine",
        "score": 0.70710678,
        "dimension": 2,
    }


def test_embedding_similarity_route_rejects_mismatched_dimensions(monkeypatch) -> None:
    async def _fake_similarity(
        *,
        model_id: str,
        left: list[float],
        right: list[float],
    ) -> tuple[LLMModelDescriptor, float]:
        del left, right
        raise LLMAPIError(
            "invalid_embedding_dimensions",
            "Embedding vectors must have identical dimensions.",
            {
                "model": model_id,
                "left_dimension": 3,
                "right_dimension": 2,
            },
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "embedding_similarity_score", _fake_similarity)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/embeddings/similarity",
                json={
                    "model": "embeddings.cosine_similarity",
                    "left": [1.0, 0.0, 0.0],
                    "right": [1.0, 0.0],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_embedding_dimensions"
    assert error["message"] == "Embedding vectors must have identical dimensions."
    assert error["details"] == {
        "model": "embeddings.cosine_similarity",
        "left_dimension": 3,
        "right_dimension": 2,
    }
    assert isinstance(error["request_id"], str)


def test_rerank_route_returns_ranked_documents(monkeypatch) -> None:
    async def _fake_rerank(
        *,
        model_id: str,
        query_embedding: list[float],
        documents: list[dict[str, object]],
        top_n: int | None,
    ):
        assert model_id == "embeddings.cosine_similarity"
        assert query_embedding == [1.0, 0.0]
        assert documents == [
            {
                "id": "doc_a",
                "embedding": [0.9, 0.1],
                "text": "alpha",
                "metadata": {"group": "A"},
            },
            {
                "id": "doc_b",
                "embedding": [0.5, 0.5],
                "text": "beta",
                "metadata": None,
            },
        ]
        assert top_n == 1
        return _embedding_similarity_model_descriptor(), [
            SimpleNamespace(
                document_id="doc_a",
                index=0,
                rank=1,
                score=0.9,
                text="alpha",
                metadata={"group": "A"},
            )
        ]

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "rerank_embeddings", _fake_rerank)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/rerank",
                json={
                    "model": "embeddings.cosine_similarity",
                    "query_embedding": [1.0, 0.0],
                    "documents": [
                        {
                            "id": "doc_a",
                            "embedding": [0.9, 0.1],
                            "text": "alpha",
                            "metadata": {"group": "A"},
                        },
                        {
                            "id": "doc_b",
                            "embedding": [0.5, 0.5],
                            "text": "beta",
                        },
                    ],
                    "top_n": 1,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "model": "embeddings.cosine_similarity",
        "similarity_metric": "cosine",
        "total_documents": 2,
        "returned_documents": 1,
        "data": [
            {
                "object": "rerank_result",
                "id": "doc_a",
                "index": 0,
                "rank": 1,
                "score": 0.9,
                "text": "alpha",
                "metadata": {"group": "A"},
            }
        ],
    }


def test_rerank_route_rejects_mismatched_dimensions(monkeypatch) -> None:
    async def _fake_rerank(
        *,
        model_id: str,
        query_embedding: list[float],
        documents: list[dict[str, object]],
        top_n: int | None,
    ):
        del query_embedding, documents, top_n
        raise LLMAPIError(
            "invalid_embedding_dimensions",
            "Embedding vectors must have identical dimensions.",
            {
                "model": model_id,
                "left_dimension": 3,
                "right_dimension": 2,
            },
        )

    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(llm_router, "rerank_embeddings", _fake_rerank)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/rerank",
                json={
                    "model": "embeddings.cosine_similarity",
                    "query_embedding": [1.0, 0.0, 0.0],
                    "documents": [
                        {"id": "doc_a", "embedding": [1.0, 0.0]},
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_embedding_dimensions"
    assert error["message"] == "Embedding vectors must have identical dimensions."
    assert error["details"] == {
        "model": "embeddings.cosine_similarity",
        "left_dimension": 3,
        "right_dimension": 2,
    }
    assert isinstance(error["request_id"], str)
