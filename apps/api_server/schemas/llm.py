from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_serializer


class LLMModelResponse(BaseModel):
    id: str
    object: Literal["model"] = "model"
    owned_by: str = "algenta"
    runtime_module: str
    description: str
    capabilities: list[str]
    supported_endpoints: list[str]
    runtime_functions: list[str]
    tokenizer_kind: str | None = None
    similarity_metric: str | None = None
    provider_backend: str | None = Field(
        default=None,
        description="Provider backend identifier for provider-routed models.",
    )
    routing_targets: list[str] = Field(
        default_factory=list,
        description="Ordered shared provider-routing targets for router-backed models.",
    )
    resolved_routing_targets: list[str] = Field(
        default_factory=list,
        description="Flattened shared provider-routing leaf targets for router-backed models.",
    )
    chat_routing_targets: list[str] = Field(
        default_factory=list,
        description="Ordered chat-completions provider-routing targets for router-backed models.",
    )
    resolved_chat_routing_targets: list[str] = Field(
        default_factory=list,
        description="Flattened chat-completions provider-routing leaf targets for router-backed models.",
    )
    embedding_routing_targets: list[str] = Field(
        default_factory=list,
        description="Ordered embeddings provider-routing targets for router-backed models.",
    )
    resolved_embedding_routing_targets: list[str] = Field(
        default_factory=list,
        description="Flattened embeddings provider-routing leaf targets for router-backed models.",
    )
    routing_fallback_policy: str | None = Field(
        default=None,
        description="Router failover policy for retryable provider errors when backend='router'.",
    )
    chat_routing_fallback_policy: str | None = Field(
        default=None,
        description="Chat-specific router failover policy for retryable provider errors when backend='router'.",
    )
    embedding_routing_fallback_policy: str | None = Field(
        default=None,
        description="Embeddings-specific router failover policy for retryable provider errors when backend='router'.",
    )
    routing_fallback_on: list[str] = Field(
        default_factory=list,
        description="Shared retryable provider error codes that are allowed to trigger router failover when backend='router'.",
    )
    chat_routing_fallback_on: list[str] = Field(
        default_factory=list,
        description="Chat-specific retryable provider error codes that are allowed to trigger router failover when backend='router'.",
    )
    embedding_routing_fallback_on: list[str] = Field(
        default_factory=list,
        description="Embeddings-specific retryable provider error codes that are allowed to trigger router failover when backend='router'.",
    )
    routing_max_attempts: int | None = Field(
        default=None,
        description="Shared maximum number of routed provider targets to attempt when backend='router'.",
    )
    chat_routing_max_attempts: int | None = Field(
        default=None,
        description="Chat-specific maximum number of routed provider targets to attempt when backend='router'.",
    )
    embedding_routing_max_attempts: int | None = Field(
        default=None,
        description="Embeddings-specific maximum number of routed provider targets to attempt when backend='router'.",
    )
    timeout_seconds: float | None = Field(
        default=None,
        description="Shared provider HTTP timeout in seconds for this model entry.",
    )
    chat_timeout_seconds: float | None = Field(
        default=None,
        description="Chat-specific provider HTTP timeout in seconds for this model entry.",
    )
    embedding_timeout_seconds: float | None = Field(
        default=None,
        description="Embeddings-specific provider HTTP timeout in seconds for this model entry.",
    )
    required_provider_headers: list[str] = Field(
        default_factory=list,
        description="Additional upstream HTTP header names required by this provider-backed model configuration.",
    )
    chat_required_provider_headers: list[str] = Field(
        default_factory=list,
        description="Additional upstream HTTP header names required for chat-completions on this provider-backed model configuration.",
    )
    embedding_required_provider_headers: list[str] = Field(
        default_factory=list,
        description="Additional upstream HTTP header names required for embeddings on this provider-backed model configuration.",
    )
    provider_auth_env_vars: list[str] = Field(
        default_factory=list,
        description="Environment variable names required to authenticate this provider-backed model configuration.",
    )
    chat_provider_auth_env_vars: list[str] = Field(
        default_factory=list,
        description="Environment variable names required to authenticate chat-completions on this provider-backed model configuration.",
    )
    embedding_provider_auth_env_vars: list[str] = Field(
        default_factory=list,
        description="Environment variable names required to authenticate embeddings on this provider-backed model configuration.",
    )
    provider_auth_configured: bool = Field(
        default=False,
        description="Whether all required provider auth environment variables are configured for this model entry.",
    )
    chat_provider_auth_configured: bool = Field(
        default=False,
        description="Whether all chat-completions provider auth environment variables are configured for this model entry.",
    )
    embedding_provider_auth_configured: bool = Field(
        default=False,
        description="Whether all embeddings provider auth environment variables are configured for this model entry.",
    )
    bridge_cache_root: str | None = Field(
        default=None,
        description="Resolved artifact/cache bridge root when Hugging Face cache support is available.",
    )
    bridge_auth_env_vars: list[str] = Field(
        default_factory=list,
        description="Supported environment variable aliases for artifact-bridge authentication.",
    )
    bridge_auth_configured: bool = Field(
        default=False,
        description="Whether one of the supported artifact-bridge auth environment variables is configured.",
    )
    bridge_tokenizer_backends: list[str] = Field(
        default_factory=list,
        description="Detected optional tokenizer bridge backends available in the current checkout.",
    )
    bridge_artifact_backends: list[str] = Field(
        default_factory=list,
        description="Detected optional artifact/cache bridge backends available in the current checkout.",
    )
    streaming_mode: Literal["passthrough", "synthetic"] = Field(
        default="synthetic",
        description=(
            "Truthful streaming capability for this model. 'passthrough' means stream=true "
            "returns the upstream's own incremental chunks as they are generated; 'synthetic' "
            "means stream=true still returns valid SSE, but the content is produced by one "
            "buffered call and sliced into fixed-size chunks afterward."
        ),
    )
    supported_parameters: list[str] = Field(
        default_factory=list,
        description="Chat-completions request parameters this model's backend actually honors.",
    )
    available: bool


class LLMModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[LLMModelResponse]


class TokenizeRequest(BaseModel):
    model: str = Field(
        default="text.tokenizer",
        description="Model identifier from GET /v1/models.",
    )
    input: str = Field(..., description="UTF-8 text to tokenize.")


class TokenizeResponse(BaseModel):
    object: Literal["tokenization"] = "tokenization"
    model: str
    tokenizer_kind: str
    tokens: list[str]
    token_count: int


class ArtifactBridgeResolveRequest(BaseModel):
    repo_id: str = Field(..., description="Hugging Face repository identifier.")
    filename: str = Field(..., description="Artifact filename to resolve from the selected repository.")
    revision: str | None = Field(
        default=None,
        description="Optional repository revision, tag, or commit hash.",
    )
    local_files_only: bool = Field(
        default=True,
        description="When true, fail closed to cache-only resolution and never download from the network.",
    )


class ArtifactBridgeResolveResponse(BaseModel):
    object: Literal["artifact_bridge_resolution"] = "artifact_bridge_resolution"
    backend: str
    artifact_backend: str | None = None
    repo_id: str
    filename: str
    revision: str | None = None
    local_files_only: bool
    status: Literal["resolved", "not_cached"]
    cache_root: str | None = None
    auth_env_vars: list[str]
    auth_configured: bool
    auth_env_var_used: str | None = None
    resolved_path: str | None = None


class ChatCompletionToolCallFunction(BaseModel):
    name: str
    arguments: str = Field(
        ...,
        description="JSON-encoded arguments for the function call (a string, per the OpenAI wire shape).",
    )


class ChatCompletionToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ChatCompletionToolCallFunction


