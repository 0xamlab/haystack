from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, TypeAdapter, ValidationError

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org, get_redis, require_verified_email
from apps.api_server.middleware.tenant_key_binding import bind_tenant_keys
from apps.api_server.schemas.llm import (
    ArtifactBridgeResolveRequest,
    ArtifactBridgeResolveResponse,
    ChatCompletionsRequest,
    ChatCompletionsResponse,
    ChatCompletionChoice,
    ChatCompletionInputMessage,
    ChatCompletionOutputMessage,
    ChatCompletionToolCall,
    ChatCompletionUsage,
    CountTokensRequest,
    CountTokensResponse,
    EmbeddingsRequest,
    EmbeddingsResponse,
    EmbeddingUsageResponse,
    EmbeddingVectorResponse,
    EmbeddingSimilarityRequest,
    EmbeddingSimilarityResponse,
    LLMModelListResponse,
    LLMModelResponse,
    ProviderAttemptResponse,
    ResponseCapabilityApproval,
    ResponseInputCapabilityApprovalContinuationItem,
    ResponseInputItem,
    ResponseOutputContent,
    ResponseOutputItem,
    RerankRequest,
    RerankResponse,
    RerankResult,
    ResponsesRequest,
    ResponsesResponse,
    TokenizeRequest,
    TokenizeResponse,
)
from apps.api_server.services import llm_provider_service
from apps.api_server.services.llm_provider_service import _features as llm_streaming_features
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.capability_plane import (
    CapabilityExecutionRequest,
    CapabilityPlaneError,
    ExecutionSessionStatus,
    execute_capability_service,
    list_capabilities_service,
)
from apps.api_server.services.llm_api_service import (
    create_chat_completion,
    resolve_artifact_bridge,
    LLMAPIError,
    clear_pending_capability_approval,
    count_text_tokens,
    create_text_embeddings,
    create_utility_conversation_response,
    create_utility_response,
    embedding_similarity_score,
    finalize_capability_approval_conversation,
    list_llm_model_descriptors,
    list_provider_discovered_descriptors,
    load_pending_capability_approval,
    rerank_embeddings,
    store_pending_capability_approval,
    tokenize_text,
)
from apps.api_server.services.quota_service import check_rate_limit
from apps.runtime.mojo_library_runner import MojoLibraryError

# B10 PR11: bind the authenticated org's per-tenant provider key for every handler in this router
# (all routes are auth-gated), so resolve_provider_api_key sees the org override in-request.
router = APIRouter(
    tags=["LLM API"],
    dependencies=[Depends(require_verified_email), Depends(bind_tenant_keys)],
)

_STREAM_CHUNK_SIZE = 24


async def _enforce_llm_api_rate_limit(
    *,
    request: Request,
    auth: AuthContext,
    redis_client: object,
) -> None:
    await check_rate_limit(
        auth["org_id"],
        auth["plan"],
        redis_client,
        request_state=request.state,
    )


def _llm_api_http_exception(exc: Exception, request: Request) -> HTTPException:
    if isinstance(exc, LLMAPIError):
        if exc.code == "model_not_supported":
            status_code = 404
        elif exc.code == "artifact_not_found":
            status_code = 404
        elif exc.code == "previous_response_id_not_found":
            status_code = 404
        elif exc.code == "payment_required":  # managed-LLM monthly spend cap reached (D3)
            status_code = 402
        elif exc.code in {
            "model_capability_unsupported",
            "invalid_embedding_dimensions",
            "invalid_provider_request",
        }:
            status_code = 422
        elif exc.code == "provider_rate_limited":
            status_code = 429
        elif exc.code in {"backend_unavailable", "artifact_bridge_backend_unavailable"}:
            status_code = 503
        elif exc.code == "provider_timeout":
            status_code = 504
        else:
            status_code = 502
        return HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details or {},
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    if exc.code in {"module_not_registered", "function_not_registered"}:
        status_code = 404
    elif exc.code == "invalid_arguments":
        status_code = 422
    elif exc.code == "compute_runtime_unavailable":
        status_code = 503
    elif exc.code == "mojo_library_timeout":
        status_code = 504
    else:
        status_code = 502
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def _sse_data(payload: object) -> str:
    if payload == "[DONE]":
        return "data: [DONE]\n\n"
    return f"data: {json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}\n\n"


def _stream_text_chunks(text: str, *, chunk_size: int = _STREAM_CHUNK_SIZE) -> list[str]:
    if not text:
        return []
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def _response_output_item_payload(
    *,
    response_id: str,
    item: ResponseOutputItem,
) -> dict[str, object]:
    return {
        "id": item.id,
        "object": item.object,
        "index": item.index,
        "provider_backend": item.provider_backend,
        "provider_model_id": item.provider_model_id,
        "provider_attempts": [attempt.model_dump(mode="json") for attempt in item.provider_attempts],
        "content": [content.model_dump(mode="json") for content in item.content],
        "response_id": response_id,
    }


def _unique_provider_metadata(
    providers: list[tuple[str, str] | None],
) -> tuple[str | None, str | None]:
    unique = {provider for provider in providers if provider is not None}
    if len(unique) != 1:
        return None, None
    return next(iter(unique))


def _provider_attempts_payload(
    attempts: tuple[object, ...] | list[object],
) -> list[ProviderAttemptResponse]:
    payload: list[ProviderAttemptResponse] = []
    for attempt in attempts:
        provider_backend = getattr(attempt, "provider_backend", None)
        provider_model_id = getattr(attempt, "provider_model_id", None)
        outcome = getattr(attempt, "outcome", None)
        error_code = getattr(attempt, "error_code", None)
        if not isinstance(provider_backend, str) or not provider_backend:
            continue
        if not isinstance(provider_model_id, str) or not provider_model_id:
            continue
        if outcome not in {"selected", "failed"}:
            continue
        payload.append(
            ProviderAttemptResponse(
                provider_backend=provider_backend,
                provider_model_id=provider_model_id,
                outcome=outcome,
                error_code=error_code if isinstance(error_code, str) and error_code else None,
            )
        )
    return payload


