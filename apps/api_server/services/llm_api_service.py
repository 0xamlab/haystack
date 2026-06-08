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


@dataclass(frozen=True)
class LLMAPIError(Exception):
    code: str
    message: str
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class LLMModelDescriptor:
    model_id: str
    runtime_module: str
    description: str
    capabilities: tuple[str, ...]
    supported_endpoints: tuple[str, ...]
    tokenizer_kind: str | None
    similarity_metric: str | None
    runtime_functions: tuple[str, ...]
    available: bool
    bridge_tokenizer_backends: tuple[str, ...] = ()
    bridge_artifact_backends: tuple[str, ...] = ()
    bridge_cache_root: str | None = None
    bridge_auth_env_vars: tuple[str, ...] = ()
    bridge_auth_configured: bool = False
    provider_backend: str | None = None
    routing_targets: tuple[str, ...] = ()
    resolved_routing_targets: tuple[str, ...] = ()
    chat_routing_targets: tuple[str, ...] = ()
    resolved_chat_routing_targets: tuple[str, ...] = ()
    embedding_routing_targets: tuple[str, ...] = ()
    resolved_embedding_routing_targets: tuple[str, ...] = ()
    routing_fallback_policy: str | None = None
    chat_routing_fallback_policy: str | None = None
    embedding_routing_fallback_policy: str | None = None
    routing_fallback_on: tuple[str, ...] = ()
    chat_routing_fallback_on: tuple[str, ...] = ()
    embedding_routing_fallback_on: tuple[str, ...] = ()
    routing_max_attempts: int | None = None
    chat_routing_max_attempts: int | None = None
    embedding_routing_max_attempts: int | None = None
    timeout_seconds: float | None = None
    chat_timeout_seconds: float | None = None
    embedding_timeout_seconds: float | None = None
    required_provider_headers: tuple[str, ...] = ()
    chat_required_provider_headers: tuple[str, ...] = ()
    embedding_required_provider_headers: tuple[str, ...] = ()
    provider_auth_env_vars: tuple[str, ...] = ()
    chat_provider_auth_env_vars: tuple[str, ...] = ()
    embedding_provider_auth_env_vars: tuple[str, ...] = ()
    provider_auth_configured: bool = False
    chat_provider_auth_configured: bool = False
    embedding_provider_auth_configured: bool = False


@dataclass(frozen=True)
class RerankDocumentResult:
    document_id: str
    index: int
    rank: int
    score: float
    text: str | None
    metadata: dict[str, object] | None


@dataclass(frozen=True)
class ProviderExecutionMetadata:
    provider_backend: str
    provider_model_id: str


@dataclass(frozen=True)
class ProviderAttemptRecord:
    provider_backend: str
    provider_model_id: str
    outcome: Literal["selected", "failed"]
    error_code: str | None = None


