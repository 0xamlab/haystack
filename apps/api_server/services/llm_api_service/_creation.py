"""Artifact bridge + tokenization + async create_* (embeddings/chat/response/rerank).

Extracted from apps/api_server/services/llm_api_service.py during modularization.
"""
from __future__ import annotations

import importlib
import importlib.util
import hashlib
import math
import json
import os
from functools import lru_cache
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from apps.api_server.services import llm_provider_service
from apps.api_server.services.runtime_library_service import (
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime.mojo_library_runner import MojoLibraryError



from apps.api_server.services.llm_api_service._definitions import *  # noqa: F401, F403
from apps.api_server.services.llm_api_service._definitions import (
    _detect_bridge_backends,
    _resolve_artifact_bridge_cache_root,
    _resolve_artifact_bridge_auth_env_vars,
    _artifact_bridge_auth_configured,
    _artifact_bridge_auth_token,
    _artifact_bridge_backend_for_filename,
    _hf_hub_download,
    _require_model_capability,
    _validate_embedding_dimensions,
    _rerank_sort_order,
    _runtime_module_descriptors,
    _ARTIFACT_BRIDGE_SPECS,
    _HASH_EMBEDDING_PERSON,
    _HUGGINGFACE_LOCAL_MISS_EXCEPTIONS,
    _TEXT_TOKENIZER_MODEL_ID,
    _TEXT_TOKENIZER_TOKENIZE_FUNCTION,
)


def resolve_artifact_bridge(
    *,
    repo_id: str,
    filename: str,
    revision: str | None = None,
    local_files_only: bool = True,
) -> ArtifactBridgeResolution:
    # Test code monkey-patches llm_api_service._detect_bridge_backends and
    # llm_api_service._hf_hub_download at the facade level — look up via
    # the facade so the patches propagate into this submodule call site.
    from apps.api_server.services import llm_api_service as _facade
    artifact_backends = _facade._detect_bridge_backends(_ARTIFACT_BRIDGE_SPECS)
    if "huggingface_hub" not in artifact_backends:
        raise LLMAPIError(
            "artifact_bridge_backend_unavailable",
            "The Hugging Face artifact bridge backend is not available in the current checkout.",
            {"required_backend": "huggingface_hub"},
        )

    cache_root = _resolve_artifact_bridge_cache_root(artifact_backends)
    auth_env_vars = _resolve_artifact_bridge_auth_env_vars(artifact_backends)
    auth_env_var_used, auth_token = _artifact_bridge_auth_token(auth_env_vars)
    auth_configured = auth_token is not None

    try:
        resolved_path = _facade._hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            cache_root=cache_root,
            local_files_only=local_files_only,
            auth_token=auth_token,
        )
    except Exception as exc:
        if local_files_only and exc.__class__.__name__ in _HUGGINGFACE_LOCAL_MISS_EXCEPTIONS:
            return ArtifactBridgeResolution(
                backend="huggingface_hub",
                artifact_backend=_artifact_bridge_backend_for_filename(filename, artifact_backends),
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                local_files_only=local_files_only,
                status="not_cached",
                cache_root=cache_root,
                auth_env_vars=auth_env_vars,
                auth_configured=auth_configured,
                auth_env_var_used=auth_env_var_used,
                resolved_path=None,
            )
        if exc.__class__.__name__ in _HUGGINGFACE_LOCAL_MISS_EXCEPTIONS:
            raise LLMAPIError(
                "artifact_not_found",
                "The requested Hugging Face artifact could not be resolved.",
                {
                    "backend": "huggingface_hub",
                    "repo_id": repo_id,
                    "filename": filename,
                    "revision": revision,
                },
            ) from exc
        raise LLMAPIError(
            "artifact_bridge_download_failed",
            "The Hugging Face artifact bridge failed to resolve the requested artifact.",
            {
                "backend": "huggingface_hub",
                "repo_id": repo_id,
                "filename": filename,
                "revision": revision,
                "local_files_only": local_files_only,
                "cause": str(exc),
            },
        ) from exc

    return ArtifactBridgeResolution(
        backend="huggingface_hub",
        artifact_backend=_artifact_bridge_backend_for_filename(filename, artifact_backends),
        repo_id=repo_id,
        filename=filename,
        revision=revision,
        local_files_only=local_files_only,
        status="resolved",
        cache_root=cache_root,
        auth_env_vars=auth_env_vars,
        auth_configured=auth_configured,
        auth_env_var_used=auth_env_var_used,
        resolved_path=resolved_path,
    )


