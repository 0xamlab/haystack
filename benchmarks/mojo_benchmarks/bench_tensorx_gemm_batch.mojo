"""bench_tensorx_gemm_batch.mojo — the new LLM kernels through the existing batch machinery.

Hand-written, not generated. No library is named `tensorx_gemm_batch`, so nothing can collide.

Why this benchmark exists separately from `bench_tensorx_and_gemm.mojo`
------------------------------------------------------------------------
That one measures the kernels. This one measures whether they got the *composition* layer for free.

`algenta_runtime/batch.mojo` and `pipeline.mojo` were built to amortize the per-dispatch cost that
dominates a fine-grained workload: `execute(module, function, args)` is unary and synchronous on every
transport, so a caller needing twenty kernels pays twenty round trips and re-encodes every
intermediate. Both take the dispatcher as a compile-time parameter and `main.mojo` instantiates them
with `dispatch_runtime_library`.

The claim being checked is that `tensorx` and `gemm` are reachable through that machinery **with no
new wiring at all** — which is the whole payoff of rule 2's flat-list export shape. If it holds, a
caller batches fifty quantization calls into one frame and pays one frame's overhead. If it does not,
these kernels would need their own message type, a daemon RPC and SDK code, the way `columnar/` and
`query/` did.

What is measured
----------------
1. **N kernel calls one at a time** through `dispatch_runtime_library` — the unary path.
2. **The same N calls in one `batch_execute` frame** — the amortized path.

Both go through the identical dispatcher, so the difference is purely per-call envelope handling.

**In-process, batching is expected to be slightly SLOWER, and measuring it here proves nothing about
speed.** Batching exists to amortize the frame round trip — a length-prefixed write, a read, and the
worker's frame I/O, measured elsewhere at ~1.1 ms warm per dispatch. Calling `dispatch_runtime_library`
directly in this process has no frame at all, so the batch path adds outer-array parsing and per-item
result re-encoding on top of identical work and nets out negative. The first version of this benchmark
asserted batching would be faster here; that assertion was wrong, not the code.

So this file gates **reachability**, which is the claim that actually needed checking, and reports the
envelope cost as a tracked number. The throughput claim belongs to an end-to-end test through the
compiled worker over its socket — which rule 1b requires anyway, since a JIT run is not sufficient
evidence for anything that crosses the wire.

Gate
----
  * every request must dispatch cleanly — no `module_not_registered`, no execution failure
  * the batch envelope must report one result per request
Envelope overhead is printed for tracking, NOT gated.
"""
from std.time import perf_counter_ns

from algenta_runtime.batch import run_batch_execute
from algenta_runtime.session import ResidentDatasets
from runtime_library_dispatch_generated import dispatch_runtime_library


def _ns_since(t0: UInt) -> Float64:
    return Float64(Int(perf_counter_ns() - t0))


def _count_occurrences(haystack: String, needle: String) -> Int:
    """Count non-overlapping occurrences by byte scan.

    `String` has no slice operator here and the byte-level scan is the idiom the tree already uses
    (see `query.plan.substring`), so this stays a plain loop rather than reaching for a helper.
    """
    var h = haystack.as_bytes()
    var nd = needle.as_bytes()
    var n_h = len(h)
    var n_n = len(nd)
    if n_n == 0 or n_h < n_n:
        return 0
    var count = 0
    var i = 0
    while i + n_n <= n_h:
        var is_match = True
        for j in range(n_n):
            if h[i + j] != nd[j]:
                is_match = False
                break
        if is_match:
            count += 1
            i += n_n
        else:
            i += 1
    return count


def _unary(mod_name: String, fn_name: String, arg_json: String) -> String:
    """One `library_execute`-shaped call, exactly as the unary path builds it."""
    return (
        String('{"module":"')
        + mod_name
        + '","function":"'
        + fn_name
        + '","args":'
        + arg_json
        + "}"
    )


