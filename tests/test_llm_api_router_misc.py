"""Tests for test_llm_api_router: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-4/tests/test_llm_api_router.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_router_helpers import *  # noqa: F401,F403


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
            f"Model '{model_id}' is not available on the current Codna LLM API surface.",
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
        == "Model 'does.not.exist' is not available on the current Codna LLM API surface."
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