async def _execute_word_tokenize(*, consumer_model_id: str, text: str) -> list[str]:
    from apps.api_server.services import llm_api_service as _facade
    execution = await _facade.execute_public_runtime_library(
        module=_TEXT_TOKENIZER_MODEL_ID,
        function=_TEXT_TOKENIZER_TOKENIZE_FUNCTION,
        args=text,
    )
    tokens = execution.result
    if not isinstance(tokens, list) or any(not isinstance(item, str) for item in tokens):
        raise LLMAPIError(
            "invalid_runtime_response",
            (
                f"Runtime library returned an invalid tokenization payload for model "
                f"'{consumer_model_id}'."
            ),
            {"model": consumer_model_id, "runtime_module": _TEXT_TOKENIZER_MODEL_ID},
        )
    return tokens


def _stable_hash_embedding(*, tokens: list[str], dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokens:
        normalized = token.strip().lower()
        if not normalized:
            continue
        digest = hashlib.blake2b(
            normalized.encode("utf-8"),
            digest_size=16,
            person=_HASH_EMBEDDING_PERSON,
        ).digest()
        bucket = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] % 2 == 0 else -1.0
        vector[bucket] += sign
    squared_norm = sum(value * value for value in vector)
    if squared_norm == 0.0:
        return vector
    norm = math.sqrt(squared_norm)
    return [value / norm for value in vector]


def _deterministic_response_id(
    *,
    model_id: str,
    inputs: list[str],
    dimensions: int | None,
) -> str:
    payload = {"model": model_id, "input": inputs, "dimensions": dimensions}
    digest = hashlib.blake2b(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
        digest_size=12,
        person=b"algenta_resp",
    ).hexdigest()
    return f"resp_{digest}"


