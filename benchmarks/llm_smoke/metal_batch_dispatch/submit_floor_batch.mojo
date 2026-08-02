"""submit_floor_batch.mojo — isolates the batched shim's pure dispatch-submission cost from kernel
compute time, the same way `residentk`'s own no-op-kernel measurement (`REALRACE_RESULTS.md`'s
"MAX dispatch submission, 171 dispatches: 16.45 ms, 33.4%") did for `DeviceContext.enqueue_function`.

Opens a real `_MBQwen3` session at the real Qwen3-0.6B shape (so pipeline resolution, buffer
allocation and the 171-descriptor build are exactly what production pays), then OVERWRITES every
descriptor's `grid_x`/`threads_x` to the smallest legal size (1 threadgroup, 32 threads — one SIMD
group, the minimum that does not change which kernel runs or how many descriptors are issued) before
timing repeated `algenta_run_token` calls. Buffer CONTENTS are never checked here — this is a timing
probe, not a correctness one; Stage 1/2/3 in `qwen3_generate_batch.mojo` and its own verification
already cover correctness.

    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \\
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/submit_floor_batch.mojo \\
        -o /tmp/submit_floor_batch \\
        -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \\
        -Xlinker -framework -Xlinker Foundation
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch
"""

from std.sys import has_accelerator
from std.time import perf_counter_ns
from metaldispatch.session import _MBQwen3, MB_GPU_BUILD
from metaldispatch.ffi import MB_DESC_STRIDE

comptime N_LAYERS: Int = 28
comptime REPS: Int = 30


fn _median(mut s: List[Float64]) -> Float64:
    for i in range(1, len(s)):
        var key = s[i]
        var j = i - 1
        while j >= 0 and s[j] > key:
            s[j + 1] = s[j]
            j -= 1
        s[j + 1] = key
    return s[len(s) // 2]


def main() raises:
    if not has_accelerator():
        print("no accelerator")
        return

    @parameter
    if not MB_GPU_BUILD:
        print("built without -D ALGENTA_GPU")
        return
    else:
        var s = _MBQwen3(1024, 16, 8, 128, 3072, N_LAYERS, 151936, 512, 1e-6, 1.0 / 11.3137)
        print("session open ok, dispatch budget:", s.dispatch_budget())

        # Shrink every descriptor's grid/threads to the minimum (1 threadgroup, 32 threads = one
        # SIMD group) so kernel compute time is negligible while the DISPATCH COUNT and pipeline
        # identities stay exactly what production issues.
        for d in range(s.n_descriptors):
            var hdr = (s.descriptors + d * MB_DESC_STRIDE).bitcast[Int32]()
            hdr[1] = Int32(1)   # grid_x
            hdr[2] = Int32(32)  # threads_x

        from metaldispatch.ffi import _mb_run_token
        # warm up
        for _ in range(5):
            _ = _mb_run_token(s.descriptors, s.n_descriptors)

        var samples = List[Float64]()
        for _ in range(REPS):
            var t0 = perf_counter_ns()
            var rc = _mb_run_token(s.descriptors, s.n_descriptors)
            if rc != 0:
                raise Error("submit_floor_batch: algenta_run_token failed")
            var t1 = perf_counter_ns()
            samples.append(Float64(Int(t1 - t0)) / 1e3)

        var med = _median(samples)
        print("  ", s.n_descriptors, "no-op-shaped dispatches / ONE shim call, median of", REPS,
              ":", med, "us  ==", med / Float64(s.n_descriptors), "us/dispatch")
        print("  implied per-token submission floor at this dispatch count:", med / 1000.0, "ms")
        print("  implied tok/s ceiling from submission alone:", 1000.0 / (med / 1000.0))