def _unique_provider_attempts(
    attempts: list[list[ProviderAttemptResponse]],
) -> list[ProviderAttemptResponse]:
    if not attempts:
        return []
    signature = [
        (
            item.provider_backend,
            item.provider_model_id,
            item.outcome,
            item.error_code,
        )
        for item in attempts[0]
    ]
    for attempt_list in attempts[1:]:
        if [
            (
                item.provider_backend,
                item.provider_model_id,
                item.outcome,
                item.error_code,
            )
            for item in attempt_list
        ] != signature:
            return []
    return attempts[0]


async def _chat_completion_stream(
    *,
    completion_id: str,
    model_id: str,
    content: str,
    provider_backend: str | None,
    provider_model_id: str | None,
    provider_attempts: list[ProviderAttemptResponse],
) -> AsyncIterator[str]:
    yield _sse_data(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": model_id,
            "provider_backend": provider_backend,
            "provider_model_id": provider_model_id,
            "provider_attempts": [item.model_dump(mode="json") for item in provider_attempts],
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
    )
    for chunk in _stream_text_chunks(content):
        yield _sse_data(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "model": model_id,
                "provider_backend": provider_backend,
                "provider_model_id": provider_model_id,
                "provider_attempts": [item.model_dump(mode="json") for item in provider_attempts],
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
            }
        )
    yield _sse_data(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": model_id,
            "provider_backend": provider_backend,
            "provider_model_id": provider_model_id,
            "provider_attempts": [item.model_dump(mode="json") for item in provider_attempts],
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield _sse_data("[DONE]")


# ─── Track C2 (real per-backend streaming, 2026-08) ────────────────────────────────────────────
#
# Real passthrough streaming activates only when the request carries no `tools` -- a model can
# only ever emit tool_calls when `tools` was set, so gating on its absence means the "streaming +
# tool_calls" combination this router still refuses below (see chat_completions()) can never
# actually arise through this path; it keeps that existing, tested contract intact while adding
# real incremental delivery for the common (no-tool-calling) case. The per-backend normalizers
# already parse tool-call deltas correctly (see _streaming.py + its golden-fixture tests) so
# wiring streamed tool-calls end-to-end through this router is a natural, self-contained
# follow-up, not a rewrite.


def _serialize_chat_completion_messages(
    messages: list[ChatCompletionInputMessage],
) -> list[dict[str, object]]:
    return [
        {
            "role": message.role,
            "content": message.content,
            **(
                {"tool_calls": [tc.model_dump(exclude_none=True) for tc in message.tool_calls]}
                if message.tool_calls
                else {}
            ),
            **({"tool_call_id": message.tool_call_id} if message.tool_call_id else {}),
            **({"name": message.name} if message.name else {}),
        }
        for message in messages
    ]


def _passthrough_stream_event_delta(event: dict[str, object]) -> dict[str, object] | None:
    delta: dict[str, object] = {}
    content = event.get("content")
    if content:
        delta["content"] = content
    tool_calls = event.get("tool_calls")
    if tool_calls:
        delta["tool_calls"] = tool_calls
    return delta or None


async def _chat_completion_stream_passthrough(
    *,
    completion_id: str,
    model_id: str,
    provider_backend: str,
    provider_model_id: str,
    provider_attempts: list[ProviderAttemptResponse],
    first_event: dict[str, object] | None,
    remaining_events: AsyncIterator[dict[str, object]],
) -> AsyncIterator[str]:
    """Real counterpart to _chat_completion_stream: consumes the already-primed normalized event
    stream directly (see _passthrough_chat_completion_stream_response) instead of slicing a fully
    generated string. Emits the EXACT SAME three-phase SSE framing (role-announce chunk, N
    content/tool_call delta chunks, terminal finish_reason chunk, [DONE]) so existing consumers
    see no format change -- only real incremental timing."""
    provider_attempts_payload = [item.model_dump(mode="json") for item in provider_attempts]
    yield _sse_data(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": model_id,
            "provider_backend": provider_backend,
            "provider_model_id": provider_model_id,
            "provider_attempts": provider_attempts_payload,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
    )

    finish_reason = "stop"

    async def _events() -> AsyncIterator[dict[str, object]]:
        if first_event is not None:
            yield first_event
        async for event in remaining_events:
            yield event

    async for event in _events():
        event_finish_reason = event.get("finish_reason")
        if event_finish_reason:
            finish_reason = event_finish_reason
        delta = _passthrough_stream_event_delta(event)
        if delta:
            yield _sse_data(
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "model": model_id,
                    "provider_backend": provider_backend,
                    "provider_model_id": provider_model_id,
                    "provider_attempts": provider_attempts_payload,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                }
            )

    yield _sse_data(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": model_id,
            "provider_backend": provider_backend,
            "provider_model_id": provider_model_id,
            "provider_attempts": provider_attempts_payload,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
        }
    )
    yield _sse_data("[DONE]")


async def _passthrough_chat_completion_stream_response(
    *,
    payload: ChatCompletionsRequest,
    request: Request,
) -> StreamingResponse:
    """Resolves the model's real streaming target, opens the real upstream connection, and PRIMES
    it (awaits the first normalized event) before ever constructing the StreamingResponse -- so a
    pre-stream failure (bad config, auth rejected, egress denied, immediate non-2xx status)
    surfaces as a normal JSON error with the correct HTTP status code, exactly like the
    non-streaming path, instead of a broken/truncated SSE response. Only a genuine failure that
    happens AFTER the connection is already open and producing chunks ends the SSE stream early."""
    messages = _serialize_chat_completion_messages(payload.messages)
    try:
        target_config, event_stream = (
            await llm_provider_service.routed_provider_chat_completion_stream(
                model_id=payload.model,
                messages=messages,
                max_output_tokens=payload.max_tokens,
            )
        )
        event_iterator = event_stream.__aiter__()
        try:
            first_event: dict[str, object] | None = await event_iterator.__anext__()
        except StopAsyncIteration:
            first_event = None
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc

    completion_id = (
        (first_event.get("id") if first_event else None)
        or f"chatcmpl_stream_{uuid.uuid4().hex}"
    )
    provider_attempts = [
        ProviderAttemptResponse(
            provider_backend=target_config.backend,
            provider_model_id=target_config.model_id,
            outcome="selected",
            error_code=None,
        )
    ]
    return StreamingResponse(
        _chat_completion_stream_passthrough(
            completion_id=str(completion_id),
            model_id=payload.model,
            provider_backend=target_config.backend,
            provider_model_id=target_config.model_id,
            provider_attempts=provider_attempts,
            first_event=first_event,
            remaining_events=event_iterator,
        ),
        media_type="text/event-stream",
    )


