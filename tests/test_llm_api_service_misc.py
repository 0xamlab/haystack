"""Tests for test_llm_api_service: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


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


