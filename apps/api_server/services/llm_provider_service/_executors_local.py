"""Local Apple-Silicon GPU engine executor (parity gap 2, 2026-08-10).

The `algenta_local` backend is NOT an HTTP provider: the configured entry's `model_name` is a key
into `ALGENTA_LOCAL_LLM_MODELS_JSON` (a JSON object mapping model name -> checkpoint directory),
and execution goes through `algenta.inference.decode()` — the same model-agnostic Metal GPU path
the SDK calls directly (Qwen3-family checkpoints, greedy by default, seeded sampling when
`temperature > 0`). The runtime worker resolves through the standard SDK env knobs
(`ALGENTA_NATIVE_WORKER` / `ALGENTA_RUNTIME_WORKER`, `ALGENTA_RUNTIME_FALLBACK_MODE`).

Scope, stated precisely:
* Chat completions only (the backend's single declared capability).
* One-shot generation: the whole completion is produced, then returned (the existing SSE path
  re-chunks it like every other backend's response; true token-by-token streaming waits on
  persistent sessions, parity gap 4).
* Messages are formatted with the checkpoint's OWN chat template (`algenta.chat_template`, the
  Qwen3 template, byte-for-byte with `transformers`) before tokenization. A checkpoint that ships
  NO chat template falls back to plain-text flattening (a single message verbatim; multiple join
  as `role: content` lines); an unsupported template is refused, not guessed.
* Sampling parameters apply here and only here; remote HTTP providers keep their own server-side
  defaults until their payload builders grow parameter pass-through.
* No managed-spend gating/metering: the call runs on this machine's GPU, there is no upstream
  cost to gate or meter.
* Tool calling (Track C3, 2026-08-29): `tools` is rendered into the chat template's tools preamble
  (`algenta.chat_template`, already implemented it -- this module only had to wire it in), and any
  `<tool_call>` blocks the model emits are parsed back out of `generated_text` into structured
  `tool_calls` (`algenta.chat_template.split_tool_calls_from_generated_text`). The template's tools
  preamble is a hint the model MAY act on, not a mechanism that can force a call: `tool_choice`
  values that require forcing (`"required"`, or a named-function choice) are refused as
  `model_capability_unsupported` at the `create_chat_completion` call site rather than silently
  best-effort'd; `"none"` and `"auto"`/unset both work (the former simply never renders the
  preamble). A checkpoint with no chat template cannot render a tools preamble either -- `tools` on
  such a model is refused the same way. Streaming a tool-calling turn is refused generically by the
  router for every backend, not specially here.
"""
from __future__ import annotations

import asyncio
import json
import os
from functools import lru_cache
from typing import Any

_LOCAL_LLM_MODELS_ENV = "ALGENTA_LOCAL_LLM_MODELS_JSON"
_LOCAL_BACKEND = "algenta_local"
_DEFAULT_MAX_NEW_TOKENS = 256
_LOCAL_DECODE_TIMEOUT_SECONDS = 600.0


@lru_cache(maxsize=1)
def load_local_llm_checkpoint_map() -> dict[str, str]:
    """Model name -> checkpoint directory, from ALGENTA_LOCAL_LLM_MODELS_JSON. Empty when unset.
    Same lru_cache discipline as load_provider_model_configs: tests clear the cache around env
    changes."""
    raw = os.environ.get(_LOCAL_LLM_MODELS_ENV) or ""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_LOCAL_LLM_MODELS_ENV} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{_LOCAL_LLM_MODELS_ENV} must be a JSON object of name -> directory.")
    result: dict[str, str] = {}
    for name, directory in parsed.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{_LOCAL_LLM_MODELS_ENV} keys must be non-empty strings.")
        if not isinstance(directory, str) or not directory.strip():
            raise ValueError(f"{_LOCAL_LLM_MODELS_ENV}[{name!r}] must be a non-empty directory path.")
        result[name.strip()] = directory.strip()
    return result


