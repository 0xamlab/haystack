"""
hostio — host I/O primitives implemented with real libc FFI. Zero Python.

Why this package exists
-----------------------
`net/unix_socket.mojo` is frozen and stays exactly as it is. Its nine `libc_*` entry points are
backed by Python's `socket` module, and its own comment says why: *"Python-backed fallback for libc
FFI compat"*. At the time it was written Mojo's FFI could not carry it, so routing through CPython
was the right call.

That decision has one consequence that now matters: the worker binary links `libpython`. Measured on
2026-07-31, exactly 14 engine files use Python, and `net/unix_socket.mojo` (18 uses) is the load
bearer on the frame path — `types.mojo` and `request_parser.mojo` only *mention* Python in
docstrings, and `main.mojo` uses it for `sys.stdin.read()` in subprocess mode alone.

Linking `libpython` costs two things the LLM plane cannot pay:

1. **Node parity.** A Node-hosted worker would have to ship an embeddable CPython per platform
   (~70-110 MB each). With no libpython, the worker is an ordinary npm `optionalDependencies` binary
   per os/arch — the esbuild/playwright pattern — and TypeScript reaches the same lifecycle Python
   does, over the same AF_UNIX frames, with no daemon.
2. **Latency.** The Python-backed frame I/O was measured dominating per-dispatch cost at ~1.1 ms warm
   / ~1.7 ms hot. The kernel plane's envelope is microseconds to a few milliseconds *per operation*,
   so a millisecond of transport is the whole budget.

`from std.ffi import external_call` now works — verified on Mojo 0.26.3.0.dev2026042305: a real
`socket(AF_UNIX, SOCK_STREAM, 0)` returns a live fd, `bind`/`listen` on a constructed `sockaddr_un`
return 0, and `send`/`recv` round-trip bytes over a `socketpair`. So the compatibility constraint that
forced the Python fallback is gone, and this package is the additive answer to it.

Nothing here modifies `net/unix_socket.mojo`, `env.mojo` or `main.mojo`. Every current caller keeps
its current behaviour; this is a second, parallel implementation used only by the new worker.

Modules
-------
  socket_native  — the nine `libc_*` AF_UNIX entry points plus framed I/O, via `external_call`

Not reachable over the wire
---------------------------
`hostio` is listed in `_SKIP_RUNTIME_DIRS` in `apps/runtime/mojo_inventory.py`. That is deliberate and
load-bearing: `socket_native_open()` takes no arguments and returns an `Int`, which is a *valid*
runtime-contract signature, so without the skip entry any SDK caller could open sockets inside the
worker. Infrastructure primitives are not kernels and must never enter the dispatch table.
"""