async def _responses_stream(
    *,
    response_id: str,
    model_id: str,
    items: list[ResponseOutputItem],
    usage: EmbeddingUsageResponse,
    provider_backend: str | None,
    provider_model_id: str | None,
    provider_attempts: list[ProviderAttemptResponse],
    approval: ResponseCapabilityApproval | None = None,
) -> AsyncIterator[str]:
    # Scope note (Track C2, 2026-08): /v1/responses stream=true stays on this SAME
    # buffered-then-chunked path unconditionally -- including for a model whose
    # /v1/chat/completions requests now get REAL passthrough streaming (see
    # _passthrough_chat_completion_stream_response above). Its event vocabulary
    # (response.created/response.output_item.done/response.completed) is structurally
    # different from chat.completion.chunk, it can legally emit MULTIPLE independent completions
    # per legacy list input, and it has no per-backend normalizer of its own -- wiring real
    # streaming through it is a deliberately separate, later piece of work, not attempted here.
    # GET /v1/models' streaming_mode flag describes chat-completions streaming capability only;
    # it is not a claim about this endpoint.
    #
    # Design note (Track C1a): a tool-call output item flows through the SAME
    # "response.output_item.done" event as any other finished item, with tool_calls/finish_reason
    # populated on its content -- there is no separate "response.function_call.done"-style event.
    # This is the simplest option consistent with the existing 3-event vocabulary: that event
    # already means "an item finished", and a tool-call item IS a finished item, just like Chat
    # Completions' own non-streaming tool-calls response reuses the ordinary completion envelope
    # rather than a parallel shape. In practice this path is also never exercised by a real SSE
    # stream yet: stream=true with tool_calls present is refused before this generator ever runs
    # (matching Track C2's identical restriction on /v1/chat/completions), so this is documented
    # forward-compatibility rather than a live combination.

    yield _sse_data(
        {
            "type": "response.created",
            "response": {
                "id": response_id,
                "object": "response",
                "status": "in_progress",
                "model": model_id,
                "provider_backend": provider_backend,
                "provider_model_id": provider_model_id,
                "provider_attempts": [item.model_dump(mode="json") for item in provider_attempts],
            },
        }
    )
    if approval is not None:
        # Track C1 (human-approval pause/resume): "response.approval_required" is the first new
        # distinct SSE event type since the original 3. Documented forward-compatibility ONLY,
        # exactly like the tool_calls note above -- stream=true combined with a capability call
        # that resolves to approval_required is refused (model_capability_unsupported) before
        # this generator ever runs, so this branch is not reachable through the live router
        # today. It still ends the stream cleanly: no fake response.completed follows a pause.
        yield _sse_data(
            {
                "type": "response.approval_required",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "status": "approval_required",
                    "model": model_id,
                    "plan_id": approval.plan_id,
                    "plan_hash": approval.plan_hash,
                    "message": approval.message,
                },
            }
        )
        yield _sse_data("[DONE]")
        return
    for item in items:
        yield _sse_data(
            {
                "type": "response.output_item.done",
                "output_index": item.index,
                "item": _response_output_item_payload(response_id=response_id, item=item),
            }
        )
    yield _sse_data(
        {
            "type": "response.completed",
            "response": {
                "id": response_id,
                "object": "response",
                "status": "completed",
                "model": model_id,
                "provider_backend": provider_backend,
                "provider_model_id": provider_model_id,
                "provider_attempts": [item.model_dump(mode="json") for item in provider_attempts],
                "usage": usage.model_dump(mode="json"),
            },
        }
    )
    yield _sse_data("[DONE]")


@router.get(
    "/v1/models",
    response_model=LLMModelListResponse,
    summary="List currently supported LLM utility models",
    description=(
        "Returns the truthful, currently executable Algenta LLM model catalog. "
        "Only runtime-backed or explicitly configured provider-backed models are advertised."
    ),
)
async def list_models(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> LLMModelListResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    # Static runtime/provider catalog + LIVE per-provider discovery (model_name "*" entries expand into
    # the models each backend currently offers, queried from its list-models API — never a stale hardcoded list).
    descriptors = list(list_llm_model_descriptors()) + list(await list_provider_discovered_descriptors())
    return LLMModelListResponse(
        data=[
            LLMModelResponse(
                id=descriptor.model_id,
                runtime_module=descriptor.runtime_module,
                description=descriptor.description,
                capabilities=list(descriptor.capabilities),
                supported_endpoints=list(descriptor.supported_endpoints),
                runtime_functions=list(descriptor.runtime_functions),
                tokenizer_kind=descriptor.tokenizer_kind,
                similarity_metric=descriptor.similarity_metric,
                provider_backend=descriptor.provider_backend,
                routing_targets=list(descriptor.routing_targets),
                resolved_routing_targets=list(descriptor.resolved_routing_targets),
                chat_routing_targets=list(descriptor.chat_routing_targets),
                resolved_chat_routing_targets=list(descriptor.resolved_chat_routing_targets),
                embedding_routing_targets=list(descriptor.embedding_routing_targets),
                resolved_embedding_routing_targets=list(
                    descriptor.resolved_embedding_routing_targets
                ),
                routing_fallback_policy=descriptor.routing_fallback_policy,
                chat_routing_fallback_policy=descriptor.chat_routing_fallback_policy,
                embedding_routing_fallback_policy=descriptor.embedding_routing_fallback_policy,
                routing_fallback_on=list(descriptor.routing_fallback_on),
                chat_routing_fallback_on=list(descriptor.chat_routing_fallback_on),
                embedding_routing_fallback_on=list(descriptor.embedding_routing_fallback_on),
                routing_max_attempts=descriptor.routing_max_attempts,
                chat_routing_max_attempts=descriptor.chat_routing_max_attempts,
                embedding_routing_max_attempts=descriptor.embedding_routing_max_attempts,
                timeout_seconds=descriptor.timeout_seconds,
                chat_timeout_seconds=descriptor.chat_timeout_seconds,
                embedding_timeout_seconds=descriptor.embedding_timeout_seconds,
                required_provider_headers=list(descriptor.required_provider_headers),
                chat_required_provider_headers=list(descriptor.chat_required_provider_headers),
                embedding_required_provider_headers=list(
                    descriptor.embedding_required_provider_headers
                ),
                provider_auth_env_vars=list(descriptor.provider_auth_env_vars),
                chat_provider_auth_env_vars=list(descriptor.chat_provider_auth_env_vars),
                embedding_provider_auth_env_vars=list(
                    descriptor.embedding_provider_auth_env_vars
                ),
                provider_auth_configured=descriptor.provider_auth_configured,
                chat_provider_auth_configured=descriptor.chat_provider_auth_configured,
                embedding_provider_auth_configured=descriptor.embedding_provider_auth_configured,
                bridge_cache_root=descriptor.bridge_cache_root,
                bridge_auth_env_vars=list(descriptor.bridge_auth_env_vars),
                bridge_auth_configured=descriptor.bridge_auth_configured,
                bridge_tokenizer_backends=list(descriptor.bridge_tokenizer_backends),
                bridge_artifact_backends=list(descriptor.bridge_artifact_backends),
                streaming_mode=descriptor.streaming_mode,
                supported_parameters=list(descriptor.supported_parameters),
                available=descriptor.available,
            )
            for descriptor in descriptors
        ]
    )


@router.post(
    "/v1/artifacts/resolve",
    response_model=ArtifactBridgeResolveResponse,
    summary="Resolve a Hugging Face artifact through the Algenta artifact bridge",
    description=(
        "Resolves a Hugging Face artifact path through the compatibility-ring artifact bridge. "
        "The default behavior is cache-only and never downloads from the network unless the "
        "caller explicitly sets local_files_only=false."
    ),
)
async def resolve_artifact(
    payload: ArtifactBridgeResolveRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> ArtifactBridgeResolveResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    try:
        resolution = resolve_artifact_bridge(
            repo_id=payload.repo_id,
            filename=payload.filename,
            revision=payload.revision,
            local_files_only=payload.local_files_only,
        )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    return ArtifactBridgeResolveResponse(
        backend=resolution.backend,
        artifact_backend=resolution.artifact_backend,
        repo_id=resolution.repo_id,
        filename=resolution.filename,
        revision=resolution.revision,
        local_files_only=resolution.local_files_only,
        status=resolution.status,
        cache_root=resolution.cache_root,
        auth_env_vars=list(resolution.auth_env_vars),
        auth_configured=resolution.auth_configured,
        auth_env_var_used=resolution.auth_env_var_used,
        resolved_path=resolution.resolved_path,
    )


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionsResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "JSON chat completion by default, or Server-Sent Events chunks when stream=true."
            ),
        }
    },
    summary="Run deterministic utility chat completion",
    description=(
        "Runs the selected model over a chat transcript and returns an assistant message. "
        "Tokenizer-backed utility chat remains deterministic, while configured provider-backed "
        "models are routed through the provider service when advertised in GET /v1/models."
    ),
)
async def chat_completions(
    payload: ChatCompletionsRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> ChatCompletionsResponse | StreamingResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    # Track C2 (real per-backend streaming, 2026-08): a streaming request with no tools, against
    # a model whose real, resolved backend has a real per-backend SSE normalizer, gets REAL
    # incremental streaming -- the upstream's own bytes are parsed and forwarded chunk-by-chunk as
    # they arrive, never buffered first. See the "Track C2" comment above
    # _chat_completion_stream_passthrough for why this is gated on "no tools".
    if payload.stream and not payload.tools:
        streaming_mode = llm_streaming_features.resolved_streaming_mode_for_model(payload.model)
        if streaming_mode == "passthrough":
            return await _passthrough_chat_completion_stream_response(
                payload=payload,
                request=request,
            )
    # Track C2 (2026-08): non-streaming tool calling. tools/tool_choice/parallel_tool_calls are
    # forwarded ONLY when the caller actually set them, so every existing call site downstream
    # (including test doubles that monkeypatch create_chat_completion with a fixed signature)
    # keeps working unchanged when a request never mentions tools.
    _tool_kwargs: dict[str, object] = {}
    if payload.tools:
        _tool_kwargs["tools"] = [tool.model_dump(exclude_none=True) for tool in payload.tools]
    if payload.tool_choice is not None:
        _tool_kwargs["tool_choice"] = (
            payload.tool_choice.model_dump(exclude_none=True)
            if isinstance(payload.tool_choice, BaseModel)
            else payload.tool_choice
        )
    if payload.parallel_tool_calls is not None:
        _tool_kwargs["parallel_tool_calls"] = payload.parallel_tool_calls
    try:
        descriptor, completion = await create_chat_completion(
            model_id=payload.model,
            messages=_serialize_chat_completion_messages(payload.messages),
            max_output_tokens=payload.max_tokens,
            temperature=payload.temperature,
            top_p=payload.top_p,
            seed=payload.seed,
            **_tool_kwargs,
        )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    # getattr(..., default): existing test doubles for create_chat_completion predate tool-calling
    # and return a SimpleNamespace without these two fields -- the real ChatCompletionResult
    # dataclass always has them (default finish_reason="stop", tool_calls=None).
    completion_tool_calls = getattr(completion, "tool_calls", None)
    completion_finish_reason = getattr(completion, "finish_reason", "stop")
    if payload.stream and completion_tool_calls:
        # True per-backend streaming of tool_calls deltas is a deliberately separate follow-up
        # (Track C2 scope is non-streaming tool calling only) -- refuse rather than silently
        # dropping the tool_calls the caller asked for into an SSE stream that can't carry them.
        raise _llm_api_http_exception(
            LLMAPIError(
                "model_capability_unsupported",
                "Streaming is not yet supported for a completion that calls tools; set stream=false.",
                {"model": descriptor.model_id, "required_capability": "streaming_tool_calls"},
            ),
            request,
        )
    response_tool_calls = (
        [
            ChatCompletionToolCall(
                id=tool_call.id,
                type="function",
                function={
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            )
            for tool_call in completion_tool_calls
        ]
        if completion_tool_calls
        else None
    )
    response = ChatCompletionsResponse(
        id=completion.completion_id,
        model=descriptor.model_id,
        provider_backend=completion.provider.provider_backend if completion.provider is not None else None,
        provider_model_id=completion.provider.provider_model_id if completion.provider is not None else None,
        provider_attempts=_provider_attempts_payload(completion.provider_attempts),
        choices=[
            ChatCompletionChoice(
                index=0,
                finish_reason=completion_finish_reason,
                message=ChatCompletionOutputMessage(
                    content=completion.content,
                    tool_calls=response_tool_calls,
                ),
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            total_tokens=completion.prompt_tokens + completion.completion_tokens,
        ),
    )
    if payload.stream:
        return StreamingResponse(
            _chat_completion_stream(
                completion_id=completion.completion_id,
                model_id=descriptor.model_id,
                content=completion.content or "",
                provider_backend=response.provider_backend,
                provider_model_id=response.provider_model_id,
                provider_attempts=response.provider_attempts,
            ),
            media_type="text/event-stream",
        )
    return response


@router.post(
    "/v1/tokenize",
    response_model=TokenizeResponse,
    summary="Tokenize text with a supported Algenta tokenizer model",
    description=(
        "Runs the selected tokenizer model and returns the produced tokens. "
        "This initial LLM API tranche currently exposes deterministic word tokenization."
    ),
)
async def tokenize(
    payload: TokenizeRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> TokenizeResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    try:
        descriptor, tokens = await tokenize_text(model_id=payload.model, text=payload.input)
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    return TokenizeResponse(
        model=descriptor.model_id,
        tokenizer_kind=descriptor.tokenizer_kind or "unknown",
        tokens=tokens,
        token_count=len(tokens),
    )


@router.post(
    "/v1/count_tokens",
    response_model=CountTokensResponse,
    summary="Count tokens with a supported Algenta tokenizer model",
    description=(
        "Runs the selected tokenizer model and returns the deterministic token count."
    ),
)
async def count_tokens(
    payload: CountTokensRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> CountTokensResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    try:
        descriptor, token_count = await count_text_tokens(model_id=payload.model, text=payload.input)
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    return CountTokensResponse(
        model=descriptor.model_id,
        tokenizer_kind=descriptor.tokenizer_kind or "unknown",
        token_count=token_count,
    )


_RESPONSE_INPUT_ITEMS_ADAPTER: TypeAdapter[list[ResponseInputItem]] = TypeAdapter(
    list[ResponseInputItem]
)


def _is_typed_response_input(raw_input: object) -> bool:
    # A list of dicts can only ever be an attempt at the typed OpenResponses input-array shape --
    # the legacy shape is str | list[str], and a dict item never validates as a str. Whether each
    # dict actually carries a well-formed "type" (message/function_call/function_call_output) is
    # then checked precisely by _RESPONSE_INPUT_ITEMS_ADAPTER, which raises a clean, specific
    # validation error rather than this classifier silently guessing wrong.
    return isinstance(raw_input, list) and len(raw_input) > 0 and isinstance(raw_input[0], dict)


def _response_output_tool_calls(
    tool_calls: object,
) -> list[ChatCompletionToolCall] | None:
    if not tool_calls:
        return None
    return [
        ChatCompletionToolCall(
            id=tool_call.id,
            type="function",
            function={
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
        )
        for tool_call in tool_calls
    ]


# ── Track C1 (human-approval pause/resume) ─────────────────────────────────────────────────
#
# execute_capability_tools=True (opt-in, default False -- zero behavior change otherwise) lets
# /v1/responses execute a model tool call server-side when its name resolves to a capability in
# the org's OWN capability_plane catalog, by calling execute_capability_service directly -- the
# SAME Python function POST /v1/capabilities/execute calls (never an internal HTTP round-trip,
# never a re-implementation of catalog listing/execution). This reuses Track C1b's existing,
# already-tested approval gate verbatim:
#   - approval_required=False capabilities execute immediately (the common case).
#   - approval_required=True capabilities pause on response.approval_required with a real
#     plan_id/plan_hash, exactly like calling POST /v1/capabilities/execute directly would.
#   - HARD SECURITY INVARIANT: nothing below ever calls the capability_plane approval service
#     function that backs POST /v1/capability-executions/{plan_id}/approve. Approval only ever
#     happens through a human hitting that separate, credentialed HTTP endpoint
#     (dependencies=[Depends(require_verified_email)]) -- the model can never approve its own
#     pending plan. (Proven mechanically, not just asserted here, by
#     tests/test_llm_responses_capability_approval.py's static reference check.)


async def _match_capability_for_tool_call(
    db: AsyncSessionDep,
    auth: AuthContext,
    tool_call: object,
) -> object | None:
    """Resolve a model tool call's name against the org's own catalog by calling the existing
    capability_plane listing service directly (the same one GET /v1/capabilities calls) --
    never a re-implementation of catalog listing/matching."""
    name = getattr(getattr(tool_call, "function", None), "name", None)
    if not name:
        return None
    catalog = await list_capabilities_service(db, auth)
    for entry in catalog:
        if entry.name == name or entry.capability_id == name:
            return entry
    return None


def _capability_tool_call_arguments(tool_call: object) -> dict[str, object]:
    raw = getattr(getattr(tool_call, "function", None), "arguments", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"_raw_arguments": raw}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _annotated_capability_output_item(
    item: object,
    *,
    capability_id: str,
    capability_status: str,
    capability_output: dict[str, object] | None = None,
    capability_error: dict[str, object] | None = None,
) -> object:
    """Duck-typed copy of `item` (a real UtilityResponseOutputItem, or a test SimpleNamespace --
    the router is the only place that constructs this, so both must work) with its tool call
    resolved: the original tool_calls are cleared -- the call has now been handled server-side,
    whether it succeeded, failed, or is paused on approval -- and the real capability_* fields
    are attached instead."""
    return SimpleNamespace(
        index=item.index,
        item_type=getattr(item, "item_type", None),
        text=getattr(item, "text", None),
        tokens=getattr(item, "tokens", None),
        token_count=getattr(item, "token_count", 0),
        embedding=getattr(item, "embedding", None),
        provider=getattr(item, "provider", None),
        provider_attempts=getattr(item, "provider_attempts", ()),
        tool_calls=None,
        finish_reason=getattr(item, "finish_reason", None),
        capability_id=capability_id,
        capability_status=capability_status,
        capability_output=capability_output,
        capability_error=capability_error,
    )


async def _apply_capability_tool_execution(
    *,
    db: AsyncSessionDep,
    auth: AuthContext,
    response_id: str,
    outputs: list,
) -> tuple[list, ResponseCapabilityApproval | None]:
    """Intercepts the FIRST tool call in the response whose name resolves to a real capability
    and executes it server-side (see module note above). Deliberately intercepts at most ONE
    tool call per response -- a model turn with multiple simultaneous capability-resolved tool
    calls is a documented scope cut for this pass. Every item whose first tool call does not
    resolve to a real capability -- or every item once one tool call has already been
    intercepted -- passes through completely unchanged, so a caller whose tools never match a
    real capability sees zero behavior change versus before this feature existed."""
    approval: ResponseCapabilityApproval | None = None
    annotated: list = []
    intercepted = False
    for item in outputs:
        tool_calls = getattr(item, "tool_calls", None)
        if intercepted or not tool_calls:
            annotated.append(item)
            continue
        tool_call = tool_calls[0]
        capability = await _match_capability_for_tool_call(db, auth, tool_call)
        if capability is None:
            annotated.append(item)
            continue
        intercepted = True
        arguments = _capability_tool_call_arguments(tool_call)
        try:
            exec_response = await execute_capability_service(
                db,
                auth,
                CapabilityExecutionRequest(capability_id=capability.capability_id, input=arguments),
            )
        except CapabilityPlaneError as exc:
            annotated.append(
                _annotated_capability_output_item(
                    item,
                    capability_id=capability.capability_id,
                    capability_status="failed",
                    capability_error={"code": exc.code, "message": exc.message},
                )
            )
            continue
        if exec_response.status == ExecutionSessionStatus.STARTED:
            # approval_required (Track C1b's existing gate): mint the pause, remember exactly
            # how to resume it once a human approves the plan out-of-band.
            store_pending_capability_approval(
                response_id,
                capability_id=capability.capability_id,
                plan_id=exec_response.plan_id,
                plan_hash=exec_response.plan_hash or "",
                tool_call_id=getattr(tool_call, "id", "") or "",
            )
            approval = ResponseCapabilityApproval(
                plan_id=exec_response.plan_id,
                plan_hash=exec_response.plan_hash or "",
                message=(
                    f"Approve via POST /v1/capability-executions/{exec_response.plan_id}/approve, "
                    "then resend this request with previous_response_id set to this response's id "
                    'and a single {"type": "capability_approval_continuation", "plan_id": '
                    f'"{exec_response.plan_id}"}} input item to complete it.'
                ),
            )
            annotated.append(
                _annotated_capability_output_item(
                    item,
                    capability_id=capability.capability_id,
                    capability_status="approval_required",
                )
            )
            continue
        succeeded = exec_response.status == ExecutionSessionStatus.SUCCEEDED
        annotated.append(
            _annotated_capability_output_item(
                item,
                capability_id=capability.capability_id,
                capability_status="succeeded" if succeeded else "failed",
                capability_output=exec_response.output,
                capability_error=exec_response.error,
            )
        )
    return annotated, approval


async def _resume_capability_approval(
    *,
    db: AsyncSessionDep,
    auth: AuthContext,
    request: Request,
    model_id: str,
    previous_response_id: str,
    plan_id: str,
) -> ResponsesResponse:
    """Resumes a response paused on response.approval_required. Never calls the capability_plane
    approval service function -- approval already happened, out-of-band, through the separate
    credentialed HTTP endpoint; this only calls execute_capability_service again with plan_id
    set, exactly as a human-approved second POST /v1/capabilities/execute call would. If the
    plan isn't actually approved yet (still pending, rejected, or expired), this returns the
    SAME approval_required pause, never a fake success."""
    pending = load_pending_capability_approval(previous_response_id)
    if pending is None or pending["plan_id"] != plan_id:
        raise _llm_api_http_exception(
            LLMAPIError(
                "invalid_provider_request",
                (
                    f"previous_response_id '{previous_response_id}' has no pending capability "
                    f"approval for plan_id '{plan_id}'."
                ),
                {"previous_response_id": previous_response_id, "plan_id": plan_id},
            ),
            request,
        )

    try:
        exec_response = await execute_capability_service(
            db,
            auth,
            CapabilityExecutionRequest(capability_id=pending["capability_id"], plan_id=plan_id),
        )
    except CapabilityPlaneError as exc:
        # Still pending / rejected / expired -- surface the SAME pause, never a fake success.
        approval = ResponseCapabilityApproval(
            plan_id=plan_id,
            plan_hash=pending["plan_hash"],
            message=(
                f"This capability execution plan is not yet approved ({exc.code}: {exc.message}). "
                f"Approve via POST /v1/capability-executions/{plan_id}/approve, then resend this "
                "same request again."
            ),
        )
        return ResponsesResponse(
            id=previous_response_id,
            status="approval_required",
            model=model_id,
            output=[],
            usage=EmbeddingUsageResponse(prompt_tokens=0, total_tokens=0),
            approval_required=approval,
        )

    clear_pending_capability_approval(previous_response_id)
    new_response_id = finalize_capability_approval_conversation(
        previous_response_id=previous_response_id,
        tool_call_id=pending["tool_call_id"],
        capability_output=exec_response.output,
    )
    succeeded = exec_response.status == ExecutionSessionStatus.SUCCEEDED
    output_item = ResponseOutputItem(
        id=f"{new_response_id}_item_0",
        index=0,
        content=[
            ResponseOutputContent(
                type="text",
                token_count=0,
                capability_id=pending["capability_id"],
                capability_status="succeeded" if succeeded else "failed",
                capability_output=exec_response.output,
                capability_error=exec_response.error,
            )
        ],
    )
    return ResponsesResponse(
        id=new_response_id,
        status="completed",
        model=model_id,
        output=[output_item],
        usage=EmbeddingUsageResponse(prompt_tokens=0, total_tokens=0),
    )


@router.post(
    "/v1/responses",
    response_model=ResponsesResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "JSON response envelope by default, or Server-Sent Events when stream=true."
            ),
        }
    },
    summary="Run the unified model response envelope",
    description=(
        "Runs the selected model and returns a unified response envelope. "
        "Tokenizer-backed and lexical-embedding utility models remain deterministic, while "
        "configured provider-backed chat and embedding models are routed through the provider "
        "service when advertised in GET /v1/models. `input` also accepts a typed "
        "OpenResponses-style array (items shaped {type: message|function_call|"
        "function_call_output, ...}) for a real multi-turn conversation with optional tool "
        "calling and previous_response_id continuation."
    ),
)
async def responses(
    payload: ResponsesRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
    db: AsyncSessionDep,
) -> ResponsesResponse | StreamingResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )

    is_typed_input = _is_typed_response_input(payload.input)

    if payload.previous_response_id is not None and not is_typed_input:
        raise _llm_api_http_exception(
            LLMAPIError(
                "invalid_provider_request",
                "previous_response_id is only supported with the typed input-array shape.",
                {"model": payload.model},
            ),
            request,
        )

    # Track C1a: tools/tool_choice/parallel_tool_calls are forwarded ONLY when the caller
    # actually set them (same convention Track C2 established for /v1/chat/completions), so
    # every existing call site downstream (including test doubles with a fixed signature) keeps
    # working unchanged when a request never mentions tools.
    _tool_kwargs: dict[str, object] = {}
    if payload.tools:
        _tool_kwargs["tools"] = [tool.model_dump(exclude_none=True) for tool in payload.tools]
    if payload.tool_choice is not None:
        _tool_kwargs["tool_choice"] = (
            payload.tool_choice.model_dump(exclude_none=True)
            if isinstance(payload.tool_choice, BaseModel)
            else payload.tool_choice
        )
    if payload.parallel_tool_calls is not None:
        _tool_kwargs["parallel_tool_calls"] = payload.parallel_tool_calls

    # Track C1: set only when execute_capability_tools=True intercepted a tool call that
    # resolved to a capability whose catalog entry required approval -- None (the overwhelming
    # common case, and the ENTIRE case for every caller who never set execute_capability_tools)
    # means zero change to the response shape below.
    approval_info: ResponseCapabilityApproval | None = None

    try:
        if is_typed_input:
            try:
                typed_items = _RESPONSE_INPUT_ITEMS_ADAPTER.validate_python(payload.input)
            except ValidationError as exc:
                prefixed_errors = [
                    {**error, "loc": ("body", "input", *error.get("loc", ()))}
                    for error in exc.errors()
                ]
                raise RequestValidationError(prefixed_errors, body=payload.input) from exc

            # Track C1 resume path: a capability_approval_continuation item resumes a response
            # that previously paused on response.approval_required. It must be the ONLY item
            # (the plan already carries what was proposed -- there is nothing else to
            # re-supply) and previous_response_id must reference the exact paused response it
            # belongs to.
            continuation_items = [
                item
                for item in typed_items
                if isinstance(item, ResponseInputCapabilityApprovalContinuationItem)
            ]
            if continuation_items:
                if len(typed_items) > 1:
                    raise _llm_api_http_exception(
                        LLMAPIError(
                            "invalid_provider_request",
                            "A capability_approval_continuation input item must be the only "
                            "item in the request.",
                            {"model": payload.model},
                        ),
                        request,
                    )
                if payload.previous_response_id is None:
                    raise _llm_api_http_exception(
                        LLMAPIError(
                            "invalid_provider_request",
                            "capability_approval_continuation requires previous_response_id set "
                            "to the paused response it resumes.",
                            {"model": payload.model},
                        ),
                        request,
                    )
                if payload.stream:
                    # Matching Track C1a's own streaming-tool_calls restriction: real-time
                    # streaming of the resume/execute step is a deliberate, separate follow-up.
                    raise _llm_api_http_exception(
                        LLMAPIError(
                            "model_capability_unsupported",
                            "Streaming is not yet supported for a "
                            "capability_approval_continuation request; set stream=false.",
                            {
                                "model": payload.model,
                                "required_capability": "streaming_tool_calls",
                            },
                        ),
                        request,
                    )
                return await _resume_capability_approval(
                    db=db,
                    auth=auth,
                    request=request,
                    model_id=payload.model,
                    previous_response_id=payload.previous_response_id,
                    plan_id=continuation_items[0].plan_id,
                )

            descriptor, response_id, outputs, total_tokens = await create_utility_conversation_response(
                model_id=payload.model,
                items=[item.model_dump(exclude_none=True) for item in typed_items],
                previous_response_id=payload.previous_response_id,
                **_tool_kwargs,
            )
            if payload.execute_capability_tools:
                # Deliberate scope cut: capability-tool interception only runs on this typed
                # conversation path, where tool calling + previous_response_id continuation
                # already coherently live -- the legacy list[str] independent-completions path
                # (below) never stores conversation history for a pause to resume against.
                outputs, approval_info = await _apply_capability_tool_execution(
                    db=db,
                    auth=auth,
                    response_id=response_id,
                    outputs=outputs,
                )
        else:
            inputs = [payload.input] if isinstance(payload.input, str) else payload.input
            descriptor, response_id, outputs, total_tokens = await create_utility_response(
                model_id=payload.model,
                inputs=inputs,
                dimensions=payload.dimensions,
                **_tool_kwargs,
            )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc

    if payload.stream and (
        approval_info is not None or any(getattr(item, "tool_calls", None) for item in outputs)
    ):
        # True per-backend streaming of tool_calls deltas is a deliberately separate follow-up
        # (matching Track C2's identical restriction on /v1/chat/completions) -- refuse rather
        # than silently dropping the tool_calls the caller asked for into an SSE stream that
        # can't carry them. Track C1 extends this SAME restriction to a capability call that
        # resolved to approval_required: streaming the pause itself is a deliberate, separate
        # scope cut (see _responses_stream's own forward-compatible approval-event support,
        # which this refusal keeps unreachable through the live router today).
        raise _llm_api_http_exception(
            LLMAPIError(
                "model_capability_unsupported",
                "Streaming is not yet supported for a response that calls tools; set stream=false.",
                {"model": descriptor.model_id, "required_capability": "streaming_tool_calls"},
            ),
            request,
        )

    response_items = [
        ResponseOutputItem(
            id=f"{response_id}_item_{item.index}",
            index=item.index,
            provider_backend=item.provider.provider_backend if item.provider is not None else None,
            provider_model_id=item.provider.provider_model_id if item.provider is not None else None,
            provider_attempts=_provider_attempts_payload(getattr(item, "provider_attempts", ())),
            content=[
                ResponseOutputContent(
                    type=item.item_type,
                    text=item.text,
                    tokens=item.tokens,
                    token_count=item.token_count,
                    embedding=item.embedding,
                    tool_calls=_response_output_tool_calls(getattr(item, "tool_calls", None)),
                    finish_reason=getattr(item, "finish_reason", None),
                    capability_id=getattr(item, "capability_id", None),
                    capability_status=getattr(item, "capability_status", None),
                    capability_output=getattr(item, "capability_output", None),
                    capability_error=getattr(item, "capability_error", None),
                )
            ],
        )
        for item in outputs
    ]
    provider_backend, provider_model_id = _unique_provider_metadata(
        [
            (
                item.provider.provider_backend,
                item.provider.provider_model_id,
            )
            if item.provider is not None
            else None
            for item in outputs
        ]
    )
    provider_attempts = _unique_provider_attempts(
        [item.provider_attempts for item in response_items]
    )
    usage = EmbeddingUsageResponse(
        prompt_tokens=total_tokens,
        total_tokens=total_tokens,
    )
    response = ResponsesResponse(
        id=response_id,
        status="approval_required" if approval_info is not None else "completed",
        model=descriptor.model_id,
        provider_backend=provider_backend,
        provider_model_id=provider_model_id,
        provider_attempts=provider_attempts,
        output=response_items,
        usage=usage,
        approval_required=approval_info,
    )
    if payload.stream:
        return StreamingResponse(
            _responses_stream(
                response_id=response_id,
                model_id=descriptor.model_id,
                items=response_items,
                usage=usage,
                provider_backend=provider_backend,
                provider_model_id=provider_model_id,
                provider_attempts=provider_attempts,
            ),
            media_type="text/event-stream",
        )
    return response


@router.post(
    "/v1/embeddings",
    response_model=EmbeddingsResponse,
    summary="Generate embeddings from text",
    description=(
        "Generates embeddings from caller-supplied text. "
        "Runtime-backed utility models use deterministic lexical hash embeddings, while "
        "configured provider-backed embedding models are routed through the provider service."
    ),
)
async def embeddings(
    payload: EmbeddingsRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> EmbeddingsResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    inputs = [payload.input] if isinstance(payload.input, str) else payload.input
    try:
        descriptor, generated, total_tokens = await create_text_embeddings(
            model_id=payload.model,
            inputs=inputs,
            dimensions=payload.dimensions,
        )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    provider_backend, provider_model_id = _unique_provider_metadata(
        [
            (
                item.provider.provider_backend,
                item.provider.provider_model_id,
            )
            if item.provider is not None
            else None
            for item in generated
        ]
    )
    provider_attempts = _unique_provider_attempts(
        [_provider_attempts_payload(getattr(item, "provider_attempts", ())) for item in generated]
    )
    return EmbeddingsResponse(
        model=descriptor.model_id,
        dimensions=payload.dimensions,
        provider_backend=provider_backend,
        provider_model_id=provider_model_id,
        provider_attempts=provider_attempts,
        data=[
            EmbeddingVectorResponse(
                index=item.index,
                embedding=item.embedding,
                token_count=item.token_count,
            )
            for item in generated
        ],
        usage=EmbeddingUsageResponse(
            prompt_tokens=total_tokens,
            total_tokens=total_tokens,
        ),
    )


@router.post(
    "/v1/embeddings/similarity",
    response_model=EmbeddingSimilarityResponse,
    summary="Score similarity between two embedding vectors",
    description=(
        "Runs a deterministic embedding similarity kernel over caller-supplied vectors. "
        "This route does not generate embeddings from text; it only scores precomputed "
        "embedding vectors with the selected runtime-backed metric."
    ),
)
async def embedding_similarity(
    payload: EmbeddingSimilarityRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> EmbeddingSimilarityResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    try:
        descriptor, score = await embedding_similarity_score(
            model_id=payload.model,
            left=payload.left,
            right=payload.right,
        )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    return EmbeddingSimilarityResponse(
        model=descriptor.model_id,
        similarity_metric=descriptor.similarity_metric or "unknown",
        score=score,
        dimension=len(payload.left),
    )


@router.post(
    "/v1/rerank",
    response_model=RerankResponse,
    summary="Rerank caller-supplied document embeddings",
    description=(
        "Runs a deterministic reranking pass over caller-supplied embedding vectors. "
        "This route does not generate embeddings from text; it ranks the provided "
        "documents with the selected runtime-backed similarity or distance metric."
    ),
)
async def rerank(
    payload: RerankRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> RerankResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    try:
        descriptor, ranked_documents = await rerank_embeddings(
            model_id=payload.model,
            query_embedding=payload.query_embedding,
            documents=[
                {
                    "id": document.id,
                    "embedding": document.embedding,
                    "text": document.text,
                    "metadata": document.metadata,
                }
                for document in payload.documents
            ],
            top_n=payload.top_n,
        )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
    return RerankResponse(
        model=descriptor.model_id,
        similarity_metric=descriptor.similarity_metric or "unknown",
        total_documents=len(payload.documents),
        returned_documents=len(ranked_documents),
        data=[
            RerankResult(
                id=item.document_id,
                index=item.index,
                rank=item.rank,
                score=item.score,
                text=item.text,
                metadata=item.metadata,
            )
            for item in ranked_documents
        ],
    )
