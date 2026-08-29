from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api_server.middleware.auth import get_current_org, get_redis, require_verified_email
from apps.api_server.middleware.tenant_key_binding import bind_tenant_keys
from apps.api_server.schemas.llm import (
    ArtifactBridgeResolveRequest,
    ArtifactBridgeResolveResponse,
    ChatCompletionsRequest,
    ChatCompletionsResponse,
    ChatCompletionChoice,
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
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.llm_api_service import (
    create_chat_completion,
    resolve_artifact_bridge,
    LLMAPIError,
    count_text_tokens,
    create_text_embeddings,
    create_utility_response,
    embedding_similarity_score,
    list_llm_model_descriptors,
    list_provider_discovered_descriptors,
    rerank_embeddings,
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


async def _responses_stream(
    *,
    response_id: str,
    model_id: str,
    items: list[ResponseOutputItem],
    usage: EmbeddingUsageResponse,
    provider_backend: str | None,
    provider_model_id: str | None,
    provider_attempts: list[ProviderAttemptResponse],
) -> AsyncIterator[str]:
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
            messages=[
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
                for message in payload.messages
            ],
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
        "service when advertised in GET /v1/models."
    ),
)
async def responses(
    payload: ResponsesRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: Annotated[object, Depends(get_redis)],
) -> ResponsesResponse | StreamingResponse:
    await _enforce_llm_api_rate_limit(
        request=request,
        auth=auth,
        redis_client=redis_client,
    )
    inputs = [payload.input] if isinstance(payload.input, str) else payload.input
    try:
        descriptor, response_id, outputs, total_tokens = await create_utility_response(
            model_id=payload.model,
            inputs=inputs,
            dimensions=payload.dimensions,
        )
    except (LLMAPIError, MojoLibraryError) as exc:
        raise _llm_api_http_exception(exc, request) from exc
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
        model=descriptor.model_id,
        provider_backend=provider_backend,
        provider_model_id=provider_model_id,
        provider_attempts=provider_attempts,
        output=response_items,
        usage=usage,
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
