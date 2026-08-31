"""Resident, step-by-step Qwen3 GPU decode sessions on the local runtime (Track C3).

Mirrors `algenta.session`'s `open_dataset`/`stream_chunks` shape exactly -- the SAME
`open`/pull(-repeated)/`close` pattern over the SAME persistent worker connection, applied to a
resident decode session (`algenta_runtime.qwen3_decode_session.Qwen3DecodeSessions` on the Mojo
side) instead of a resident dataset cursor:

    handle = open_qwen3_decode_session(
        checkpoint_dir, prompt_token_ids, max_new_tokens=16, routing_module=MODULE, timeout=60.0,
    )
    while True:
        step = step_qwen3_decode_session(handle, routing_module=MODULE, timeout=60.0)
        ... consume step["token_id"] ...
        if step["done"]:
            break
    close_qwen3_decode_session(handle, routing_module=MODULE, timeout=60.0)

`algenta.inference.decode_stream()` is the intended caller -- it wraps this trio in a generator
that closes the session in a `finally` block so an abandoned generator (a caller that stops
iterating before `done`) never leaks the underlying GPU session. Handles are scoped to the worker
connection and never reused after a close, so a stale reference fails cleanly
(`qwen3_session_not_found`) instead of reading whatever took its place -- same contract
`algenta.session`'s dataset handles already have.

GREEDY DECODE ONLY: mirrors the Mojo-side registry's own scope (see
`mojo/engine/algenta_runtime/qwen3_decode_session.mojo`'s module docstring) -- there is no sampling
parameter here because there is no sampled code path to drive yet.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "Qwen3DecodeSessionError",
    "close_qwen3_decode_session",
    "open_qwen3_decode_session",
    "step_qwen3_decode_session",
]


class Qwen3DecodeSessionError(RuntimeError):
    """A qwen3 decode session operation failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _send(
    frame: dict[str, Any],
    *,
    module_name: str,
    timeout: float,
    require_verified: bool,
) -> dict[str, Any]:
    from algenta.native import worker

    try:
        response = worker.execute(
            frame,
            timeout=timeout,
            require_verified=require_verified,
            module_name=module_name,
        )
    except worker.NativeWorkerUnavailable as exc:
        raise Qwen3DecodeSessionError("compute_runtime_unavailable", str(exc)) from exc

    code = response.get("error_code")
    if isinstance(code, str) and code:
        raise Qwen3DecodeSessionError(
            code, str(response.get("error_message") or response.get("error") or "")
        )
    return response


def open_qwen3_decode_session(
    checkpoint_dir: str,
    prompt_token_ids: list[int],
    *,
    max_new_tokens: int,
    routing_module: str,
    timeout: float,
    require_verified: bool = False,
    use_native_grouped_fa_attn_no_mirror: bool = True,
    use_msl_parity_all_roles: bool = True,
) -> str:
    """Open a resident Qwen3 decode session and return its handle.

    `checkpoint_dir` must already be the CONVERTED directory (`manifest.json` + `weights.blob`) --
    same requirement `algenta.inference.decode()`'s own `converted_checkpoint_dir` carries, and the
    same one `algenta.inference.decode_stream()` satisfies before calling this. `prompt_token_ids`
    is always used directly (there is no "baked into the manifest" fallback on this path). The two
    `use_*` flags default to the same values `decode()`'s own greedy path defaults to, so an
    equivalent call resolves the same execution plan on the Mojo side.

    At most one session may be open per worker connection at a time (the underlying GPU buffer
    table is a single resident slot, process-wide) -- opening a second session before closing the
    first raises `Qwen3DecodeSessionError("qwen3_session_already_open", ...)`.
    """
    response = _send(
        {
            "type": "qwen3_decode_open",
            "checkpoint_dir": str(checkpoint_dir),
            "prompt_token_ids": list(prompt_token_ids),
            "max_new_tokens": int(max_new_tokens),
            "use_native_grouped_fa_attn_no_mirror": bool(use_native_grouped_fa_attn_no_mirror),
            "use_msl_parity_all_roles": bool(use_msl_parity_all_roles),
        },
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )
    handle = response.get("session")
    if not isinstance(handle, str) or not handle:
        raise Qwen3DecodeSessionError(
            "mojo_result_parse_failed", f"qwen3_decode_open returned {response!r}"
        )
    return handle


def step_qwen3_decode_session(
    handle: str,
    *,
    routing_module: str,
    timeout: float,
    require_verified: bool = False,
) -> dict[str, Any]:
    """Advance `handle` by exactly one token and return the full response.

    Response keys: `token_id` (int), `position` (int, prompt + generated tokens so far),
    `done` (bool, true on the response carrying the LAST token this session will ever produce),
    `stopped_on_eos` (bool), `dispatches` (int, 0 for the prefill-buffered first token). Calling
    this again after `done` was already returned once is answered idempotently (the same last
    token, `done: True` again) rather than advancing the session further.
    """
    response = _send(
        {"type": "qwen3_decode_next", "session": handle},
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )
    if "token_id" not in response:
        raise Qwen3DecodeSessionError(
            "mojo_result_parse_failed", f"qwen3_decode_next returned {response!r}"
        )
    return response


def close_qwen3_decode_session(
    handle: str,
    *,
    routing_module: str,
    timeout: float,
    require_verified: bool = False,
) -> bool:
    """Close `handle`, releasing its GPU session. Safe to call at most once per handle; a second
    close (or a close of an unknown/already-closed handle) raises `qwen3_session_not_found` rather
    than crashing the worker connection -- callers that only close best-effort (e.g. a generator's
    `finally` block racing a caller-initiated close) should catch `Qwen3DecodeSessionError`."""
    response = _send(
        {"type": "qwen3_decode_close", "session": handle},
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )
    return bool(response.get("closed"))
