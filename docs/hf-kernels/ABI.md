# Algenta in-process C ABI v1 (`libalgenta_<family>`)

Status: contract written before implementation (plan v3, Stage 1). Every statement below is a
requirement the implementation in `mojo/hfkernel/abi.mojo` and the generated `_native.py` must meet,
and every test in Stage 1 refers to a numbered clause.

## 1. Symbols (exact C types)

```c
int32_t algenta_runtime_version(void);                       /* 1.1 always returns 1 for this ABI */
void*   algenta_runtime_init(const char* config_utf8_nul);   /* 1.2 NULL on failure               */
char*   algenta_runtime_execute(void* h, const char* req_utf8_nul); /* 1.3 NULL only on allocation failure */
void    algenta_runtime_free(char* p);                       /* 1.4 frees a pointer returned by 1.3 */
void    algenta_runtime_shutdown(void* h);                   /* 1.5 releases a handle from 1.2      */
```

These five are the **only** exported symbols. Everything else in the library is private.

## 2. Strings

- 2.1 All `const char*` inputs are UTF-8, NUL-terminated.
- 2.2 The adapter scans an input with an explicit bound (`MAX_REQUEST_BYTES`, default 64 MiB, the
  worker's frame cap) **before** constructing a Mojo `String` or parsing. If no NUL is found within the
  bound, the call returns the error envelope `request_too_large` (3.3) without copying the input.
  The length check never happens after a full copy.
- 2.3 Invalid UTF-8 inside the bound is a supported error (`request_invalid_utf8`), never a crash.
- 2.4 Responses are UTF-8, NUL-terminated, and never contain interior NUL bytes.

## 3. Requests and responses

- 3.1 The request envelope is the worker's own: `{"type": "<request_type>", ...}` with `library_execute`
  as `{"type":"library_execute","module":"<m>","function":"<f>","args":[...]}`.
- 3.2 The response is the worker's own envelope: `{"result": ...}`, `{"result": ..., "mutated_args": ...}`
  or `{"error": "<text>", "error_code": "<code>", "error_message": "<text>"}`.
- 3.3 Adapter-level error codes (raised before the frozen dispatch runs): `request_too_large`,
  `request_invalid_utf8`, `request_not_json`, `request_type_unsupported` (route not declared by this
  family), `request_nesting_exceeded`, `count_exceeds_list_length` (count relations, same code as the SDK and server guards), `invalid_arguments` (a bounded argument whose length cannot be measured), `request_bounds_exceeded`
  (element count / dimension product / numeric range), `response_too_large`, `handle_invalid`
  (NULL handle), `runtime_execution_failed` (a `raises` escaping the frozen dispatch, wrapped).
- 3.4 Malformed JSON inside a valid, bounded buffer is a **supported** input and yields 3.3 codes.
- 3.5 A request whose `type` is not in the family's declared `request_types` is rejected before any
  dispatch or backend initialisation (`request_type_unsupported`).

## 4. Ownership and lifecycle

- 4.1 Every non-NULL pointer returned by `execute` is a fresh heap allocation owned by the caller.
- 4.2 The caller releases it **only** through `algenta_runtime_free` of the **same library instance**
  that produced it. Freeing through another instance, freeing twice, freeing a pointer not produced by
  1.3, or passing a dangling pointer is **undefined misuse** (5.2), not a supported error.
- 4.3 `free(NULL)` is a supported no-op.
- 4.4 `execute` returns NULL **only** when the response could not be allocated. The Python wrapper
  maps NULL to `KernelError("runtime_execution_failed")`.
- 4.5 A handle from `init` is valid until `shutdown`. `shutdown(NULL)` is a supported no-op.
  `shutdown` twice on the same handle is undefined misuse.
- 4.6 `execute(NULL, req)` returns the `handle_invalid` envelope (supported).
- 4.7 Completion (synchronous contract): `execute` returns only after the work required for the
  operation's result has completed and relevant execution errors have been collected. For
  accelerator sessions this means waiting on the operation/stream, not a device-wide sync.
  Session-owned resources stay valid until the session is closed. `shutdown` waits for, or
  explicitly rejects, outstanding operations (never returns while device work is in flight).
- 4.8 Process lifecycle: the library supports load → init → execute* → shutdown → unload in one
  process. Calling `execute` concurrently with `shutdown` on the same handle is undefined misuse;
  the wrapper prevents it with its lock. Fork after `init` is **not supported**: the runtime's
  worker threads (4.9) do not exist in the child. The wrapper forgets its handle in the child
  (`os.register_at_fork`) so a child re-initialises lazily, and the card tells users to start worker
  processes with `spawn`.
- 4.9 Runtime device: a Mojo `main` binary creates the process-wide AsyncRT CPU device in its
  prologue (`std.builtin._startup._ensure_runtime_init`); a shared library has no prologue, so `init`
  and `execute` get-or-create it (`KGEN_CompilerRT_AsyncRT_GetOrCreateCPUDevice`) before any
  dispatch. Without it the first `parallelize` kernel dereferenced NULL inside the runtime
  (`normk.rmsnorm`, `gemm.blocked`; measured 2026-09-21). The reference is held for the process
  lifetime and never released: same-toolchain families share one runtime image.

## 5. Supported API space vs undefined misuse

- 5.1 Supported: any well-formed call sequence per §4 with any byte content in a valid,
  NUL-terminated buffer within the bound. The contract for supported calls is: **no abort, no
  memory corruption, a well-formed envelope or NULL per 4.4**.
- 5.2 Undefined misuse: invalid or dangling pointers, buffers without a NUL within the bound *and*
  without readable memory, double free, cross-instance free, use after shutdown, concurrent
  execute/shutdown on one handle. No raw-pointer ABI can recover from these; tests for them run in
  isolated subprocesses and only document behaviour.

## 6. Thread safety

- 6.1 Distinct handles may be used from distinct threads concurrently only if the family's
  manifest says so; until Stage 2 measures it, the wrapper serialises all calls to one library
  instance with one lock (the "defined execution scope" of the wrapper).
- 6.2 Cross-family or cross-revision serialisation is **not** provided by this ABI; it needs an
  explicit shared coordinator and a concurrency test (plan v3, Concurrency scope).

## 7. Python wrapper obligations (`_native.py`)

- 7.1 `restype` of `execute` is `c_void_p`; bytes are copied out with `ctypes.string_at` and the
  pointer is then passed to `free`. Never `c_char_p` (it drops the pointer needed for `free`).
- 7.2 Handshake: `algenta_runtime_version() == 1` before any other call; mismatch raises.
- 7.3 One handle per loaded library instance; `shutdown` at interpreter exit via `atexit`, guarded
  against double calls.
- 7.4 The wrapper validates arguments (count relations, types, finite floats, 64-bit integer ranges,
  UTF-8 strings) for usability, but the safety argument is §2–§5 at the native boundary.
- 7.5 Every file the wrapper opens is named in `_native/manifest.json` (`load_order`, `library`,
  `files`), is a bare file name, and matches its recorded byte size and SHA-256 before `dlopen`; a
  Git LFS pointer, a truncated download or an edited manifest fails closed with
  `NativeUnavailable("native_unavailable")`. A macOS host below the manifest's `minos` fails with
  `platform_unsupported` before any load.
- 7.6 A library without the five §1 symbols fails with `NativeUnavailable("abi_mismatch")`; a failed
  load is cached for the process so callers see one error, not a re-load per call.
- 7.7 Engine result structs carry an integer `status` from their package's vocabulary
  (`<pkg>.contract.<x>_status_name`); the wrapper embeds the vocabulary in `CONTRACT["status_names"]`
  at generation time and raises `KernelError(<status name>)` for any non-`ok` status.

## 8. Versioning

- 8.1 Any change to §1 signatures, §3 envelopes or §4 ownership bumps `ABI_VERSION` and the Hub
  kernel major version together.