def main() raises:
    var failures = 0
    print("=== tensorx/gemm through the existing batch machinery ===")

    # A realistic fine-grained mix: dtype queries and quantization calibration, the shape a
    # quantization pass actually makes when it is deciding a layout.
    var n_calls = 64
    var modules = List[String]()
    var functions = List[String]()
    var args = List[String]()
    for i in range(n_calls):
        if i % 4 == 0:
            modules.append(String("tensorx.dtype"))
            functions.append(String("dtx_eps"))
            args.append(String("[3]"))
        elif i % 4 == 1:
            modules.append(String("tensorx.dtype"))
            functions.append(String("dtx_max_finite"))
            args.append(String("[4]"))
        elif i % 4 == 2:
            modules.append(String("tensorx.pack"))
            functions.append(String("calibrate_absmax"))
            args.append(String("[[0.5,-0.25,1.0,-1.0,0.125],5]"))
        else:
            modules.append(String("gemm.contract"))
            functions.append(String("gemm_work_fits"))
            args.append(String("[64,64,64,68719476736]"))

    var datasets = ResidentDatasets()

    # Warm the dispatcher before timing: the first call through a 111k-line if-chain pays for the
    # instruction cache, and that cost belongs to neither path.
    var warm = dispatch_runtime_library(_unary(modules[0], functions[0], args[0]))
    _ = warm

    # ── 1. unary: one dispatch per call ──────────────────────────────────────
    var unary_results = List[String]()
    var t0 = perf_counter_ns()
    for i in range(n_calls):
        unary_results.append(dispatch_runtime_library(_unary(modules[i], functions[i], args[i])))
    var unary_ns = _ns_since(t0)

    # ── 2. batched: one frame, N requests ────────────────────────────────────
    var frame = String('{"type":"batch_execute","requests":[')
    for i in range(n_calls):
        if i > 0:
            frame += ","
        frame += _unary(modules[i], functions[i], args[i])
    frame += '],"partial_ok":true}'

    var t1 = perf_counter_ns()
    var batched = run_batch_execute(dispatch_runtime_library, frame, datasets)
    var batch_ns = _ns_since(t1)

    print("")
    print("   calls:", n_calls)
    print("   unary  ns:", unary_ns, "  ns/call:", unary_ns / Float64(n_calls))
    print("   batched ns:", batch_ns, "  ns/call:", batch_ns / Float64(n_calls))
    var speedup = unary_ns / batch_ns if batch_ns > 0.0 else 0.0
    print("   amortization:", speedup, "x")

    # ── correctness: the batch envelope carries every result ─────────────────
    # Checked by counting the per-item result objects rather than by string-diffing the envelope,
    # because the batch wraps each result with its own outcome fields.
    var found = _count_occurrences(batched, String("\"result\""))

    if found >= n_calls:
        print("   envelope carries", found, "result field(s) for", n_calls, "requests")
    else:
        failures += 1
        print("   FAIL: batch envelope reported", found, "results for", n_calls, "requests")

    # No item may have failed — these are all valid calls.
    var n_exec_fail = _count_occurrences(batched, String("mojo_library_execution_failed"))
    var n_unregistered = _count_occurrences(batched, String("module_not_registered"))
    if n_exec_fail == 0 and n_unregistered == 0:
        print("   every batched call dispatched cleanly — tensorx and gemm are batch-reachable")
    else:
        failures += 1
        print("   FAIL: a batched call did not dispatch. Are the new modules in the contract?")

    var overhead_pct = (1.0 / speedup - 1.0) * 100.0 if speedup > 0.0 else 0.0
    print("   envelope overhead in-process:", overhead_pct, "%  (tracked, not gated)")

    print("")
    print("   In-process there is no frame to amortize, so the envelope is pure added cost and this")
    print("   number is EXPECTED to be negative. Batching pays over the worker's AF_UNIX transport,")
    print("   where each unary call also costs a length-prefixed round trip. That measurement needs")
    print("   the compiled binary and belongs in an end-to-end test, not here.")

    print("")
    if failures == 0:
        print("✅ batch reachability gate: the new kernels compose with no new wiring")
    else:
        print("❌ batch reachability gate:", failures, "failure(s)")
