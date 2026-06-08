"""Dataclasses (LLMAPIError, LLMModelDescriptor, etc.) + helpers + list/get descriptors.

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
    # Test code monkey-patches llm_api_service.list_public_runtime_library_descriptors
    # at the facade level — look up via facade so the patch propagates here.
    from apps.api_server.services import llm_api_service as _facade
    return {
        descriptor.name: descriptor.functions
        for descriptor in _facade.list_public_runtime_library_descriptors()
    }


def list_llm_model_descriptors() -> tuple[LLMModelDescriptor, ...]:
    from apps.api_server.services import llm_api_service as _facade
    runtime_health = _facade.get_public_runtime_library_health()
    runtime_modules = _runtime_module_descriptors()
    tokenizer_functions = runtime_modules.get(_TEXT_TOKENIZER_MODEL_ID)
    embedding_functions = runtime_modules.get(_EMBEDDINGS_MODULE_ID)
    tokenizer_backends = _facade._detect_bridge_backends(_TOKENIZER_BRIDGE_SPECS)
    artifact_backends = _facade._detect_bridge_backends(_ARTIFACT_BRIDGE_SPECS)
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
    from apps.api_server.services import llm_api_service as _facade
    for descriptor in _facade.list_llm_model_descriptors():
        if descriptor.model_id == model_id:
            return descriptor
    raise LLMAPIError(
        "model_not_supported",
        f"Model '{model_id}' is not available on the current Algenta LLM API surface.",
        {"model": model_id},
    )

