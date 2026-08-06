"""submit_floor_batch_deep_allsimd7_vary_n.mojo -- `submit_floor_batch_deep_allsimd7.mojo`'s own
no-op-shaped-dispatch methodology, but sweeping HOW MANY of the 199 deep-table descriptors get
submitted per call (`_mb_run_token(s.descriptors_deep, k)` for varying `k <= s.n_descriptors_deep`),
using the REAL, production-compiled pipeline objects (no synthetic stand-in kernel) -- this is the
fixed-vs-marginal decomposition the lever-recomputation task (2026-08-03) asks for, done against the
actual kernels this codebase ships rather than a hand-written no-op MSL kernel (`submission_fixed_vs_
marginal_probe.m`'s synthetic kernel measurably UNDER-estimated the real per-dispatch cost -- see that
probe's own module docstring revision note for why: swapping `setComputePipelineState` between complex,
real, high-register/high-threadgroup-memory compiled kernels is not free even at a trivial grid size,
and a one-line synthetic kernel does not reproduce that cost).

Same grid-shrink trick as `submit_floor_batch_deep_allsimd7.mojo` (every descriptor's grid_x/threads_x
forced to 1 threadgroup / 32 threads so KERNEL EXECUTION time is negligible at every k), then fits
`time_us = fixed_us + marginal_us_per_dispatch * k` by ordinary least squares over the sweep.

    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \\
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/submit_floor_batch_deep_allsimd7_vary_n.mojo \\
        -o /tmp/submit_floor_batch_deep_allsimd7_vary_n \\
        -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \\
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch_deep_allsimd7_vary_n
"""

from std.sys import has_accelerator
from std.time import perf_counter_ns
from metaldispatch.session import _MBQwen3I8AllSimd7, MB_GPU_BUILD
from metaldispatch.ffi import MB_DESC_STRIDE, _mb_run_token

comptime N_LAYERS: Int = 28
comptime REPS: Int = 30
comptime WARMUP: Int = 5
comptime D_MODEL: Int = 1024
comptime H_Q: Int = 16
comptime H_KV: Int = 8
comptime D_HEAD: Int = 128
comptime D_FF: Int = 3072
comptime VOCAB: Int = 151936
comptime MAX_CTX: Int = 8192


def _median(mut s: List[Float64]) -> Float64:
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
        var s = _MBQwen3I8AllSimd7(
            D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, 1e-6, 1.0 / 11.3137
        )
        s._ensure_deep_initialized()
        print("deep dispatch budget:", s.n_descriptors_deep)

        for d in range(s.n_descriptors_deep):
            var hdr = (s.descriptors_deep + d * MB_DESC_STRIDE).bitcast[Int32]()
            hdr[1] = Int32(1)
            hdr[2] = Int32(32)

        # warm up at full size first
        for _ in range(5):
            _ = _mb_run_token(s.descriptors_deep, s.n_descriptors_deep)

        var ks = List[Int]()
        ks.append(1); ks.append(10); ks.append(25); ks.append(50); ks.append(75)
        ks.append(100); ks.append(150); ks.append(199)

        var sum_n = 0.0
        var sum_t = 0.0
        var sum_nn = 0.0
        var sum_nt = 0.0
        var count = 0.0

        print("k,median_us,us_per_dispatch")
        for ki in range(len(ks)):
            var k = ks[ki]
            var samples = List[Float64]()
            for rep in range(WARMUP + REPS):
                var t0 = perf_counter_ns()
                var rc = _mb_run_token(s.descriptors_deep, k)
                var t1 = perf_counter_ns()
                if rc != 0:
                    raise Error("submit_floor_batch_deep_allsimd7_vary_n: algenta_run_token failed at k=" + String(k))
                if rep >= WARMUP:
                    samples.append(Float64(Int(t1 - t0)) / 1e3)
            var med = _median(samples)
            print(k, ",", med, ",", med / Float64(k))
            sum_n += Float64(k)
            sum_t += med
            sum_nn += Float64(k) * Float64(k)
            sum_nt += Float64(k) * med
            count += 1.0

        var mean_n = sum_n / count
        var mean_t = sum_t / count
        var cov_nt = sum_nt / count - mean_n * mean_t
        var var_n = sum_nn / count - mean_n * mean_n
        var marginal = cov_nt / var_n
        var fixed = mean_t - marginal * mean_n

        print("")
        print("=== OLS fit (REAL production pipelines): time_us = fixed_us + marginal_us_per_dispatch * k ===")
        print("fixed_us (per-command-buffer, ONE-TIME cost):", fixed)
        print("marginal_us_per_dispatch (per-dispatch encode+pipeline-swap cost):", marginal)
        print("sanity: fit predicts at k=199:", fixed + marginal * 199.0, "us  (measured single-shot floor was ~1806-1828us)")