class ChatCompletionInputMessage(BaseModel):
    role: Literal["system", "user", "assistant", "developer", "tool"]
    content: str | None = Field(
        default=None,
        description="UTF-8 message content. May be omitted/null on an assistant message that only calls tools.",
    )
    tool_calls: list[ChatCompletionToolCall] | None = Field(
        default=None,
        description="Tool calls requested by a prior assistant turn (assistant role only).",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="The id of the tool call this message answers (tool role only).",
    )
    name: str | None = Field(
        default=None,
        description="Optional participant name, echoed by some clients on any role.",
    )


class ChatCompletionToolFunctionDef(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema object describing the function's parameters.",
    )
    strict: bool | None = None


class ChatCompletionToolDef(BaseModel):
    type: Literal["function"] = "function"
    function: ChatCompletionToolFunctionDef


class ChatCompletionToolChoiceFunctionName(BaseModel):
    name: str


class ChatCompletionNamedToolChoice(BaseModel):
    type: Literal["function"] = "function"
    function: ChatCompletionToolChoiceFunctionName


class ChatCompletionsRequest(BaseModel):
    model: str = Field(
        default="text.tokenizer",
        description="Chat-capable utility model identifier from GET /v1/models.",
    )
    messages: list[ChatCompletionInputMessage] = Field(
        ...,
        min_length=1,
        description="Ordered chat transcript processed by the selected utility model.",
    )
    stream: bool = Field(
        default=False,
        description="When true, return Server-Sent Events with deterministic completion chunks.",
    )
    tools: list[ChatCompletionToolDef] | None = Field(
        default=None,
        description=(
            "Function tools the model may call. Forwarded to provider-backed chat models that "
            "support tool calling, and to algenta_local (rendered into the Qwen3 chat template's "
            "tools preamble); unsupported on the deterministic tokenizer utility model and on an "
            "algenta_local checkpoint with no chat template."
        ),
    )
    tool_choice: Literal["auto", "none", "required"] | ChatCompletionNamedToolChoice | None = Field(
        default=None,
        description=(
            "Controls whether/which tool the model must call. Ignored unless 'tools' is set. "
            "algenta_local supports 'auto' (default) and 'none' only -- its tools preamble is a "
            "hint the model may act on, not a mechanism that can force a call, so 'required' and "
            "a named-function choice are refused (model_capability_unsupported) on that backend."
        ),
    )
    parallel_tool_calls: bool | None = Field(
        default=None,
        description=(
            "Hint to allow/disallow multiple tool calls in one turn. Best-effort: honored where the "
            "provider's API exposes an equivalent knob, otherwise ignored."
        ),
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum tokens to generate. Applies to algenta_local backend models (default 256) "
            "and forwarded providers that accept an output budget; ignored otherwise."
        ),
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Sampling temperature. Applies to algenta_local backend models: 0 or omitted is "
            "greedy (argmax), > 0 draws from the model distribution. Remote providers use their "
            "server-side defaults."
        ),
    )
    top_p: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description=(
            "Nucleus sampling threshold for algenta_local backend models. Remote providers use "
            "their server-side defaults."
        ),
    )
    seed: int | None = Field(
        default=None,
        description=(
            "Sampling seed for algenta_local backend models: same prompt + parameters + seed "
            "reproduce the identical completion. Remote providers use their server-side defaults."
        ),
    )


class ChatCompletionOutputMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ChatCompletionToolCall] | None = Field(
        default=None,
        description="Tool calls the model made this turn, present when finish_reason is 'tool_calls'.",
    )


class ChatCompletionChoice(BaseModel):
    index: int
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter"] = "stop"
    message: ChatCompletionOutputMessage


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ProviderAttemptResponse(BaseModel):
    provider_backend: str
    provider_model_id: str
    outcome: Literal["selected", "failed"]
    error_code: str | None = None


class ChatCompletionsResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    model: str
    provider_backend: str | None = Field(
        default=None,
        description="Concrete provider backend that served this chat completion when routed.",
    )
    provider_model_id: str | None = Field(
        default=None,
        description="Concrete configured provider model that served this chat completion when routed.",
    )
    provider_attempts: list[ProviderAttemptResponse] = Field(
        default_factory=list,
        description="Ordered provider attempts made while serving this chat completion.",
    )
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class CountTokensRequest(BaseModel):
    model: str = Field(
        default="text.tokenizer",
        description="Model identifier from GET /v1/models.",
    )
    input: str = Field(..., description="UTF-8 text to count with the selected tokenizer.")


class CountTokensResponse(BaseModel):
    object: Literal["token_count"] = "token_count"
    model: str
    tokenizer_kind: str
    token_count: int


class EmbeddingsRequest(BaseModel):
    model: str = Field(
        default="text.hash_embedding_v1",
        description="Embedding model identifier from GET /v1/models.",
    )
    input: str | list[str] = Field(
        ...,
        description="One UTF-8 string or a list of UTF-8 strings to embed.",
    )
    dimensions: int = Field(
        default=64,
        gt=0,
        le=4096,
        description="Output embedding dimensionality for the deterministic lexical hash encoder.",
    )


class EmbeddingVectorResponse(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]
    token_count: int


class EmbeddingUsageResponse(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingsResponse(BaseModel):
    object: Literal["list"] = "list"
    model: str
    dimensions: int
    provider_backend: str | None = Field(
        default=None,
        description="Concrete provider backend that served this embeddings request when routed.",
    )
    provider_model_id: str | None = Field(
        default=None,
        description="Concrete configured provider model that served this embeddings request when routed.",
    )
    provider_attempts: list[ProviderAttemptResponse] = Field(
        default_factory=list,
        description="Ordered provider attempts made while serving this embeddings request.",
    )
    data: list[EmbeddingVectorResponse]
    usage: EmbeddingUsageResponse


class ResponseInputTextPart(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class ResponseInputMessageItem(BaseModel):
    type: Literal["message"] = "message"
    role: Literal["user", "assistant", "system", "developer"]
    content: str | list[ResponseInputTextPart] = Field(
        ...,
        description=(
            "Message content: a plain string, or a list of input_text parts (concatenated in "
            "order)."
        ),
    )


class ResponseInputFunctionCallItem(BaseModel):
    type: Literal["function_call"] = "function_call"
    call_id: str = Field(
        ...,
        description="Identifier this call is answered by in a later function_call_output item.",
    )
    name: str
    arguments: str = Field(
        ...,
        description="JSON-encoded call arguments (a string, per the OpenAI wire shape).",
    )


class ResponseInputFunctionCallOutputItem(BaseModel):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str = Field(
        ...,
        description="Matches the call_id of the function_call item this output answers.",
    )
    output: str = Field(
        ...,
        description="The tool's result as a string. JSON-encode structured results yourself.",
    )


class ResponseInputCapabilityApprovalContinuationItem(BaseModel):
    """Track C1 (human-approval pause/resume): resumes a response that paused on
    response.approval_required because its capability-plane execution plan required approval.

    Carries no input of its own -- the plan already carries what was originally proposed (see
    apps.api_server.services.capability_plane._execution._propose_capability_execution). Must be
    the ONLY item in the input array, and previous_response_id must reference the exact paused
    response this plan_id belongs to. A human approves the plan out-of-band first, via the
    separate, credentialed POST /v1/capability-executions/{plan_id}/approve endpoint -- never
    through this item or any other LLM-driven code path.
    """

    type: Literal["capability_approval_continuation"] = "capability_approval_continuation"
    plan_id: str = Field(
        ...,
        description=(
            "The plan_id from a prior response's approval_required pause. Send this only after "
            "a human has approved the plan via POST /v1/capability-executions/{plan_id}/approve."
        ),
    )


ResponseInputItem = Annotated[
    ResponseInputMessageItem
    | ResponseInputFunctionCallItem
    | ResponseInputFunctionCallOutputItem
    | ResponseInputCapabilityApprovalContinuationItem,
    Field(discriminator="type"),
]


class ResponsesRequest(BaseModel):
    model: str = Field(
        default="text.tokenizer",
        description="Utility model identifier from GET /v1/models.",
    )
    input: str | list[str] | list[dict[str, Any]] = Field(
        ...,
        description=(
            "Either the legacy shape -- one UTF-8 string, or a list of UTF-8 strings each "
            "processed as an INDEPENDENT single-turn request against the selected model -- or a "
            "typed OpenResponses-style input array (items shaped "
            "{\"type\": \"message\" | \"function_call\" | \"function_call_output\", ...}) processed "
            "as ONE multi-turn conversation. The two shapes are never mixed: a list is classified "
            "as typed only when every item is an object carrying a \"type\" key, otherwise it is "
            "treated as the legacy list of independent strings."
        ),
    )
    dimensions: int = Field(
        default=64,
        gt=0,
        le=4096,
        description="Embedding dimensions when the selected model generates deterministic embeddings.",
    )
    stream: bool = Field(
        default=False,
        description="When true, return Server-Sent Events with deterministic response output events.",
    )
    tools: list[ChatCompletionToolDef] | None = Field(
        default=None,
        description=(
            "Function tools the model may call. Forwarded to provider-backed chat models that "
            "support tool calling, and to algenta_local (rendered into the Qwen3 chat template's "
            "tools preamble); unsupported on the deterministic tokenizer utility model and on an "
            "algenta_local checkpoint with no chat template."
        ),
    )
    tool_choice: Literal["auto", "none", "required"] | ChatCompletionNamedToolChoice | None = Field(
        default=None,
        description=(
            "Controls whether/which tool the model must call. Ignored unless 'tools' is set. "
            "algenta_local supports 'auto' (default) and 'none' only -- its tools preamble is a "
            "hint the model may act on, not a mechanism that can force a call, so 'required' and "
            "a named-function choice are refused (model_capability_unsupported) on that backend."
        ),
    )
    parallel_tool_calls: bool | None = Field(
        default=None,
        description=(
            "Hint to allow/disallow multiple tool calls in one turn. Best-effort: honored where the "
            "provider's API exposes an equivalent knob, otherwise ignored."
        ),
    )
    previous_response_id: str | None = Field(
        default=None,
        description=(
            "Continue a prior typed-input-array conversation: the id of an earlier /v1/responses "
            "call whose message history (including any tool calls/results) is prepended before "
            "this call's input items. Only valid together with the typed input-array shape. "
            "LIMITATION: this history is held in the serving process's memory only -- it does not "
            "survive a process restart and will not be found if a later request lands on a "
            "different worker/replica than the one that served the original call."
        ),
    )
    execute_capability_tools: bool = Field(
        default=False,
        description=(
            "Track C1 (human-approval pause/resume), OPT-IN and OFF by default. When true, a "
            "model tool call in the typed-input-array conversation path whose name resolves to a "
            "capability in this org's own GET /v1/capabilities catalog is executed server-side "
            "(via the same execute_capability_service that POST /v1/capabilities/execute calls) "
            "instead of being returned as an inert tool_call for the caller to run themselves. A "
            "capability whose catalog entry sets approval_required=True pauses the response "
            "instead of executing (status='approval_required', see ResponsesResponse."
            "approval_required) until a human approves the pending plan through the separate, "
            "credentialed POST /v1/capability-executions/{plan_id}/approve endpoint -- this "
            "option can never approve a plan itself. Resume the paused response with "
            "previous_response_id set to it and a single "
            "{type: capability_approval_continuation, plan_id: ...} input item. Default false "
            "means zero behavior change for every existing caller."
        ),
    )


class ResponseOutputContent(BaseModel):
    type: Literal["tokenization", "embedding", "text"]
    text: str | None = None
    tokens: list[str] | None = None
    token_count: int
    embedding: list[float] | None = None
    tool_calls: list[ChatCompletionToolCall] | None = Field(
        default=None,
        description="Tool calls the model made this turn, present when finish_reason is 'tool_calls'.",
    )
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter"] | None = Field(
        default=None,
        description=(
            "Present for chat/provider-backed text turns; mirrors Chat Completions' finish_reason. "
            "Null for tokenization/embedding output, where the concept does not apply."
        ),
    )
    capability_id: str | None = Field(
        default=None,
        description=(
            "Track C1: set only when execute_capability_tools=True resolved this item's tool "
            "call to a real capability in the org's own catalog. Omitted from the response "
            "entirely for every existing caller (execute_capability_tools defaults to False) --"
            " see this model's _serialize_omitting_unset_capability_fields."
        ),
    )
    capability_status: Literal["succeeded", "failed", "approval_required"] | None = Field(
        default=None,
        description=(
            "Outcome of the server-side capability execution this tool call was routed to. "
            "Omitted unless capability_id is set."
        ),
    )
    capability_output: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The capability's real output (CapabilityExecutionResponse.output) when "
            "capability_status == 'succeeded'. Omitted otherwise."
        ),
    )
    capability_error: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The capability's real error (CapabilityExecutionResponse.error) when "
            "capability_status == 'failed'. Omitted otherwise."
        ),
    )

    @model_serializer(mode="wrap")
    def _serialize_omitting_unset_capability_fields(self, handler: object):
        """Track A5 "additive fields only" discipline, made airtight: these four Track C1 fields
        are entirely ABSENT from the wire shape (not merely null) whenever unset, so every
        existing caller -- everyone who never sets execute_capability_tools=True, which is the
        overwhelming default -- gets a byte-identical response to before this change existed.
        Proven by tests/test_llm_api_router_responses_route.py, run completely unmodified.
        Every OTHER optional field on this model (tokens, embedding, tool_calls, finish_reason,
        ...) keeps its pre-existing behavior of always serializing, null or not -- only these
        four brand-new fields get this treatment.

        Deliberately UNANNOTATED return type: a `-> dict[str, Any]` annotation here makes
        pydantic advertise this model's *entire* OpenAPI/JSON schema as a bare
        `{type: object, additionalProperties: true}` blob (it takes the wrap-serializer's return
        annotation as gospel for schema generation and discards the field-level schema below) --
        confirmed by direct comparison of this model's own __pydantic_core_schema__ with/without
        the annotation. Leaving the return type off keeps the full per-field schema in
        schemas/openapi/openapi.yaml with zero change to runtime behavior (Python never enforces
        return annotations)."""
        data = handler(self)  # type: ignore[operator]
        for key in ("capability_id", "capability_status", "capability_output", "capability_error"):
            if getattr(self, key) is None:
                data.pop(key, None)
        return data


class ResponseOutputItem(BaseModel):
    id: str
    object: Literal["response.output"] = "response.output"
    index: int
    provider_backend: str | None = Field(
        default=None,
        description="Concrete provider backend that served this output item when routed.",
    )
    provider_model_id: str | None = Field(
        default=None,
        description="Concrete configured provider model that served this output item when routed.",
    )
    provider_attempts: list[ProviderAttemptResponse] = Field(
        default_factory=list,
        description="Ordered provider attempts made while serving this output item.",
    )
    content: list[ResponseOutputContent]


class ResponseCapabilityApproval(BaseModel):
    """Track C1 (human-approval pause/resume): mirrors CapabilityExecutionResponse's own
    plan_id/plan_hash pair for the capability-plane execution plan this response is paused on.
    Approval happens ONLY through the separate, credentialed POST
    /v1/capability-executions/{plan_id}/approve endpoint -- never through this response, this
    request, or any other LLM/MCP-driven code path."""

    plan_id: str
    plan_hash: str
    message: str = Field(
        ...,
        description="Human-facing instructions for approving and then resuming this response.",
    )


class ResponsesResponse(BaseModel):
    id: str
    object: Literal["response"] = "response"
    status: Literal["completed", "approval_required"] = "completed"
    model: str
    provider_backend: str | None = Field(
        default=None,
        description="Concrete provider backend that served this response when routed uniformly.",
    )
    provider_model_id: str | None = Field(
        default=None,
        description="Concrete configured provider model that served this response when routed uniformly.",
    )
    provider_attempts: list[ProviderAttemptResponse] = Field(
        default_factory=list,
        description="Ordered provider attempts shared by every output item when routed uniformly.",
    )
    output: list[ResponseOutputItem]
    usage: EmbeddingUsageResponse
    approval_required: ResponseCapabilityApproval | None = Field(
        default=None,
        description=(
            "Track C1: set only when status == 'approval_required' -- this response is paused "
            "awaiting a human's decision on a pending capability_plane execution plan. Omitted "
            "from the response entirely (not merely null) for every existing caller "
            "(execute_capability_tools defaults to False)."
        ),
    )

    @model_serializer(mode="wrap")
    def _serialize_omitting_unset_approval_required(self, handler: object):
        """Same byte-identical-for-existing-callers guarantee as ResponseOutputContent's own
        serializer above, for this one brand-new top-level field. Also deliberately
        UNANNOTATED return type -- see _serialize_omitting_unset_capability_fields's docstring
        for why: a `-> dict[str, Any]` annotation collapses this model's OpenAPI schema to a
        bare additionalProperties blob."""
        data = handler(self)  # type: ignore[operator]
        if self.approval_required is None:
            data.pop("approval_required", None)
        return data


