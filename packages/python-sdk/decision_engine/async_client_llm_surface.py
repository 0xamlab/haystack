from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from .async_client_model_surface_common import _request_model
from .async_client_stream_surface_common import _stream_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def list_models(client: AsyncDecisionEngineClient) -> Any:
    return await _request_model(client, "GET", "/v1/models", "LLMModelListResult")


async def tokenize(
    client: AsyncDecisionEngineClient,
    text: str,
    *,
    model: str = "text.tokenizer",
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/tokenize",
        "TokenizeResult",
        json_body={"model": model, "input": text},
    )


async def count_tokens(
    client: AsyncDecisionEngineClient,
    text: str,
    *,
    model: str = "text.tokenizer",
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/count_tokens",
        "CountTokensResult",
        json_body={"model": model, "input": text},
    )


async def resolve_artifact_bridge(
    client: AsyncDecisionEngineClient,
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
    return await _request_model(
        client,
        "POST",
        "/v1/artifacts/resolve",
        "ArtifactBridgeResolveResult",
        json_body=payload,
    )


def _chat_completions_tool_kwargs(
    *,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any] | None,
    parallel_tool_calls: bool | None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if tools is not None:
        extra["tools"] = tools
    if tool_choice is not None:
        extra["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        extra["parallel_tool_calls"] = parallel_tool_calls
    return extra


async def chat_completions(
    client: AsyncDecisionEngineClient,
    messages: list[dict[str, Any]],
    *,
    model: str = "text.tokenizer",
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    parallel_tool_calls: bool | None = None,
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/chat/completions",
        "ChatCompletionsResult",
        json_body={
            "model": model,
            "messages": messages,
            **_chat_completions_tool_kwargs(
                tools=tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls
            ),
        },
    )


def stream_chat_completions(
    client: AsyncDecisionEngineClient,
    messages: list[dict[str, Any]],
    *,
    model: str = "text.tokenizer",
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    parallel_tool_calls: bool | None = None,
) -> AsyncIterator[Any]:
    return _stream_model(
        client,
        "POST",
        "/v1/chat/completions",
        "ChatCompletionsStreamChunkResult",
        json_body={
            "model": model,
            "messages": messages,
            "stream": True,
            **_chat_completions_tool_kwargs(
                tools=tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls
            ),
        },
    )


async def responses(
    client: AsyncDecisionEngineClient,
    input_value: str | list[str],
    *,
    model: str = "text.tokenizer",
    dimensions: int = 64,
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/responses",
        "ResponsesResult",
        json_body={"model": model, "input": input_value, "dimensions": dimensions},
    )


def stream_responses(
    client: AsyncDecisionEngineClient,
    input_value: str | list[str],
    *,
    model: str = "text.tokenizer",
    dimensions: int = 64,
) -> AsyncIterator[Any]:
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


async def embeddings(
    client: AsyncDecisionEngineClient,
    input_value: str | list[str],
    *,
    model: str = "text.hash_embedding_v1",
    dimensions: int = 64,
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/embeddings",
        "EmbeddingsResult",
        json_body={"model": model, "input": input_value, "dimensions": dimensions},
    )


async def embedding_similarity(
    client: AsyncDecisionEngineClient,
    left: list[float],
    right: list[float],
    *,
    model: str = "embeddings.cosine_similarity",
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/embeddings/similarity",
        "EmbeddingSimilarityResult",
        json_body={"model": model, "left": left, "right": right},
    )


async def rerank(
    client: AsyncDecisionEngineClient,
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
    return await _request_model(
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