@dataclass(frozen=True)
class GeneratedEmbedding:
    index: int
    embedding: list[float]
    token_count: int
    provider: ProviderExecutionMetadata | None = None
    provider_attempts: tuple[ProviderAttemptRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UtilityResponseOutputItem:
    index: int
    item_type: Literal["tokenization", "embedding", "text"]
    text: str
    tokens: list[str] | None
    token_count: int
    embedding: list[float] | None
    provider: ProviderExecutionMetadata | None = None
    provider_attempts: tuple[ProviderAttemptRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ChatCompletionResult:
    completion_id: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    provider: ProviderExecutionMetadata | None = None
    provider_attempts: tuple[ProviderAttemptRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ArtifactBridgeResolution:
    backend: str
    artifact_backend: str | None
    repo_id: str
    filename: str
    revision: str | None
    local_files_only: bool
    status: Literal["resolved", "not_cached"]
    cache_root: str | None
    auth_env_vars: tuple[str, ...]
    auth_configured: bool
    auth_env_var_used: str | None
    resolved_path: str | None


_TEXT_TOKENIZER_MODEL_ID = "text.tokenizer"
_TEXT_TOKENIZER_TOKENIZE_FUNCTION = "word_tokenize"
_TEXT_TOKENIZER_CAPABILITIES = ("tokenize", "count_tokens", "chat_completions")
_TEXT_TOKENIZER_SUPPORTED_ENDPOINTS = (
    "/v1/models",
    "/v1/tokenize",
    "/v1/count_tokens",
    "/v1/chat/completions",
    "/v1/responses",
)
_HASH_EMBEDDING_MODEL_ID = "text.hash_embedding_v1"
_HASH_EMBEDDING_CAPABILITIES = ("embeddings",)
_HASH_EMBEDDING_SUPPORTED_ENDPOINTS = ("/v1/models", "/v1/embeddings", "/v1/responses")
_HASH_EMBEDDING_PERSON = b"algenta_embed_v1"
_EMBEDDINGS_MODULE_ID = "embeddings"
_EMBEDDING_SIMILARITY_MODELS = (
    (
        "embeddings.cosine_similarity",
        "cosine_similarity",
        "cosine",
        "Cosine similarity over caller-supplied embedding vectors.",
    ),
    (
        "embeddings.euclidean_distance",
        "euclidean_distance",
        "euclidean",
        "Euclidean distance over caller-supplied embedding vectors.",
    ),
    (
        "embeddings.manhattan_distance",
        "manhattan_distance",
        "manhattan",
        "Manhattan distance over caller-supplied embedding vectors.",
    ),
)
_EMBEDDING_SIMILARITY_CAPABILITIES = ("embedding_similarity", "rerank")
_EMBEDDING_SIMILARITY_SUPPORTED_ENDPOINTS = (
    "/v1/models",
    "/v1/embeddings/similarity",
    "/v1/rerank",
)
_DISTANCE_METRICS = frozenset({"euclidean", "manhattan"})
_TOKENIZER_BRIDGE_SPECS = (
    ("tiktoken", "tiktoken"),
    ("tokenizers", "tokenizers"),
    ("sentencepiece", "sentencepiece"),
)
_ARTIFACT_BRIDGE_SPECS = (
    ("safetensors", "safetensors"),
    ("huggingface_hub", "huggingface_hub"),
)
_HUGGINGFACE_CACHE_ENV = "HUGGINGFACE_HUB_CACHE"
_HF_HOME_ENV = "HF_HOME"
_HUGGINGFACE_AUTH_ENV_VARS = (
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
)
_HUGGINGFACE_LOCAL_MISS_EXCEPTIONS = frozenset(
    {
        "LocalEntryNotFoundError",
        "EntryNotFoundError",
        "RepositoryNotFoundError",
        "RevisionNotFoundError",
        "RemoteEntryNotFoundError",
    }
)


@lru_cache(maxsize=1)
def _detect_bridge_backends(
    specs: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    return tuple(
        backend_name
        for module_name, backend_name in specs
        if importlib.util.find_spec(module_name) is not None
    )


def _resolve_artifact_bridge_cache_root(
    artifact_backends: tuple[str, ...],
) -> str | None:
    explicit_cache = os.environ.get(_HUGGINGFACE_CACHE_ENV, "").strip()
    if explicit_cache:
        return str(Path(explicit_cache).expanduser())

    hf_home = os.environ.get(_HF_HOME_ENV, "").strip()
    if hf_home:
        return str((Path(hf_home).expanduser() / "hub"))

    if "huggingface_hub" in artifact_backends:
        return str((Path.home() / ".cache" / "huggingface" / "hub"))
    return None


def _resolve_artifact_bridge_auth_env_vars(
    artifact_backends: tuple[str, ...],
) -> tuple[str, ...]:
    if "huggingface_hub" not in artifact_backends:
        return ()
    return _HUGGINGFACE_AUTH_ENV_VARS


def _artifact_bridge_auth_configured(auth_env_vars: tuple[str, ...]) -> bool:
    return any(os.environ.get(name, "").strip() for name in auth_env_vars)


def _artifact_bridge_auth_token(
    auth_env_vars: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for env_var in auth_env_vars:
        value = os.environ.get(env_var, "").strip()
        if value:
            return env_var, value
    return None, None


def _artifact_bridge_backend_for_filename(
    filename: str,
    artifact_backends: tuple[str, ...],
) -> str | None:
    if filename.endswith(".safetensors") and "safetensors" in artifact_backends:
        return "safetensors"
    return None


def _hf_hub_download(
    *,
    repo_id: str,
    filename: str,
    revision: str | None,
    cache_root: str | None,
    local_files_only: bool,
    auth_token: str | None,
) -> str:
    huggingface_hub = importlib.import_module("huggingface_hub")
    kwargs: dict[str, object] = {
        "repo_id": repo_id,
        "filename": filename,
        "local_files_only": local_files_only,
    }
    if revision is not None:
        kwargs["revision"] = revision
    if cache_root is not None:
        kwargs["cache_dir"] = cache_root
    if auth_token is not None:
        kwargs["token"] = auth_token
    return str(huggingface_hub.hf_hub_download(**kwargs))


def _require_model_capability(
    descriptor: LLMModelDescriptor,
    *,
    capability: str,
    operation: str,
) -> None:
    if capability in descriptor.capabilities:
        return
    raise LLMAPIError(
        "model_capability_unsupported",
        f"Model '{descriptor.model_id}' does not support {operation}.",
        {"model": descriptor.model_id, "required_capability": capability},
    )


def _validate_embedding_dimensions(
    *,
    model_id: str,
    left_dimension: int,
    right_dimension: int,
) -> None:
    if left_dimension == right_dimension:
        return
    raise LLMAPIError(
        "invalid_embedding_dimensions",
        "Embedding vectors must have identical dimensions.",
        {
            "model": model_id,
            "left_dimension": left_dimension,
            "right_dimension": right_dimension,
        },
    )


def _rerank_sort_order(similarity_metric: str | None) -> Literal["ascending", "descending"]:
    if similarity_metric in _DISTANCE_METRICS:
        return "ascending"
    return "descending"


def _runtime_module_descriptors() -> dict[str, tuple[str, ...]]:
    return {
        descriptor.name: descriptor.functions
        for descriptor in list_public_runtime_library_descriptors()
    }


def list_llm_model_descriptors() -> tuple[LLMModelDescriptor, ...]:
    runtime_health = get_public_runtime_library_health()
    runtime_modules = _runtime_module_descriptors()
    tokenizer_functions = runtime_modules.get(_TEXT_TOKENIZER_MODEL_ID)
    embedding_functions = runtime_modules.get(_EMBEDDINGS_MODULE_ID)
    tokenizer_backends = _detect_bridge_backends(_TOKENIZER_BRIDGE_SPECS)
    artifact_backends = _detect_bridge_backends(_ARTIFACT_BRIDGE_SPECS)
    bridge_cache_root = _resolve_artifact_bridge_cache_root(artifact_backends)
    bridge_auth_env_vars = _resolve_artifact_bridge_auth_env_vars(artifact_backends)
    bridge_auth_configured = _artifact_bridge_auth_configured(bridge_auth_env_vars)

    descriptors: list[LLMModelDescriptor] = []

    if tokenizer_functions is not None:
        descriptors.append(
            LLMModelDescriptor(
                model_id=_TEXT_TOKENIZER_MODEL_ID,
                runtime_module=_TEXT_TOKENIZER_MODEL_ID,
                description=(
                    "Deterministic word tokenizer backed by the signed Algenta runtime library "
                    "catalog."
                ),
                capabilities=_TEXT_TOKENIZER_CAPABILITIES,
                supported_endpoints=_TEXT_TOKENIZER_SUPPORTED_ENDPOINTS,
                tokenizer_kind="word",
                similarity_metric=None,
                runtime_functions=tokenizer_functions,
                bridge_tokenizer_backends=tokenizer_backends,
                bridge_artifact_backends=artifact_backends,
                bridge_cache_root=bridge_cache_root,
                bridge_auth_env_vars=bridge_auth_env_vars,
                bridge_auth_configured=bridge_auth_configured,
                available=runtime_health.runtime_available,
            )
        )
        if _TEXT_TOKENIZER_TOKENIZE_FUNCTION in frozenset(tokenizer_functions):
            descriptors.append(
                LLMModelDescriptor(
                    model_id=_HASH_EMBEDDING_MODEL_ID,
                    runtime_module=_TEXT_TOKENIZER_MODEL_ID,
                    description=(
                        "Deterministic lexical hash embeddings generated from runtime tokenization "
                        "and stable feature hashing."
                    ),
                    capabilities=_HASH_EMBEDDING_CAPABILITIES,
                    supported_endpoints=_HASH_EMBEDDING_SUPPORTED_ENDPOINTS,
                    tokenizer_kind="word",
                    similarity_metric=None,
                    runtime_functions=(_TEXT_TOKENIZER_TOKENIZE_FUNCTION,),
                    bridge_tokenizer_backends=tokenizer_backends,
                    bridge_artifact_backends=artifact_backends,
                    bridge_cache_root=bridge_cache_root,
                    bridge_auth_env_vars=bridge_auth_env_vars,
                    bridge_auth_configured=bridge_auth_configured,
                    available=runtime_health.runtime_available,
                )
            )

    if embedding_functions is not None:
        exported_embedding_functions = frozenset(embedding_functions)
        for model_id, function_name, metric_name, description in _EMBEDDING_SIMILARITY_MODELS:
            if function_name not in exported_embedding_functions:
                continue
            descriptors.append(
                LLMModelDescriptor(
                    model_id=model_id,
                    runtime_module=_EMBEDDINGS_MODULE_ID,
                    description=description,
                    capabilities=_EMBEDDING_SIMILARITY_CAPABILITIES,
                    supported_endpoints=_EMBEDDING_SIMILARITY_SUPPORTED_ENDPOINTS,
                    tokenizer_kind=None,
                    similarity_metric=metric_name,
                    runtime_functions=(function_name,),
                    bridge_tokenizer_backends=(),
                    bridge_artifact_backends=(),
                    available=runtime_health.runtime_available,
                )
            )

    seen_model_ids = {descriptor.model_id for descriptor in descriptors}
    try:
        provider_configs = llm_provider_service.load_provider_model_configs()
    except ValueError as exc:
        raise LLMAPIError(
            "invalid_provider_configuration",
            "Provider model configuration is invalid.",
            {"cause": str(exc)},
        ) from exc

    for provider_config in provider_configs:
        if provider_config.model_id in seen_model_ids:
            continue
        supported_endpoints = ["/v1/models"]
        if "chat_completions" in provider_config.capabilities:
            supported_endpoints.append("/v1/chat/completions")
        if "embeddings" in provider_config.capabilities:
            supported_endpoints.append("/v1/embeddings")
        if "chat_completions" in provider_config.capabilities or "embeddings" in provider_config.capabilities:
            supported_endpoints.append("/v1/responses")
        descriptors.append(
            LLMModelDescriptor(
                model_id=provider_config.model_id,
                runtime_module=f"provider.{provider_config.backend}",
                description=provider_config.description,
                capabilities=provider_config.capabilities,
                supported_endpoints=tuple(supported_endpoints),
                tokenizer_kind=None,
                similarity_metric=None,
                runtime_functions=(),
                bridge_tokenizer_backends=(),
                bridge_artifact_backends=(),
                available=True,
                provider_backend=provider_config.backend,
                routing_targets=provider_config.routing_targets,
                resolved_routing_targets=llm_provider_service.get_provider_resolved_route_targets(
                    model_id=provider_config.model_id
                ),
                chat_routing_targets=provider_config.chat_routing_targets,
                resolved_chat_routing_targets=(
                    llm_provider_service.get_provider_resolved_chat_route_targets(
                        model_id=provider_config.model_id
                    )
                ),
                embedding_routing_targets=provider_config.embedding_routing_targets,
                resolved_embedding_routing_targets=(
                    llm_provider_service.get_provider_resolved_embedding_route_targets(
                        model_id=provider_config.model_id
                    )
                ),
                routing_fallback_policy=provider_config.routing_fallback_policy,
                chat_routing_fallback_policy=provider_config.chat_routing_fallback_policy,
                embedding_routing_fallback_policy=provider_config.embedding_routing_fallback_policy,
                routing_fallback_on=provider_config.routing_fallback_on,
                chat_routing_fallback_on=provider_config.chat_routing_fallback_on,
                embedding_routing_fallback_on=provider_config.embedding_routing_fallback_on,
                routing_max_attempts=provider_config.routing_max_attempts,
                chat_routing_max_attempts=provider_config.chat_routing_max_attempts,
                embedding_routing_max_attempts=provider_config.embedding_routing_max_attempts,
                timeout_seconds=provider_config.timeout_seconds,
                chat_timeout_seconds=provider_config.chat_timeout_seconds,
                embedding_timeout_seconds=provider_config.embedding_timeout_seconds,
                required_provider_headers=llm_provider_service.get_provider_required_header_names(
                    model_id=provider_config.model_id
                ),
                chat_required_provider_headers=(
                    llm_provider_service.get_provider_required_header_names_for_capability(
                        model_id=provider_config.model_id,
                        capability="chat_completions",
                    )
                ),
                embedding_required_provider_headers=(
                    llm_provider_service.get_provider_required_header_names_for_capability(
                        model_id=provider_config.model_id,
                        capability="embeddings",
                    )
                ),
                provider_auth_env_vars=llm_provider_service.get_provider_required_auth_env_vars(
                    model_id=provider_config.model_id
                ),
                chat_provider_auth_env_vars=(
                    llm_provider_service.get_provider_required_auth_env_vars_for_capability(
                        model_id=provider_config.model_id,
                        capability="chat_completions",
                    )
                ),
                embedding_provider_auth_env_vars=(
                    llm_provider_service.get_provider_required_auth_env_vars_for_capability(
                        model_id=provider_config.model_id,
                        capability="embeddings",
                    )
                ),
                provider_auth_configured=llm_provider_service.provider_auth_configured(
                    model_id=provider_config.model_id
                ),
                chat_provider_auth_configured=(
                    llm_provider_service.provider_auth_configured_for_capability(
                        model_id=provider_config.model_id,
                        capability="chat_completions",
                    )
                ),
                embedding_provider_auth_configured=(
                    llm_provider_service.provider_auth_configured_for_capability(
                        model_id=provider_config.model_id,
                        capability="embeddings",
                    )
                ),
            )
        )

    descriptors.sort(key=lambda item: item.model_id)
    return tuple(descriptors)


def get_llm_model_descriptor(model_id: str) -> LLMModelDescriptor:
    for descriptor in list_llm_model_descriptors():
        if descriptor.model_id == model_id:
            return descriptor
    raise LLMAPIError(
        "model_not_supported",
        f"Model '{model_id}' is not available on the current Algenta LLM API surface.",
        {"model": model_id},
    )


def resolve_artifact_bridge(
    *,
    repo_id: str,
    filename: str,
    revision: str | None = None,
    local_files_only: bool = True,
) -> ArtifactBridgeResolution:
    artifact_backends = _detect_bridge_backends(_ARTIFACT_BRIDGE_SPECS)
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
        resolved_path = _hf_hub_download(
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
    execution = await execute_public_runtime_library(
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
    descriptor = get_llm_model_descriptor(model_id)
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
    descriptor = get_llm_model_descriptor(model_id)
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
    execution = await execute_public_runtime_library(
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
    descriptor = get_llm_model_descriptor(model_id)
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
        execution = await execute_public_runtime_library(
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
    descriptor = get_llm_model_descriptor(model_id)
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
    descriptor = get_llm_model_descriptor(model_id)
    outputs: list[UtilityResponseOutputItem] = []
    total_tokens = 0
    provider_config = llm_provider_service.get_configured_provider_model(model_id)

    if provider_config is not None and "chat_completions" in descriptor.capabilities:
        completion_ids: list[str] = []
        for index, text in enumerate(inputs):
            _, completion = await create_chat_completion(
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
        embedding_descriptor, generated, total_tokens = await create_text_embeddings(
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
) -> tuple[LLMModelDescriptor, ChatCompletionResult]:
    descriptor = get_llm_model_descriptor(model_id)
    _require_model_capability(
        descriptor,
        capability="chat_completions",
        operation="chat completions",
    )
    provider_config = llm_provider_service.get_configured_provider_model(model_id)
    if provider_config is not None:
        return descriptor, await llm_provider_service.routed_provider_chat_completion(
            model_id=model_id,
            messages=messages,
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