class EmbeddingSimilarityRequest(BaseModel):
    model: str = Field(
        default="embeddings.cosine_similarity",
        description="Similarity model identifier from GET /v1/models.",
    )
    left: list[float] = Field(
        ...,
        min_length=1,
        description="First embedding vector.",
    )
    right: list[float] = Field(
        ...,
        min_length=1,
        description="Second embedding vector.",
    )


class EmbeddingSimilarityResponse(BaseModel):
    object: Literal["embedding_similarity"] = "embedding_similarity"
    model: str
    similarity_metric: str
    score: float
    dimension: int


class RerankDocumentInput(BaseModel):
    id: str = Field(..., description="Stable document identifier for the returned ranking row.")
    embedding: list[float] = Field(
        ...,
        min_length=1,
        description="Precomputed embedding vector for the candidate document.",
    )
    text: str | None = Field(
        default=None,
        description="Optional raw document text returned unchanged in the ranking output.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured document metadata returned unchanged in the ranking output.",
    )


class RerankRequest(BaseModel):
    model: str = Field(
        default="embeddings.cosine_similarity",
        description="Reranking model identifier from GET /v1/models.",
    )
    query_embedding: list[float] = Field(
        ...,
        min_length=1,
        description="Precomputed query embedding vector.",
    )
    documents: list[RerankDocumentInput] = Field(
        ...,
        min_length=1,
        description="Candidate documents with caller-supplied embeddings.",
    )
    top_n: int | None = Field(
        default=None,
        gt=0,
        description="Optional number of ranked documents to return. Defaults to all documents.",
    )


class RerankResult(BaseModel):
    object: Literal["rerank_result"] = "rerank_result"
    id: str
    index: int
    rank: int
    score: float
    text: str | None = None
    metadata: dict[str, Any] | None = None


class RerankResponse(BaseModel):
    object: Literal["list"] = "list"
    model: str
    similarity_metric: str
    total_documents: int
    returned_documents: int
    data: list[RerankResult]
