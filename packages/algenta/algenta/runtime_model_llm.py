from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _optional_positive_int(data: dict[str, Any], key: str, context: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TypeError(f"{context}.{key} must be a positive integer.")
    return value


def _optional_positive_float(data: dict[str, Any], key: str, context: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0.0:
        raise TypeError(f"{context}.{key} must be a positive number.")
    return float(value)


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _optional_mapping(data: dict[str, Any], key: str, context: str) -> dict[str, Any] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"{context}.{key} must be a mapping.")
    return value


def _require_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    raw = data.get(key) or []
    if not isinstance(raw, list):
        raise TypeError(f"{context}.{key} must be a list.")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item:
            raise TypeError(f"{context}.{key}.{index} must be a non-empty string.")
        result.append(item)
    return result


def _require_float_list(data: dict[str, Any], key: str, context: str) -> list[float]:
    raw = data.get(key) or []
    if not isinstance(raw, list):
        raise TypeError(f"{context}.{key} must be a list.")
    values: list[float] = []
    for index, item in enumerate(raw):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(f"{context}.{key}.{index} must be a number.")
        values.append(float(item))
    return values


def _require_provider_attempts_list(
    data: dict[str, Any],
    key: str,
    context: str,
) -> list[ProviderAttemptOutput]:
    raw = data.get(key) or []
    if not isinstance(raw, list):
        raise TypeError(f"{context}.{key} must be a list.")
    return [ProviderAttemptOutput.from_api(item) for item in raw]


@dataclass(frozen=True)
class LLMModelOutput:
    id: str
    object: str
    owned_by: str
    runtime_module: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    supported_endpoints: list[str] = field(default_factory=list)
    runtime_functions: list[str] = field(default_factory=list)
    tokenizer_kind: str | None = None
    similarity_metric: str | None = None
    provider_backend: str | None = None
    routing_targets: list[str] = field(default_factory=list)
    resolved_routing_targets: list[str] = field(default_factory=list)
    chat_routing_targets: list[str] = field(default_factory=list)
    resolved_chat_routing_targets: list[str] = field(default_factory=list)
    embedding_routing_targets: list[str] = field(default_factory=list)
    resolved_embedding_routing_targets: list[str] = field(default_factory=list)
    routing_fallback_policy: str | None = None
    chat_routing_fallback_policy: str | None = None
    embedding_routing_fallback_policy: str | None = None
    routing_fallback_on: list[str] = field(default_factory=list)
    chat_routing_fallback_on: list[str] = field(default_factory=list)
    embedding_routing_fallback_on: list[str] = field(default_factory=list)
    routing_max_attempts: int | None = None
    chat_routing_max_attempts: int | None = None
    embedding_routing_max_attempts: int | None = None
    timeout_seconds: float | None = None
    chat_timeout_seconds: float | None = None
    embedding_timeout_seconds: float | None = None
    required_provider_headers: list[str] = field(default_factory=list)
    chat_required_provider_headers: list[str] = field(default_factory=list)
    embedding_required_provider_headers: list[str] = field(default_factory=list)
    provider_auth_env_vars: list[str] = field(default_factory=list)
    chat_provider_auth_env_vars: list[str] = field(default_factory=list)
    embedding_provider_auth_env_vars: list[str] = field(default_factory=list)
    provider_auth_configured: bool = False
    chat_provider_auth_configured: bool = False
    embedding_provider_auth_configured: bool = False
    bridge_cache_root: str | None = None
    bridge_auth_env_vars: list[str] = field(default_factory=list)
    bridge_auth_configured: bool = False
    bridge_tokenizer_backends: list[str] = field(default_factory=list)
    bridge_artifact_backends: list[str] = field(default_factory=list)
    available: bool = False

    @classmethod
    def from_api(cls, payload: Any) -> LLMModelOutput:
        context = "models.item"
        data = coerce_payload_mapping(payload)
        available = data.get("available")
        if not isinstance(available, bool):
            raise TypeError(f"{context}.available must be a boolean.")
        bridge_auth_configured = data.get("bridge_auth_configured", False)
        if not isinstance(bridge_auth_configured, bool):
            raise TypeError(f"{context}.bridge_auth_configured must be a boolean.")
        provider_auth_configured = data.get("provider_auth_configured", False)
        if not isinstance(provider_auth_configured, bool):
            raise TypeError(f"{context}.provider_auth_configured must be a boolean.")
        chat_provider_auth_configured = data.get("chat_provider_auth_configured", False)
        if not isinstance(chat_provider_auth_configured, bool):
            raise TypeError(f"{context}.chat_provider_auth_configured must be a boolean.")
        embedding_provider_auth_configured = data.get(
            "embedding_provider_auth_configured",
            False,
        )
        if not isinstance(embedding_provider_auth_configured, bool):
            raise TypeError(
                f"{context}.embedding_provider_auth_configured must be a boolean."
            )
        return cls(
            id=_require_string(data, "id", context),
            object=_require_string(data, "object", context),
            owned_by=_require_string(data, "owned_by", context),
            runtime_module=_require_string(data, "runtime_module", context),
            description=_require_string(data, "description", context),
            capabilities=_require_string_list(data, "capabilities", context),
            supported_endpoints=_require_string_list(data, "supported_endpoints", context),
            runtime_functions=_require_string_list(data, "runtime_functions", context),
            tokenizer_kind=_optional_string(data, "tokenizer_kind", context),
            similarity_metric=_optional_string(data, "similarity_metric", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            routing_targets=_require_string_list(data, "routing_targets", context),
            resolved_routing_targets=_require_string_list(
                data, "resolved_routing_targets", context
            ),
            chat_routing_targets=_require_string_list(data, "chat_routing_targets", context),
            resolved_chat_routing_targets=_require_string_list(
                data, "resolved_chat_routing_targets", context
            ),
            embedding_routing_targets=_require_string_list(
                data,
                "embedding_routing_targets",
                context,
            ),
            resolved_embedding_routing_targets=_require_string_list(
                data,
                "resolved_embedding_routing_targets",
                context,
            ),
            routing_fallback_policy=_optional_string(data, "routing_fallback_policy", context),
            chat_routing_fallback_policy=_optional_string(
                data,
                "chat_routing_fallback_policy",
                context,
            ),
            embedding_routing_fallback_policy=_optional_string(
                data,
                "embedding_routing_fallback_policy",
                context,
            ),
            routing_fallback_on=_require_string_list(data, "routing_fallback_on", context),
            chat_routing_fallback_on=_require_string_list(
                data,
                "chat_routing_fallback_on",
                context,
            ),
            embedding_routing_fallback_on=_require_string_list(
                data,
                "embedding_routing_fallback_on",
                context,
            ),
            routing_max_attempts=_optional_positive_int(data, "routing_max_attempts", context),
            chat_routing_max_attempts=_optional_positive_int(
                data,
                "chat_routing_max_attempts",
                context,
            ),
            embedding_routing_max_attempts=_optional_positive_int(
                data,
                "embedding_routing_max_attempts",
                context,
            ),
            timeout_seconds=_optional_positive_float(data, "timeout_seconds", context),
            chat_timeout_seconds=_optional_positive_float(
                data,
                "chat_timeout_seconds",
                context,
            ),
            embedding_timeout_seconds=_optional_positive_float(
                data,
                "embedding_timeout_seconds",
                context,
            ),
            required_provider_headers=_require_string_list(
                data,
                "required_provider_headers",
                context,
            ),
            chat_required_provider_headers=_require_string_list(
                data,
                "chat_required_provider_headers",
                context,
            ),
            embedding_required_provider_headers=_require_string_list(
                data,
                "embedding_required_provider_headers",
                context,
            ),
            provider_auth_env_vars=_require_string_list(
                data,
                "provider_auth_env_vars",
                context,
            ),
            chat_provider_auth_env_vars=_require_string_list(
                data,
                "chat_provider_auth_env_vars",
                context,
            ),
            embedding_provider_auth_env_vars=_require_string_list(
                data,
                "embedding_provider_auth_env_vars",
                context,
            ),
            provider_auth_configured=provider_auth_configured,
            chat_provider_auth_configured=chat_provider_auth_configured,
            embedding_provider_auth_configured=embedding_provider_auth_configured,
            bridge_cache_root=_optional_string(data, "bridge_cache_root", context),
            bridge_auth_env_vars=_require_string_list(data, "bridge_auth_env_vars", context),
            bridge_auth_configured=bridge_auth_configured,
            bridge_tokenizer_backends=_require_string_list(
                data,
                "bridge_tokenizer_backends",
                context,
            ),
            bridge_artifact_backends=_require_string_list(
                data,
                "bridge_artifact_backends",
                context,
            ),
            available=available,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class LLMModelListOutput:
    object: str = "list"
    data: list[LLMModelOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> LLMModelListOutput:
        context = "models"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            data=[LLMModelOutput.from_api(item) for item in raw_items],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TokenizeOutput:
    object: str
    model: str
    tokenizer_kind: str
    tokens: list[str] = field(default_factory=list)
    token_count: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> TokenizeOutput:
        context = "tokenize"
        data = coerce_payload_mapping(payload)
        return cls(
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            tokenizer_kind=_require_string(data, "tokenizer_kind", context),
            tokens=_require_string_list(data, "tokens", context),
            token_count=_require_integer(data, "token_count", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CountTokensOutput:
    object: str
    model: str
    tokenizer_kind: str
    token_count: int

    @classmethod
    def from_api(cls, payload: Any) -> CountTokensOutput:
        context = "count_tokens"
        data = coerce_payload_mapping(payload)
        return cls(
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            tokenizer_kind=_require_string(data, "tokenizer_kind", context),
            token_count=_require_integer(data, "token_count", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ArtifactBridgeResolveOutput:
    object: str
    backend: str
    artifact_backend: str | None
    repo_id: str
    filename: str
    revision: str | None
    local_files_only: bool
    status: str
    cache_root: str | None
    auth_env_vars: list[str] = field(default_factory=list)
    auth_configured: bool = False
    auth_env_var_used: str | None = None
    resolved_path: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ArtifactBridgeResolveOutput:
        context = "artifact_bridge_resolution"
        data = coerce_payload_mapping(payload)
        auth_configured = data.get("auth_configured", False)
        local_files_only = data.get("local_files_only")
        if not isinstance(auth_configured, bool):
            raise TypeError(f"{context}.auth_configured must be a boolean.")
        if not isinstance(local_files_only, bool):
            raise TypeError(f"{context}.local_files_only must be a boolean.")
        return cls(
            object=_require_string(data, "object", context),
            backend=_require_string(data, "backend", context),
            artifact_backend=_optional_string(data, "artifact_backend", context),
            repo_id=_require_string(data, "repo_id", context),
            filename=_require_string(data, "filename", context),
            revision=_optional_string(data, "revision", context),
            local_files_only=local_files_only,
            status=_require_string(data, "status", context),
            cache_root=_optional_string(data, "cache_root", context),
            auth_env_vars=_require_string_list(data, "auth_env_vars", context),
            auth_configured=auth_configured,
            auth_env_var_used=_optional_string(data, "auth_env_var_used", context),
            resolved_path=_optional_string(data, "resolved_path", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionMessageOutput:
    role: str
    content: str

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionMessageOutput:
        context = "chat_completions.message"
        data = coerce_payload_mapping(payload)
        return cls(
            role=_require_string(data, "role", context),
            content=_require_string(data, "content", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionChoiceOutput:
    index: int
    finish_reason: str
    message: ChatCompletionMessageOutput

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionChoiceOutput:
        context = "chat_completions.choices.item"
        data = coerce_payload_mapping(payload)
        return cls(
            index=_require_integer(data, "index", context),
            finish_reason=_require_string(data, "finish_reason", context),
            message=ChatCompletionMessageOutput.from_api(data.get("message")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionUsageOutput:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionUsageOutput:
        context = "chat_completions.usage"
        data = coerce_payload_mapping(payload)
        return cls(
            prompt_tokens=_require_integer(data, "prompt_tokens", context),
            completion_tokens=_require_integer(data, "completion_tokens", context),
            total_tokens=_require_integer(data, "total_tokens", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ProviderAttemptOutput:
    provider_backend: str
    provider_model_id: str
    outcome: str
    error_code: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ProviderAttemptOutput:
        context = "provider_attempts.item"
        data = coerce_payload_mapping(payload)
        outcome = _require_string(data, "outcome", context)
        if outcome not in {"selected", "failed"}:
            raise TypeError(f"{context}.outcome must be 'selected' or 'failed'.")
        return cls(
            provider_backend=_require_string(data, "provider_backend", context),
            provider_model_id=_require_string(data, "provider_model_id", context),
            outcome=outcome,
            error_code=_optional_string(data, "error_code", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionsOutput:
    id: str
    object: str
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptOutput] = field(default_factory=list)
    choices: list[ChatCompletionChoiceOutput] = field(default_factory=list)
    usage: ChatCompletionUsageOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionsOutput:
        context = "chat_completions"
        data = coerce_payload_mapping(payload)
        raw_choices = data.get("choices") or []
        if not isinstance(raw_choices, list):
            raise TypeError(f"{context}.choices must be a list.")
        return cls(
            id=_require_string(data, "id", context),
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            provider_model_id=_optional_string(data, "provider_model_id", context),
            provider_attempts=_require_provider_attempts_list(data, "provider_attempts", context),
            choices=[ChatCompletionChoiceOutput.from_api(item) for item in raw_choices],
            usage=ChatCompletionUsageOutput.from_api(data.get("usage")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionChunkDeltaOutput:
    role: str | None = None
    content: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionChunkDeltaOutput:
        context = "chat_completions_stream.choices.item.delta"
        data = coerce_payload_mapping(payload)
        role = data.get("role")
        if role is not None and (not isinstance(role, str) or not role):
            raise TypeError(f"{context}.role must be a non-empty string.")
        content = data.get("content")
        if content is not None and (not isinstance(content, str) or not content):
            raise TypeError(f"{context}.content must be a non-empty string.")
        return cls(role=role, content=content)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionChunkChoiceOutput:
    index: int
    delta: ChatCompletionChunkDeltaOutput
    finish_reason: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionChunkChoiceOutput:
        context = "chat_completions_stream.choices.item"
        data = coerce_payload_mapping(payload)
        finish_reason = data.get("finish_reason")
        if finish_reason is not None and (not isinstance(finish_reason, str) or not finish_reason):
            raise TypeError(f"{context}.finish_reason must be a non-empty string.")
        return cls(
            index=_require_integer(data, "index", context),
            delta=ChatCompletionChunkDeltaOutput.from_api(data.get("delta")),
            finish_reason=finish_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ChatCompletionsStreamChunkOutput:
    id: str
    object: str
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptOutput] = field(default_factory=list)
    choices: list[ChatCompletionChunkChoiceOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> ChatCompletionsStreamChunkOutput:
        context = "chat_completions_stream"
        data = coerce_payload_mapping(payload)
        raw_choices = data.get("choices") or []
        if not isinstance(raw_choices, list):
            raise TypeError(f"{context}.choices must be a list.")
        return cls(
            id=_require_string(data, "id", context),
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            provider_model_id=_optional_string(data, "provider_model_id", context),
            provider_attempts=_require_provider_attempts_list(data, "provider_attempts", context),
            choices=[ChatCompletionChunkChoiceOutput.from_api(item) for item in raw_choices],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EmbeddingVectorOutput:
    object: str
    index: int
    embedding: list[float] = field(default_factory=list)
    token_count: int = 0

    @classmethod
    def from_api(cls, payload: Any) -> EmbeddingVectorOutput:
        context = "embeddings.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            object=_require_string(data, "object", context),
            index=_require_integer(data, "index", context),
            embedding=_require_float_list(data, "embedding", context),
            token_count=_require_integer(data, "token_count", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EmbeddingUsageOutput:
    prompt_tokens: int
    total_tokens: int

    @classmethod
    def from_api(cls, payload: Any) -> EmbeddingUsageOutput:
        context = "embeddings.usage"
        data = coerce_payload_mapping(payload)
        return cls(
            prompt_tokens=_require_integer(data, "prompt_tokens", context),
            total_tokens=_require_integer(data, "total_tokens", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EmbeddingsOutput:
    object: str
    model: str
    dimensions: int
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptOutput] = field(default_factory=list)
    data: list[EmbeddingVectorOutput] = field(default_factory=list)
    usage: EmbeddingUsageOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> EmbeddingsOutput:
        context = "embeddings"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            dimensions=_require_integer(data, "dimensions", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            provider_model_id=_optional_string(data, "provider_model_id", context),
            provider_attempts=_require_provider_attempts_list(data, "provider_attempts", context),
            data=[EmbeddingVectorOutput.from_api(item) for item in raw_items],
            usage=EmbeddingUsageOutput.from_api(data.get("usage")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ResponseOutputContentOutput:
    type: str
    text: str
    token_count: int
    tokens: list[str] | None = None
    embedding: list[float] | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ResponseOutputContentOutput:
        context = "responses.output.item.content.item"
        data = coerce_payload_mapping(payload)
        tokens = data.get("tokens")
        if tokens is not None:
            if not isinstance(tokens, list):
                raise TypeError(f"{context}.tokens must be a list.")
            token_values = _require_string_list({"tokens": tokens}, "tokens", context)
        else:
            token_values = None
        embedding = data.get("embedding")
        if embedding is not None:
            if not isinstance(embedding, list):
                raise TypeError(f"{context}.embedding must be a list.")
            embedding_values = _require_float_list({"embedding": embedding}, "embedding", context)
        else:
            embedding_values = None
        return cls(
            type=_require_string(data, "type", context),
            text=_require_string(data, "text", context),
            token_count=_require_integer(data, "token_count", context),
            tokens=token_values,
            embedding=embedding_values,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ResponseOutputItemOutput:
    id: str
    object: str
    index: int
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptOutput] = field(default_factory=list)
    content: list[ResponseOutputContentOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> ResponseOutputItemOutput:
        context = "responses.output.item"
        data = coerce_payload_mapping(payload)
        raw_content = data.get("content") or []
        if not isinstance(raw_content, list):
            raise TypeError(f"{context}.content must be a list.")
        return cls(
            id=_require_string(data, "id", context),
            object=_require_string(data, "object", context),
            index=_require_integer(data, "index", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            provider_model_id=_optional_string(data, "provider_model_id", context),
            provider_attempts=_require_provider_attempts_list(data, "provider_attempts", context),
            content=[ResponseOutputContentOutput.from_api(item) for item in raw_content],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ResponsesOutput:
    id: str
    object: str
    status: str
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptOutput] = field(default_factory=list)
    output: list[ResponseOutputItemOutput] = field(default_factory=list)
    usage: EmbeddingUsageOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ResponsesOutput:
        context = "responses"
        data = coerce_payload_mapping(payload)
        raw_output = data.get("output") or []
        if not isinstance(raw_output, list):
            raise TypeError(f"{context}.output must be a list.")
        return cls(
            id=_require_string(data, "id", context),
            object=_require_string(data, "object", context),
            status=_require_string(data, "status", context),
            model=_require_string(data, "model", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            provider_model_id=_optional_string(data, "provider_model_id", context),
            provider_attempts=_require_provider_attempts_list(data, "provider_attempts", context),
            output=[ResponseOutputItemOutput.from_api(item) for item in raw_output],
            usage=EmbeddingUsageOutput.from_api(data.get("usage")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ResponseLifecycleOutput:
    id: str
    object: str
    status: str
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptOutput] = field(default_factory=list)
    usage: EmbeddingUsageOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ResponseLifecycleOutput:
        context = "responses_stream.response"
        data = coerce_payload_mapping(payload)
        return cls(
            id=_require_string(data, "id", context),
            object=_require_string(data, "object", context),
            status=_require_string(data, "status", context),
            model=_require_string(data, "model", context),
            provider_backend=_optional_string(data, "provider_backend", context),
            provider_model_id=_optional_string(data, "provider_model_id", context),
            provider_attempts=_require_provider_attempts_list(data, "provider_attempts", context),
            usage=EmbeddingUsageOutput.from_api(data.get("usage")) if data.get("usage") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ResponseStreamEventOutput:
    type: str
    response: ResponseLifecycleOutput | None = None
    output_index: int | None = None
    item: ResponseOutputItemOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ResponseStreamEventOutput:
        context = "responses_stream"
        data = coerce_payload_mapping(payload)
        response_payload = data.get("response")
        item_payload = data.get("item")
        output_index = data.get("output_index")
        if output_index is not None and (isinstance(output_index, bool) or not isinstance(output_index, int)):
            raise TypeError(f"{context}.output_index must be an integer.")
        return cls(
            type=_require_string(data, "type", context),
            response=ResponseLifecycleOutput.from_api(response_payload)
            if response_payload is not None
            else None,
            output_index=output_index,
            item=ResponseOutputItemOutput.from_api(item_payload) if item_payload is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EmbeddingSimilarityOutput:
    object: str
    model: str
    similarity_metric: str
    score: float
    dimension: int

    @classmethod
    def from_api(cls, payload: Any) -> EmbeddingSimilarityOutput:
        context = "embedding_similarity"
        data = coerce_payload_mapping(payload)
        return cls(
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            similarity_metric=_require_string(data, "similarity_metric", context),
            score=_require_number(data, "score", context),
            dimension=_require_integer(data, "dimension", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RerankDocumentOutput:
    object: str
    id: str
    index: int
    rank: int
    score: float
    text: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RerankDocumentOutput:
        context = "rerank.data.item"
        data = coerce_payload_mapping(payload)
        return cls(
            object=_require_string(data, "object", context),
            id=_require_string(data, "id", context),
            index=_require_integer(data, "index", context),
            rank=_require_integer(data, "rank", context),
            score=_require_number(data, "score", context),
            text=_optional_string(data, "text", context),
            metadata=_optional_mapping(data, "metadata", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RerankResponseOutput:
    object: str
    model: str
    similarity_metric: str
    total_documents: int
    returned_documents: int
    data: list[RerankDocumentOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RerankResponseOutput:
        context = "rerank"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("data") or []
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.data must be a list.")
        return cls(
            object=_require_string(data, "object", context),
            model=_require_string(data, "model", context),
            similarity_metric=_require_string(data, "similarity_metric", context),
            total_documents=_require_integer(data, "total_documents", context),
            returned_documents=_require_integer(data, "returned_documents", context),
            data=[RerankDocumentOutput.from_api(item) for item in raw_items],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
