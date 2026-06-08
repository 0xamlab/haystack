from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from .client_model_surface_common import _request_model
from .client_stream_surface_common import _stream_model

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def list_models(client: DecisionEngineClient) -> Any:
    return _request_model(client, "GET", "/v1/models", "LLMModelListResult")


def tokenize(
    client: DecisionEngineClient,
    text: str,
    *,
    model: str = "text.tokenizer",
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/tokenize",
        "TokenizeResult",
        json_body={"model": model, "input": text},
    )


def count_tokens(
    client: DecisionEngineClient,
    text: str,
    *,
    model: str = "text.tokenizer",
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/count_tokens",
        "CountTokensResult",
        json_body={"model": model, "input": text},
    )


def resolve_artifact_bridge(
    client: DecisionEngineClient,
    *,
    repo_id: str,
    filename: str,
    revision: str | None = None,
    local_files_only: bool = True,
) -> Any:
    payload: dict[str, Any] = {
        "repo_id": repo_id,
        "filename": filename,
        "local_files_only": local_files_only,
    }
    if revision is not None:
        payload["revision"] = revision
    return _request_model(
        client,
        "POST",
        "/v1/artifacts/resolve",
        "ArtifactBridgeResolveResult",
        json_body=payload,
    )


def chat_completions(
    client: DecisionEngineClient,
    messages: list[dict[str, str]],
    *,
    model: str = "text.tokenizer",
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/chat/completions",
        "ChatCompletionsResult",
        json_body={"model": model, "messages": messages},
    )


def stream_chat_completions(
    client: DecisionEngineClient,
    messages: list[dict[str, str]],
    *,
    model: str = "text.tokenizer",
) -> Iterator[Any]:
    return _stream_model(
        client,
        "POST",
        "/v1/chat/completions",
        "ChatCompletionsStreamChunkResult",
        json_body={"model": model, "messages": messages, "stream": True},
    )


def responses(
    client: DecisionEngineClient,
    input_value: str | list[str],
    *,
    model: str = "text.tokenizer",
    dimensions: int = 64,
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/responses",
        "ResponsesResult",
        json_body={"model": model, "input": input_value, "dimensions": dimensions},
    )


def stream_responses(
    client: DecisionEngineClient,
    input_value: str | list[str],
    *,
    model: str = "text.tokenizer",
    dimensions: int = 64,
) -> Iterator[Any]:
    return _stream_model(
        client,
        "POST",
        "/v1/responses",
        "ResponseStreamEventResult",
        json_body={
            "model": model,
            "input": input_value,
            "dimensions": dimensions,
            "stream": True,
        },
    )


def embeddings(
    client: DecisionEngineClient,
    input_value: str | list[str],
    *,
    model: str = "text.hash_embedding_v1",
    dimensions: int = 64,
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/embeddings",
        "EmbeddingsResult",
        json_body={"model": model, "input": input_value, "dimensions": dimensions},
    )


def embedding_similarity(
    client: DecisionEngineClient,
    left: list[float],
    right: list[float],
    *,
    model: str = "embeddings.cosine_similarity",
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/embeddings/similarity",
        "EmbeddingSimilarityResult",
        json_body={"model": model, "left": left, "right": right},
    )


def rerank(
    client: DecisionEngineClient,
    query_embedding: list[float],
    documents: list[dict[str, Any]],
    *,
    model: str = "embeddings.cosine_similarity",
    top_n: int | None = None,
) -> Any:
    payload: dict[str, Any] = {
        "model": model,
        "query_embedding": query_embedding,
        "documents": documents,
    }
    if top_n is not None:
        payload["top_n"] = top_n
    return _request_model(
        client,
        "POST",
        "/v1/rerank",
        "RerankResponseResult",
        json_body=payload,
    )


__all__ = [
    "chat_completions",
    "count_tokens",
    "resolve_artifact_bridge",
    "embedding_similarity",
    "embeddings",
    "list_models",
    "rerank",
    "responses",
    "stream_chat_completions",
    "stream_responses",
    "tokenize",
]