def local_prompt_text_from_messages(messages: list[dict[str, str]]) -> str:
    """Fallback plain-text flattening for a checkpoint that ships NO chat template: a single
    message is used verbatim; multiple messages join as `role: content` lines. Checkpoints WITH a
    supported chat template never reach this -- they are formatted by `algenta.chat_template`
    instead (see execute_local_chat_completion)."""
    if len(messages) == 1:
        return str(messages[0].get("content") or "")
    return "\n".join(
        f"{message.get('role', 'user')}: {message.get('content') or ''}" for message in messages
    )


def _run_local_decode(
    *,
    checkpoint_dir: str,
    max_new_tokens: int,
    temperature: float | None,
    top_p: float | None,
    seed: int | None,
    prompt_text: str | None = None,
    messages: list[dict[str, str]] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    MojoRuntime, _InferenceError, decode = _import_algenta_inference()

    runtime = MojoRuntime(mode="local", timeout=_LOCAL_DECODE_TIMEOUT_SECONDS)
    kwargs: dict[str, Any] = {}
    if temperature is not None:
        kwargs["temperature"] = float(temperature)
    if top_p is not None:
        kwargs["top_p"] = float(top_p)
    if seed is not None:
        kwargs["seed"] = int(seed)
    if messages is not None:
        kwargs["messages"] = messages
        if tools:
            kwargs["tools"] = tools
    else:
        kwargs["prompt_text"] = prompt_text
    return decode(
        runtime,
        checkpoint_dir=checkpoint_dir,
        max_new_tokens=max_new_tokens,
        **kwargs,
    )


def _import_algenta_inference() -> tuple[Any, Any, Any]:
    """(MojoRuntime, InferenceError, decode) from the algenta SDK. Repo-dev convenience: when the
    server runs from the repo root (start-local.sh's PYTHONPATH=.), the SDK lives under
    packages/algenta and is not pip-installed, so add it to sys.path on first miss. ImportError
    propagates when the SDK is genuinely absent; the caller maps it to backend_unavailable."""
    try:
        from algenta import MojoRuntime
        from algenta.inference import InferenceError, decode

        return MojoRuntime, InferenceError, decode
    except ImportError:
        import sys

        repo_candidate = os.path.join(os.getcwd(), "packages", "algenta")
        if os.path.isdir(repo_candidate) and repo_candidate not in sys.path:
            sys.path.insert(0, repo_candidate)
        from algenta import MojoRuntime
        from algenta.inference import InferenceError, decode

        return MojoRuntime, InferenceError, decode


async def execute_local_chat_completion(
    *,
    config: Any,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    seed: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: object | None = None,
) -> Any:
    """Run one local-GPU chat completion and shape it exactly like the provider path's result
    (ChatCompletionResult with provider metadata + one `selected` attempt record), so the router's
    response/SSE plumbing consumes it unchanged.

    `tools`/`tool_choice` (Track C3): `tool_choice="none"` renders no tools preamble at all (same
    as omitting `tools`); any other value (`None`/`"auto"`, the defaults) renders the preamble and
    lets the model decide. A forced choice (`"required"` or a named-function choice) has already
    been refused upstream, at the `create_chat_completion` call site, before this function is
    reached -- the Qwen3 template has no mechanism to guarantee a call, so it is never silently
    attempted here."""
    from apps.api_server.services.llm_api_service import (
        ChatCompletionResult,
        ChatCompletionToolCall,
        ChatCompletionToolCallFunction,
        LLMAPIError,
        ProviderAttemptRecord,
        ProviderExecutionMetadata,
        _deterministic_chat_completion_id,
    )

    try:
        checkpoint_map = load_local_llm_checkpoint_map()
    except ValueError as exc:
        raise LLMAPIError(
            "invalid_provider_configuration",
            "Local engine model configuration is invalid.",
            {"cause": str(exc)},
        ) from exc

    checkpoint_dir = checkpoint_map.get(config.upstream_model)
    if checkpoint_dir is None:
        raise LLMAPIError(
            "model_not_supported",
            f"Local model '{config.upstream_model}' is not listed in {_LOCAL_LLM_MODELS_ENV}.",
            {"model": config.model_id, "local_model": config.upstream_model},
        )

    try:
        _MojoRuntime, InferenceError, _decode = _import_algenta_inference()
        from algenta.chat_template import (
            is_qwen3_chat_template,
            load_chat_template,
            split_tool_calls_from_generated_text,
        )
    except ImportError as exc:
        raise LLMAPIError(
            "backend_unavailable",
            "The algenta SDK is not importable in this deployment, so the local engine backend "
            "cannot run.",
            {"cause": str(exc)},
        ) from exc

    # Route chat messages through the checkpoint's own chat template when it ships a supported
    # one; a checkpoint with NO template falls back to plain-text flattening. (An unsupported
    # template is is_qwen3_chat_template()==False, which also flattens -- matching the documented
    # no-template behavior rather than refusing a whole model for a formatting gap.)
    has_chat_template = is_qwen3_chat_template(load_chat_template(checkpoint_dir))

    # tool_choice="none" is the same as never having passed tools at all -- no preamble, no
    # expectation the model calls anything. Anything else that reaches here (None/"auto") renders
    # the preamble and lets the model decide; a forced choice was already refused upstream.
    effective_tools = list(tools) if tools and tool_choice != "none" else None
    if effective_tools and not has_chat_template:
        raise LLMAPIError(
            "model_capability_unsupported",
            f"Local model '{config.upstream_model}' has no chat template, so it cannot render a "
            "tools preamble; tool calling requires a checkpoint with a supported chat template.",
            {
                "model": config.model_id,
                "local_model": config.upstream_model,
                "required_capability": "tool_calling",
            },
        )

    decode_input: dict[str, Any] = (
        {"messages": [dict(message) for message in messages], "tools": effective_tools}
        if has_chat_template
        else {"prompt_text": local_prompt_text_from_messages(messages)}
    )

    max_new_tokens = max_output_tokens if max_output_tokens else _DEFAULT_MAX_NEW_TOKENS
    try:
        result = await asyncio.to_thread(
            _run_local_decode,
            checkpoint_dir=checkpoint_dir,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            **decode_input,
        )
    except Exception as exc:  # noqa: BLE001 - engine refusals surface as mapped LLMAPIErrors
        if isinstance(exc, InferenceError):
            code = (
                "invalid_provider_request"
                if exc.code
                in (
                    "invalid_arguments",
                    "unsupported_architecture",
                    "checkpoint_not_found",
                    "unsupported_chat_template",
                )
                else "backend_unavailable"
            )
            raise LLMAPIError(
                code,
                f"Local engine refused the call: {exc}",
                {"engine_code": exc.code},
            ) from exc
        raise LLMAPIError(
            "backend_unavailable",
            f"Local engine execution failed: {exc}",
            {"cause": str(exc)},
        ) from exc

    completion_id = _deterministic_chat_completion_id(
        model_id=config.model_id,
        messages=[dict(message) for message in messages],
    )
    raw_text = result.generated_text or ""
    content: str | None = raw_text
    tool_calls: tuple[Any, ...] | None = None
    finish_reason = "stop"
    if effective_tools:
        parsed_content, parsed_calls = split_tool_calls_from_generated_text(raw_text)
        if parsed_calls:
            content = parsed_content
            tool_calls = tuple(
                ChatCompletionToolCall(
                    id=f"call_{completion_id}_{index}",
                    type="function",
                    function=ChatCompletionToolCallFunction(
                        name=call["name"],
                        arguments=json.dumps(
                            call["arguments"], separators=(",", ":"), sort_keys=True
                        ),
                    ),
                )
                for index, call in enumerate(parsed_calls)
            )
            finish_reason = "tool_calls"

    completion_tokens = max(len(result.token_ids) - result.n_prompt, 0)
    return ChatCompletionResult(
        completion_id=completion_id,
        content=content,
        prompt_tokens=result.n_prompt,
        completion_tokens=completion_tokens,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        provider=ProviderExecutionMetadata(
            provider_backend=_LOCAL_BACKEND,
            provider_model_id=config.model_id,
        ),
        provider_attempts=(
            ProviderAttemptRecord(
                provider_backend=_LOCAL_BACKEND,
                provider_model_id=config.model_id,
                outcome="selected",
            ),
        ),
    )
