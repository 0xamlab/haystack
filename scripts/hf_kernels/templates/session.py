"""Resident decode sessions on the accelerator: greedy Qwen3-family decode, one token per step."""
from __future__ import annotations

from ._native import _BACKEND, KernelError, execute


class DecodeSession:
    """A resident greedy decode session on the GPU (Apple Metal or NVIDIA CUDA).

    Open it with a converted checkpoint directory (the `manifest.json` + `weights.blob` form
    written by `prepare_model_checkpoint()` in the `algenta` package) and the prompt as token ids
    from the checkpoint's own tokenizer. One session is open at a time per kernel instance.

    Iterating the session yields one generated token id per step; each step returns only after
    its token has been computed on the device. `step()` returns the full record for one token
    (`token_id`, `position`, `done`, `stopped_on_eos`). Iteration ends after `max_new_tokens`
    tokens or after an end-of-text token, which is the last id yielded. Use the session as a
    context manager or call `close()`; a closed session raises `KernelError("session_closed")`.

    Attributes: `id` (the native session id), `n_prompt` (prompt length in tokens),
    `max_new_tokens`, `done`. Needs the Metal or CUDA build; on the CPU build the constructor raises
    `KernelError("gpu_build_required")` before touching the native library.
    """

    def __init__(self, checkpoint_dir: str, prompt_token_ids: list[int], *, max_new_tokens: int) -> None:
        if _BACKEND not in ("metal", "cuda"):
            raise KernelError("gpu_build_required", f"DecodeSession needs the Metal or CUDA build; this is the {_BACKEND} build. Load the kernel with backend=\"metal\" (macOS 26 or later) or on a CUDA host.")
        if not isinstance(checkpoint_dir, str) or not checkpoint_dir:
            raise KernelError("invalid_arguments", "checkpoint_dir must be a non-empty string (a converted checkpoint directory)")
        ids = list(prompt_token_ids) if isinstance(prompt_token_ids, (list, tuple)) else None
        if not ids or any(isinstance(t, bool) or not isinstance(t, int) or t < 0 for t in ids):
            raise KernelError("invalid_arguments", "prompt_token_ids must be a non-empty list of non-negative ints")
        if isinstance(max_new_tokens, bool) or not isinstance(max_new_tokens, int) or max_new_tokens < 1:
            raise KernelError("invalid_arguments", "max_new_tokens must be an int of at least 1")
        reply = execute({"type": "qwen3_decode_open", "checkpoint_dir": checkpoint_dir, "prompt_token_ids": ids, "max_new_tokens": max_new_tokens})
        _raise_if_error(reply)
        session = reply.get("session")
        if not isinstance(session, str) or not session:
            raise KernelError("runtime_execution_failed", "the kernel returned no session id")
        self._id: str | None = session
        n_prompt = reply.get("n_prompt", len(ids))
        self.n_prompt = int(n_prompt) if isinstance(n_prompt, int) and not isinstance(n_prompt, bool) else len(ids)
        self.max_new_tokens = max_new_tokens
        self.done = False

    @property
    def id(self) -> str | None:
        return self._id

    def step(self) -> dict:
        """Produce the next token. Returns `{"token_id", "position", "done", "stopped_on_eos"}`;
        the call returns only after the token has been computed on the device."""
        if self._id is None:
            raise KernelError("session_closed", "this session has been closed")
        if self.done:
            raise KernelError("session_done", "this session has produced all of its tokens")
        reply = execute({"type": "qwen3_decode_next", "session": self._id})
        _raise_if_error(reply)
        token_id = reply.get("token_id")
        if isinstance(token_id, bool) or not isinstance(token_id, int):
            raise KernelError("runtime_execution_failed", "the kernel returned no token id")
        self.done = bool(reply.get("done"))
        return {"token_id": token_id, "position": reply.get("position"), "done": self.done, "stopped_on_eos": bool(reply.get("stopped_on_eos"))}

    next = step  # earlier spelling

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.done or self._id is None:
            raise StopIteration
        return self.step()["token_id"]

    def close(self) -> None:
        """Release the session's device memory. Safe to call more than once."""
        if self._id is None:
            return
        reply = execute({"type": "qwen3_decode_close", "session": self._id})
        try:
            _raise_if_error(reply)
        except KernelError as exc:
            if exc.code != "qwen3_session_not_found":  # the engine no longer holds it: nothing left to release
                raise  # the id is kept, so close() can be retried
        self._id = None

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def decode(checkpoint_dir: str, prompt_token_ids: list[int], *, max_new_tokens: int) -> list[int]:
    """Greedy-decode up to `max_new_tokens` tokens in one call and return their ids."""
    with DecodeSession(checkpoint_dir, prompt_token_ids, max_new_tokens=max_new_tokens) as session:
        return list(session)


def _raise_if_error(reply: object) -> None:
    if not isinstance(reply, dict):
        raise KernelError("runtime_execution_failed", "the kernel returned a malformed reply")
    error = reply.get("error")
    if error not in (None, "", False):
        raise KernelError(str(reply.get("error_code") or "runtime_execution_failed"), str(reply.get("error_message") or error))


__all__ = ["DecodeSession", "decode"]
