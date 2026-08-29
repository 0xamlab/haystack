from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMModelResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    object: Literal["model"] = "model"
    owned_by: str = "algenta"
    runtime_module: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    supported_endpoints: list[str] = Field(default_factory=list)
    runtime_functions: list[str] = Field(default_factory=list)
    tokenizer_kind: str | None = None
    similarity_metric: str | None = None
    provider_backend: str | None = None
    routing_targets: list[str] = Field(default_factory=list)
    resolved_routing_targets: list[str] = Field(default_factory=list)
    chat_routing_targets: list[str] = Field(default_factory=list)
    resolved_chat_routing_targets: list[str] = Field(default_factory=list)
    embedding_routing_targets: list[str] = Field(default_factory=list)
    resolved_embedding_routing_targets: list[str] = Field(default_factory=list)
    routing_fallback_policy: str | None = None
    chat_routing_fallback_policy: str | None = None
    embedding_routing_fallback_policy: str | None = None
    routing_fallback_on: list[str] = Field(default_factory=list)
    chat_routing_fallback_on: list[str] = Field(default_factory=list)
    embedding_routing_fallback_on: list[str] = Field(default_factory=list)
    routing_max_attempts: int | None = None
    chat_routing_max_attempts: int | None = None
    embedding_routing_max_attempts: int | None = None
    timeout_seconds: float | None = None
    chat_timeout_seconds: float | None = None
    embedding_timeout_seconds: float | None = None
    required_provider_headers: list[str] = Field(default_factory=list)
    chat_required_provider_headers: list[str] = Field(default_factory=list)
    embedding_required_provider_headers: list[str] = Field(default_factory=list)
    provider_auth_env_vars: list[str] = Field(default_factory=list)
    chat_provider_auth_env_vars: list[str] = Field(default_factory=list)
    embedding_provider_auth_env_vars: list[str] = Field(default_factory=list)
    provider_auth_configured: bool = False
    chat_provider_auth_configured: bool = False
    embedding_provider_auth_configured: bool = False
    bridge_cache_root: str | None = None
    bridge_auth_env_vars: list[str] = Field(default_factory=list)
    bridge_auth_configured: bool = False
    bridge_tokenizer_backends: list[str] = Field(default_factory=list)
    bridge_artifact_backends: list[str] = Field(default_factory=list)
    available: bool


class LLMModelListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["list"] = "list"
    data: list[LLMModelResult] = Field(default_factory=list)


class TokenizeResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["tokenization"] = "tokenization"
    model: str
    tokenizer_kind: str
    tokens: list[str] = Field(default_factory=list)
    token_count: int


class CountTokensResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["token_count"] = "token_count"
    model: str
    tokenizer_kind: str
    token_count: int


class ArtifactBridgeResolveResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["artifact_bridge_resolution"] = "artifact_bridge_resolution"
    backend: str
    artifact_backend: str | None = None
    repo_id: str
    filename: str
    revision: str | None = None
    local_files_only: bool
    status: Literal["resolved", "not_cached"]
    cache_root: str | None = None
    auth_env_vars: list[str] = Field(default_factory=list)
    auth_configured: bool = False
    auth_env_var_used: str | None = None
    resolved_path: str | None = None


class ChatCompletionToolCallFunctionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    name: str
    arguments: str


class ChatCompletionToolCallResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    type: Literal["function"] = "function"
    function: ChatCompletionToolCallFunctionResult


class ChatCompletionMessageResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ChatCompletionToolCallResult] | None = None


class ChatCompletionDeltaResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChoiceResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    index: int
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter"] = "stop"
    message: ChatCompletionMessageResult


class ChatCompletionChunkChoiceResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    index: int
    delta: ChatCompletionDeltaResult
    finish_reason: Literal["stop"] | None = None


class ChatCompletionUsageResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ProviderAttemptResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    provider_backend: str
    provider_model_id: str
    outcome: Literal["selected", "failed"]
    error_code: str | None = None


class ChatCompletionsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptResult] = Field(default_factory=list)
    choices: list[ChatCompletionChoiceResult] = Field(default_factory=list)
    usage: ChatCompletionUsageResult


class ChatCompletionsStreamChunkResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptResult] = Field(default_factory=list)
    choices: list[ChatCompletionChunkChoiceResult] = Field(default_factory=list)


class EmbeddingVectorResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float] = Field(default_factory=list)
    token_count: int


class EmbeddingUsageResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    prompt_tokens: int
    total_tokens: int


class EmbeddingsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["list"] = "list"
    model: str
    dimensions: int
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptResult] = Field(default_factory=list)
    data: list[EmbeddingVectorResult] = Field(default_factory=list)
    usage: EmbeddingUsageResult


class ResponseOutputContentResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    type: Literal["tokenization", "embedding", "text"]
    text: str
    tokens: list[str] | None = None
    token_count: int
    embedding: list[float] | None = None


class ResponseOutputItemResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    object: Literal["response.output"] = "response.output"
    index: int
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptResult] = Field(default_factory=list)
    content: list[ResponseOutputContentResult] = Field(default_factory=list)


class ResponsesResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    object: Literal["response"] = "response"
    status: Literal["completed"] = "completed"
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptResult] = Field(default_factory=list)
    output: list[ResponseOutputItemResult] = Field(default_factory=list)
    usage: EmbeddingUsageResult


class ResponseLifecycleResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    object: Literal["response"] = "response"
    status: Literal["in_progress", "completed"]
    model: str
    provider_backend: str | None = None
    provider_model_id: str | None = None
    provider_attempts: list[ProviderAttemptResult] = Field(default_factory=list)
    usage: EmbeddingUsageResult | None = None


class ResponseStreamEventResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    type: Literal["response.created", "response.output_item.done", "response.completed"]
    response: ResponseLifecycleResult | None = None
    output_index: int | None = None
    item: ResponseOutputItemResult | None = None


class EmbeddingSimilarityResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["embedding_similarity"] = "embedding_similarity"
    model: str
    similarity_metric: str
    score: float
    dimension: int


class RerankDocumentResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["rerank_result"] = "rerank_result"
    id: str
    index: int
    rank: int
    score: float
    text: str | None = None
    metadata: dict[str, Any] | None = None


class RerankResponseResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    object: Literal["list"] = "list"
    model: str
    similarity_metric: str
    total_documents: int
    returned_documents: int
    data: list[RerankDocumentResult] = Field(default_factory=list)
