"""Truthful per-backend streaming-capability + supported-parameter feature table.

Track C2 (real per-backend streaming, 2026-08).

Two streaming classes, surfaced honestly through GET /v1/models rather than silently assumed:

  - "passthrough": the backend's own streaming wire format is parsed incrementally, chunk-by-chunk,
    as the upstream actually generates it (see _streaming.py's normalizers) -- the openai-shaped
    family (openai, openai_compatible, groq, xai, mistral) plus anthropic.

  - "synthetic": stream=true still returns a valid SSE response, but the content is produced by one
    buffered (non-streaming) call and then sliced into fixed-size chunks afterward
    (apps/api_server/routers/llm.py's _stream_text_chunks) -- google_genai, cohere, and ollama each
    have a real streaming API of their own, just a DIFFERENT wire shape per backend with no
    normalizer here yet (deliberately deferred per this track's written scope); algenta_local's
    true-streaming gap is separate, later work. Never silently claimed as real.
"""
from __future__ import annotations

from typing import Literal

StreamingMode = Literal["passthrough", "synthetic"]

# Backends with a real per-backend SSE normalizer in _streaming.py.
PASSTHROUGH_STREAMING_BACKENDS: frozenset[str] = frozenset(
    {"openai", "openai_compatible", "groq", "xai", "mistral", "anthropic"}
)

# Backends with their own real streaming API but no normalizer here yet -- listed explicitly
# (rather than only implied by omission) so the deferral is a visible, intentional statement.
SYNTHETIC_STREAMING_BACKENDS: frozenset[str] = frozenset({"google_genai", "cohere", "ollama"})

_BACKEND_SUPPORTED_CHAT_PARAMETERS: dict[str, tuple[str, ...]] = {
    "openai": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
    "openai_compatible": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
    "groq": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
    "xai": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
    "mistral": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
    "anthropic": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
    "google_genai": ("max_tokens", "tools", "tool_choice"),
    "cohere": ("max_tokens", "tools", "tool_choice"),
    "ollama": ("max_tokens", "tools"),
    "algenta_local": ("max_tokens", "temperature", "top_p", "seed", "tools", "tool_choice"),
    "router": ("max_tokens", "tools", "tool_choice", "parallel_tool_calls", "stream"),
}


def streaming_mode_for_backend(backend: str | None) -> StreamingMode:
    """Truthful streaming capability for a raw backend name in isolation (no router resolution).
    Anything not in the passthrough set -- including None, an unrecognized name, or a future
    backend added here without a normalizer -- reports "synthetic": the safe, honest default that
    never claims passthrough without a real normalizer behind it."""
    if backend in PASSTHROUGH_STREAMING_BACKENDS:
        return "passthrough"
    return "synthetic"


def supported_parameters_for_backend(backend: str | None) -> tuple[str, ...]:
    if backend is None:
        return ()
    return _BACKEND_SUPPORTED_CHAT_PARAMETERS.get(backend, ())


def resolved_streaming_mode_for_model(model_id: str) -> StreamingMode:
    """The model's OWN, TRUE streaming capability. For a direct provider config this is just its
    backend's mode; for a `router` meta-backend model, walk to its first configured
    chat-completions leaf target and report THAT target's real backend mode -- so a router model
    never advertises "passthrough" on the strength of the word "router" alone while it actually
    bottoms out on a synthetic-only backend today. A model this process has no configuration for
    (utility/tokenizer models, or an unresolvable id) reports "synthetic" -- consistent with the
    fact that they only ever get the synthetic buffered-chunk stream."""
    from apps.api_server.services import llm_provider_service

    config = llm_provider_service.get_configured_provider_model(model_id)
    if config is None:
        return "synthetic"
    if config.backend != "router":
        return streaming_mode_for_backend(config.backend)
    for target_id in llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id=model_id
    ):
        target_config = llm_provider_service.get_configured_provider_model(target_id)
        if target_config is not None:
            return streaming_mode_for_backend(target_config.backend)
    return "synthetic"


def resolved_supported_parameters_for_model(model_id: str) -> tuple[str, ...]:
    """Mirrors resolved_streaming_mode_for_model's router-walk, but for the supported_parameters
    advertisement: a router model reports its first resolved chat-completions leaf target's
    parameter set."""
    from apps.api_server.services import llm_provider_service

    config = llm_provider_service.get_configured_provider_model(model_id)
    if config is None:
        return ()
    if config.backend != "router":
        return supported_parameters_for_backend(config.backend)
    for target_id in llm_provider_service.get_provider_resolved_chat_route_targets(
        model_id=model_id
    ):
        target_config = llm_provider_service.get_configured_provider_model(target_id)
        if target_config is not None:
            return supported_parameters_for_backend(target_config.backend)
    return ()
