# Smallest public session API (draft for Stage 2b — required before the GPU spike)

Status: contract draft; Stage 2b implements exactly this and nothing more. JSON is the control
plane; models, caches and intermediate buffers stay resident inside the native session. This is
**not** a zero-copy interface for arbitrary external GPU tensors.

## Objects

- **Family library instance** — one loaded `libalgenta_<family>` (ABI v1 handle from `init`).
- **Session** — server-side state owned by one library instance and bound to one backend/device.
  Identified by an opaque `session_id` string returned by the library. A session id is only valid
  with the library instance (and loaded revision) that created it; the Python wrapper keys sessions
  by `(id(lib), session_id)` and rejects any other pairing before calling native code (ABI 4.5).

## Requests (all through `algenta_runtime_execute`, family must declare these `request_types`)

| type | payload | reply |
|---|---|---|
| `session_open` | `{"type":"session_open","kind":"<qwen3_decode|dataset|...>","backend":"cpu|metal|cuda","device":<int, optional>, "config":{...}}` | `{"result":{"session_id":"...","backend":"metal","device":0,"capabilities":{...}}}` or error |
| `session_execute` | `{"type":"session_execute","session_id":"...","op":"<operation>","args":{...}}` | `{"result":...}` — returns only after the operation's work has **completed** on the device and errors have been collected (ABI 4.7) |
| `session_close` | `{"type":"session_close","session_id":"..."}` | `{"result":true}`; releases all session-owned resources; idempotent for an unknown id → `session_unknown` error, never a crash |
| `session_list` | `{"type":"session_list"}` | ids + backend + open time; diagnostics only |

The existing worker request types (`dataset_open`, Qwen3 decode-session types) are mapped onto
these three verbs by the family's generated router; nothing in the frozen engine changes.

## Backend selection

- `backend` is explicit. `"auto"` is **not** offered in v1 (the loader already chose the artifact
  variant; the session must not silently switch). A backend the artifact was not built for →
  `backend_unavailable` (recoverable, session not created).
- Device index is optional; default 0; out of range → `device_invalid` (recoverable).

## Errors

| class | codes | effect |
|---|---|---|
| recoverable | `backend_unavailable`, `device_invalid`, `session_unknown`, `invalid_arguments`, `count_exceeds_list_length`, `op_unsupported`, `resource_exhausted` (allocation refused up front) | session (if any) stays valid |
| session-invalidating | `device_fault` (asynchronous device error surfaced at completion), `session_corrupt` | the reply says `"session_invalidated": true`; further `session_execute` on that id → `session_unknown`; resources are released by the library |
| process-fatal (must not happen in supported space) | none by contract | covered by the ABI safety suites |

## Lifecycle rules

- `shutdown` on the library instance closes every open session first, waiting for in-flight
  device work or rejecting it with `device_shutdown` (ABI 4.7); it never returns with work in flight.
- The wrapper serialises calls per library instance (one lock). Concurrency across sessions of one
  instance is a Stage 2b measurement, not a promise.
- Fork after a session is open is unsupported (Stage 2 result to be recorded).

## What Stage 2b must demonstrate (pass criteria)

Public Python entry → `session_open(kind, backend="metal")` → `session_execute(op)` runs on the
GPU (device timing or Metal capture evidence) → reply arrives after completion → decoded result
equals the worker/reference path (`mojo/tests/libs/test_residentk_session.mojo` golden vectors) →
`session_close` releases resources (device memory returns to baseline) → `shutdown` with an open
session closes it. Same sequence on CUDA before any CUDA artifact is published.

## As shipped in the Python package (2026-09-21)

The generated `session.py` exposes exactly one session kind, mapped onto the engine's
`qwen3_decode_open` / `qwen3_decode_next` / `qwen3_decode_close` routes:

- `DecodeSession(checkpoint_dir, prompt_token_ids, *, max_new_tokens)` validates its arguments
  before any native call (`invalid_arguments`) and raises `metal_required` on a build that is not
  Metal, before touching the library.
- The session is a real iterator: `next(session)` and `for token in session` yield generated token
  ids; `session.step()` returns the full record `{token_id, position, done, stopped_on_eos}`.
  Iteration ends after `max_new_tokens` tokens or an end-of-text token, which is the last id yielded.
- `close()` is idempotent; a closed session raises `session_closed`, an exhausted one `session_done`.
  A malformed native reply raises `runtime_execution_failed`, never a Python `AttributeError`.
- `decode(checkpoint_dir, prompt_token_ids, *, max_new_tokens)` runs one session to completion.

Measured 2026-09-21 on the published Metal build (Qwen3-0.6B converted checkpoint, prompt
`[785, 3974, 13876, 38835, 34208, 916]`, 8 tokens): iterator, `step()` and `decode()` all return
`[279, 15678, 5562, 13, 576, 3974, 13876, 38835]`, equal to the worker reference.