def _response_id_from_chat_completion_ids(*, model_id: str, completion_ids: list[str]) -> str:
    digest = hashlib.blake2b(
        json.dumps(
            {"model": model_id, "completion_ids": completion_ids},
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8"),
        digest_size=12,
        person=b"algenta_resp",
    ).hexdigest()
    return f"resp_{digest}"


def _unique_provider_metadata(
    items: list[ProviderExecutionMetadata | None],
) -> ProviderExecutionMetadata | None:
    provider_items = [item for item in items if item is not None]
    if not provider_items:
        return None
    first = provider_items[0]
    if all(item == first for item in provider_items[1:]):
        return first
    return None


def _deterministic_chat_completion_id(*, model_id: str, messages: list[dict[str, str]]) -> str:
    digest = hashlib.blake2b(
        json.dumps({"model": model_id, "messages": messages}, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        ),
        digest_size=12,
        person=b"algenta_chat",
    ).hexdigest()
    return f"chatcmpl_{digest}"


async def tokenize_text(*, model_id: str, text: str) -> tuple[LLMModelDescriptor, list[str]]:
    from apps.api_server.services import llm_api_service as _facade
    descriptor = _facade.get_llm_model_descriptor(model_id)
    _require_model_capability(
        descriptor,
        capability="tokenize",
        operation="tokenization",
    )
    return descriptor, await _execute_word_tokenize(consumer_model_id=model_id, text=text)


async def count_text_tokens(*, model_id: str, text: str) -> tuple[LLMModelDescriptor, int]:
    descriptor, tokens = await tokenize_text(model_id=model_id, text=text)
    return descriptor, len(tokens)


async def embedding_similarity_score(
    *,
    model_id: str,
    left: list[float],
    right: list[float],
) -> tuple[LLMModelDescriptor, float]:
    from apps.api_server.services import llm_api_service as _facade
    descriptor = _facade.get_llm_model_descriptor(model_id)
    _require_model_capability(
        descriptor,
        capability="embedding_similarity",
        operation="embedding similarity scoring",
    )
    _validate_embedding_dimensions(
        model_id=model_id,
        left_dimension=len(left),
        right_dimension=len(right),
    )

    function_name = descriptor.runtime_functions[0]
    from apps.api_server.services import llm_api_service as _facade
    execution = await _facade.execute_public_runtime_library(
        module=descriptor.runtime_module,
        function=function_name,
        args=[left, right],
    )
    score = execution.result
    if not isinstance(score, (int, float)):
        raise LLMAPIError(
            "invalid_runtime_response",
            (
                f"Runtime library returned an invalid similarity payload for model "
                f"'{model_id}'."
            ),
            {"model": model_id, "runtime_module": descriptor.runtime_module},
        )
    return descriptor, float(score)


async def rerank_embeddings(
    *,
    model_id: str,
    query_embedding: list[float],
    documents: list[dict[str, object]],
    top_n: int | None,
) -> tuple[LLMModelDescriptor, list[RerankDocumentResult]]:
    from apps.api_server.services import llm_api_service as _facade
    descriptor = _facade.get_llm_model_descriptor(model_id)
    _require_model_capability(
        descriptor,
        capability="rerank",
        operation="reranking",
    )

    query_dimension = len(query_embedding)
    function_name = descriptor.runtime_functions[0]
    scored_documents: list[RerankDocumentResult] = []

    for index, document in enumerate(documents):
        raw_embedding = document["embedding"]
        if not isinstance(raw_embedding, list):
            raise LLMAPIError(
                "invalid_embedding_dimensions",
                "Embedding vectors must have identical dimensions.",
                {
                    "model": model_id,
                    "left_dimension": query_dimension,
                    "right_dimension": 0,
                },
            )
        embedding = [float(value) for value in raw_embedding]
        _validate_embedding_dimensions(
            model_id=model_id,
            left_dimension=query_dimension,
            right_dimension=len(embedding),
        )
        from apps.api_server.services import llm_api_service as _facade
        execution = await _facade.execute_public_runtime_library(
            module=descriptor.runtime_module,
            function=function_name,
            args=[query_embedding, embedding],
        )
        score = execution.result
        if not isinstance(score, (int, float)):
            raise LLMAPIError(
                "invalid_runtime_response",
                (
                    f"Runtime library returned an invalid rerank payload for model "
                    f"'{model_id}'."
                ),
                {"model": model_id, "runtime_module": descriptor.runtime_module},
            )
        metadata = document.get("metadata")
        scored_documents.append(
            RerankDocumentResult(
                document_id=str(document["id"]),
                index=index,
                rank=0,
                score=float(score),
                text=document.get("text") if isinstance(document.get("text"), str) else None,
                metadata=metadata if isinstance(metadata, dict) else None,
            )
        )

    reverse = _rerank_sort_order(descriptor.similarity_metric) == "descending"
    ordered_documents = sorted(
        scored_documents,
        key=lambda item: (item.score, -item.index) if reverse else (item.score, item.index),
        reverse=reverse,
    )
    if top_n is not None:
        ordered_documents = ordered_documents[:top_n]

    reranked = [
        RerankDocumentResult(
            document_id=item.document_id,
            index=item.index,
            rank=rank,
            score=item.score,
            text=item.text,
            metadata=item.metadata,
        )
        for rank, item in enumerate(ordered_documents, start=1)
    ]
    return descriptor, reranked


async def create_text_embeddings(
    *,
    model_id: str,
    inputs: list[str],
    dimensions: int,
) -> tuple[LLMModelDescriptor, list[GeneratedEmbedding], int]:
    from apps.api_server.services import llm_api_service as _facade
    descriptor = _facade.get_llm_model_descriptor(model_id)
    _require_model_capability(
        descriptor,
        capability="embeddings",
        operation="embedding generation",
    )
    provider_config = llm_provider_service.get_configured_provider_model(model_id)
    if provider_config is not None:
        generated, total_tokens = await llm_provider_service.routed_provider_embeddings(
            model_id=model_id,
            inputs=inputs,
            dimensions=dimensions,
        )
        return descriptor, generated, total_tokens

    generated: list[GeneratedEmbedding] = []
    total_tokens = 0
    for index, text in enumerate(inputs):
        tokens = await _execute_word_tokenize(consumer_model_id=model_id, text=text)
        token_count = len(tokens)
        total_tokens += token_count
        generated.append(
            GeneratedEmbedding(
                index=index,
                embedding=_stable_hash_embedding(tokens=tokens, dimensions=dimensions),
                token_count=token_count,
            )
        )
    return descriptor, generated, total_tokens


async def create_utility_response(
    *,
    model_id: str,
    inputs: list[str],
    dimensions: int,
) -> tuple[LLMModelDescriptor, str, list[UtilityResponseOutputItem], int]:
    from apps.api_server.services import llm_api_service as _facade
    descriptor = _facade.get_llm_model_descriptor(model_id)
    outputs: list[UtilityResponseOutputItem] = []
    total_tokens = 0
    provider_config = llm_provider_service.get_configured_provider_model(model_id)
    from apps.api_server.services import llm_api_service as _facade

    if provider_config is not None and "chat_completions" in descriptor.capabilities:
        completion_ids: list[str] = []
        for index, text in enumerate(inputs):
            _, completion = await _facade.create_chat_completion(
                model_id=model_id,
                messages=[{"role": "user", "content": text}],
            )
            completion_ids.append(completion.completion_id)
            total_tokens += completion.prompt_tokens + completion.completion_tokens
            outputs.append(
                UtilityResponseOutputItem(
                    index=index,
                    item_type="text",
                    text=completion.content,
                    tokens=None,
                    token_count=completion.completion_tokens,
                    embedding=None,
                    provider=completion.provider,
                    provider_attempts=completion.provider_attempts,
                )
            )
        return (
            descriptor,
            _response_id_from_chat_completion_ids(
                model_id=model_id,
                completion_ids=completion_ids,
            ),
            outputs,
            total_tokens,
        )

    if "tokenize" in descriptor.capabilities:
        for index, text in enumerate(inputs):
            tokens = await _execute_word_tokenize(consumer_model_id=model_id, text=text)
            token_count = len(tokens)
            total_tokens += token_count
            outputs.append(
                UtilityResponseOutputItem(
                    index=index,
                    item_type="tokenization",
                    text=text,
                    tokens=tokens,
                    token_count=token_count,
                    embedding=None,
                )
            )
        return (
            descriptor,
            _deterministic_response_id(model_id=model_id, inputs=inputs, dimensions=None),
            outputs,
            total_tokens,
        )

    if "embeddings" in descriptor.capabilities:
        embedding_descriptor, generated, total_tokens = await _facade.create_text_embeddings(
            model_id=model_id,
            inputs=inputs,
            dimensions=dimensions,
        )
        for generated_item, text in zip(generated, inputs, strict=True):
            outputs.append(
                UtilityResponseOutputItem(
                    index=generated_item.index,
                    item_type="embedding",
                    text=text,
                    tokens=None,
                    token_count=generated_item.token_count,
                    embedding=generated_item.embedding,
                    provider=generated_item.provider,
                    provider_attempts=generated_item.provider_attempts,
                )
            )
        return (
            embedding_descriptor,
            _deterministic_response_id(model_id=model_id, inputs=inputs, dimensions=dimensions),
            outputs,
            total_tokens,
        )

    raise LLMAPIError(
        "model_capability_unsupported",
        f"Model '{model_id}' does not support responses.",
        {"model": model_id, "required_capability": "tokenize_or_embeddings"},
    )


async def create_chat_completion(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    seed: int | None = None,
    tools: list[dict[str, object]] | None = None,
    tool_choice: object | None = None,
    parallel_tool_calls: bool | None = None,
) -> tuple[LLMModelDescriptor, ChatCompletionResult]:
    from apps.api_server.services import llm_api_service as _facade
    descriptor = _facade.get_llm_model_descriptor(model_id)
    _require_model_capability(
        descriptor,
        capability="chat_completions",
        operation="chat completions",
    )
    provider_config = llm_provider_service.get_configured_provider_model(model_id)
    if provider_config is not None and provider_config.backend == "algenta_local":
        # Parity gap 2 (2026-08-10): the local Apple-Silicon GPU engine. Not an HTTP provider --
        # executed directly through algenta.inference.decode(); sampling parameters apply to this
        # backend (remote providers keep their server-side defaults until their payload builders
        # grow parameter pass-through). Tool calling on the local engine is a separate track (C3) --
        # refuse honestly rather than silently answering without ever looking at the tools.
        if tools:
            raise LLMAPIError(
                "model_capability_unsupported",
                f"Model '{model_id}' (backend 'algenta_local') does not support tool calling.",
                {"model": model_id, "backend": "algenta_local", "required_capability": "tool_calling"},
            )
        return descriptor, await llm_provider_service.execute_local_chat_completion(
            config=provider_config,
            messages=messages,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
        )
    if provider_config is not None:
        # Forward the output budget/tool-calling params only when set, so callers/stubs that
        # don't expect the kwarg are unaffected (None/absent == unchanged prior behavior).
        _output_budget = (
            {} if max_output_tokens is None else {"max_output_tokens": max_output_tokens}
        )
        _tool_kwargs: dict[str, object] = {}
        if tools:
            _tool_kwargs["tools"] = tools
        if tool_choice is not None:
            _tool_kwargs["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            _tool_kwargs["parallel_tool_calls"] = parallel_tool_calls
        return descriptor, await llm_provider_service.routed_provider_chat_completion(
            model_id=model_id,
            messages=messages,
            **_output_budget,
            **_tool_kwargs,
        )

    if tools:
        raise LLMAPIError(
            "model_capability_unsupported",
            f"Model '{model_id}' does not support tool calling.",
            {"model": model_id, "required_capability": "tool_calling"},
        )
    serialized_messages: list[dict[str, str]] = []
    prompt_tokens = 0
    for message in messages:
        content = message["content"]
        tokens = await _execute_word_tokenize(consumer_model_id=model_id, text=content)
        prompt_tokens += len(tokens)
        serialized_messages.append({"role": message["role"], "content": content})

    user_messages = [item["content"] for item in serialized_messages if item["role"] == "user"]
    transcript = "\n".join(user_messages or [serialized_messages[-1]["content"]])
    transcript_tokens = await _execute_word_tokenize(consumer_model_id=model_id, text=transcript)
    assistant_payload = {
        "model": model_id,
        "token_count": len(transcript_tokens),
        "tokens": transcript_tokens,
    }
    assistant_content = json.dumps(assistant_payload, separators=(",", ":"), sort_keys=True)
    completion_tokens = len(
        await _execute_word_tokenize(consumer_model_id=model_id, text=assistant_content)
    )
    return (
        descriptor,
        ChatCompletionResult(
            completion_id=_deterministic_chat_completion_id(
                model_id=model_id,
                messages=serialized_messages,
            ),
            content=assistant_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )
