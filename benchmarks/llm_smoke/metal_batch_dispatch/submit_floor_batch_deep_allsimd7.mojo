"""submit_floor_batch_deep_allsimd7.mojo — `submit_floor_batch.mojo`'s own no-op-shaped-dispatch
methodology, retargeted at `_MBQwen3I8AllSimd7`'s DEEP/split-K descriptor table (`descriptors_deep`,
`n_descriptors_deep = 1 + 7*n_layers + 2 = 199` at this model's `n_layers=28`) instead of the shallow
table's 171. Added for the lever-recomputation task (2026-08-03): "recompute both structural levers'
real ceilings with CURRENT numbers (post PR #524's dynamic split-K policy)". No existing file in this
directory isolates the DEEP table's own submission floor — `submit_floor_batch.mojo` only measures the
shallow 171-descriptor table, and every existing GPU-counter probe for the deep table (`qwen3_probe_
counters_i8_allsimd*_splitk_deepctx.mojo`) measures GPU-side per-role time via `algenta_run_token_
counters` + `resolveCounterRange`, not the pure host-submission floor via plain `algenta_run_token`.

WHY THIS NUMBER DOES NOT NEED TO BE MEASURED AT MULTIPLE `n_keys` VALUES SEPARATELY: `_build_
descriptors_deep` (session.mojo) allocates and issues `self.n_descriptors_deep` GPU dispatches on
EVERY deep-branch step regardless of `n_keys` — `_apply_n_splits` (also session.mojo) only rewrites
the split dispatch's `grid_x` header field and two `n_splits` VALUE arguments in place; it never adds
or removes a descriptor. So the number of encoder-setup/dispatch/end-encoding calls the host issues
per token is dtypically FIXED at 199 for every depth from the first deep-branch step onward (`n_keys
>= 32` under the new dynamic gate) — the host-side submission cost this probe isolates is therefore a
single number that applies at every depth this task samples (50/500/1000/2000/4000), not one that
needs to be re-measured per depth. (What DOES change with depth is how much actual GPU compute each
of those 199 dispatches does, in particular the two split-K dispatches' grid width — that is the
GPU-counter probes' job, not this one.)

Same technique as `submit_floor_batch.mojo`: open a real `_MBQwen3I8AllSimd7` session at the real
Qwen3-0.6B shape (so buffer allocation, pipeline resolution and the 199-descriptor deep build are
exactly what production pays), force the deep table to materialize (`_ensure_deep_initialized`,
bypassing `step()`'s lazy-init gate directly, same pattern `qwen3_probe_counters_i8_allsimd7_splitk_
deepctx.mojo` uses), then OVERWRITE every deep descriptor's `grid_x`/`threads_x` to the smallest legal
size (1 threadgroup, 32 threads) before timing repeated `_mb_run_token(s.descriptors_deep, ...)` calls.
Buffer CONTENTS are never checked here — pure timing probe, not correctness.

    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \\
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/submit_floor_batch_deep_allsimd7.mojo \\
        -o /tmp/submit_floor_batch_deep_allsimd7 \\
        -Xlinker /tmp/batch_shim.o -Xlinker -framework -Xlinker Metal \\
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/submit_floor_batch_deep_allsimd7
"""

from std.sys import has_accelerator
from std.time import perf_counter_ns
from metaldispatch.session import _MBQwen3I8AllSimd7, MB_GPU_BUILD
from metaldispatch.ffi import MB_DESC_STRIDE

comptime N_LAYERS: Int = 28
comptime REPS: Int = 30
comptime D_MODEL: Int = 1024
comptime H_Q: Int = 16
comptime H_KV: Int = 8
comptime D_HEAD: Int = 128
comptime D_FF: Int = 3072
comptime VOCAB: Int = 151936
comptime MAX_CTX: Int = 8192


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
        var s = _MBQwen3I8AllSimd7(
            D_MODEL, H_Q, H_KV, D_HEAD, D_FF, N_LAYERS, VOCAB, MAX_CTX, 1e-6, 1.0 / 11.3137
        )
        print("session open ok, shallow dispatch budget:", s.n_descriptors)

        # Force the deep table to materialize (normally deferred to the first deep-branch `step()`
        # call) so this probe can reach `s.descriptors_deep`/`s.n_descriptors_deep` directly.
        s._ensure_deep_initialized()
        print("deep dispatch budget:", s.n_descriptors_deep)

        # Shrink every DEEP descriptor's grid/threads to the minimum (1 threadgroup, 32 threads = one
        # SIMD group) so kernel compute time is negligible while the DISPATCH COUNT and pipeline
        # identities stay exactly what production issues at any depth.
        for d in range(s.n_descriptors_deep):
            var hdr = (s.descriptors_deep + d * MB_DESC_STRIDE).bitcast[Int32]()
            hdr[1] = Int32(1)   # grid_x
            hdr[2] = Int32(32)  # threads_x

        from metaldispatch.ffi import _mb_run_token
        # warm up
        for _ in range(5):
            _ = _mb_run_token(s.descriptors_deep, s.n_descriptors_deep)

        var samples = List[Float64]()
        for _ in range(REPS):
            var t0 = perf_counter_ns()
            var rc = _mb_run_token(s.descriptors_deep, s.n_descriptors_deep)
            if rc != 0:
                raise Error("submit_floor_batch_deep_allsimd7: algenta_run_token failed")
            var t1 = perf_counter_ns()
            samples.append(Float64(Int(t1 - t0)) / 1e3)

        var med = _median(samples)
        print("  ", s.n_descriptors_deep, "no-op-shaped DEEP dispatches / ONE shim call, median of", REPS,
              ":", med, "us  ==", med / Float64(s.n_descriptors_deep), "us/dispatch")
        print("  implied per-token submission floor at this dispatch count (any depth >= the n_keys=32 gate):",
              med / 1000.0, "ms")
        print("  implied tok/s ceiling from submission alone:", 1000.0 / (med / 1000.0))
