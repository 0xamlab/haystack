"""gemm_qkv_proj_dualstream.mojo -- the pre-registered DUAL-STREAM concurrency test from the
REALRACE_RESULTS.md "Gate 0, MECHANISM RESOLVED (2026-08-12)" entry: now that llama.cpp's batch
amortization is proven to be DISPATCH OVERLAP (fresh-weight differential refuted cache residency),
the fork for the Algenta side is whether `_qkv_proj_gemm_mma8x8` leaves OCCUPANCY HEADROOM on the
machine (grid/fragment lever exists) or whether its single-stream ~3.9 TF/s (~14% of its Int8
ceiling) is already everything it can put on the GPU (inner-loop floor -- only a microkernel
restructure moves it). The test: run TWO batched streams CONCURRENTLY (two committed command
buffers in flight on the session queue before either waits, via the NEW `batch_shim_async.m`
commit/wait-split shim) and compare AGGREGATE throughput to a single dense stream of equal or
equal-per-stream size:

    S1  single stream, N=112            (baseline aggregate: 112 dispatches / gpu_total)
    S2  single stream, N=56             (per-stream baseline for the dual pairing)
    D1  two concurrent streams x N=56   (same 112 total dispatches as S1)
    D2  two concurrent streams x N=112  (224 total dispatches)

Decision rule, pre-registered in the ledger entry: if D1/D2 aggregate throughput (dispatches per
ms of two-stream span) exceeds S1's by >= 15%, the kernel has occupancy headroom and a
grid/fragment/scheduling lever exists; if within ~10%, the single-dispatch SIMD utilization is the
floor. The two-stream overlap itself is measured directly from the two command buffers'
GPUStartTime/GPUEndTime: span = max(end)-min(start); overlap_ms = durA+durB-span.

Does NOT modify any existing file. Same descriptor plumbing as `gemm_qkv_proj_batching_sim_gpuonly.
mojo` (same unmodified `metaldispatch.ffi` helpers, same real qkv_proj shape M=256/K=1024/N=4096,
same `_qkv_proj_gemm_mma8x8` discovery by substring), differing only in the shim linked (the `_as`
symbols of `batch_shim_async.m` instead of `_gt` of `batch_shim_gputime.m`) and the dual-commit
sweep below. Correctness of this file's own plumbing is checked against the CPU Float64 oracle at
the same small CORR shape before any timing runs.

Build (same recipe family as gemm_qkv_proj_batching_sim_gpuonly.mojo, with batch_shim_async.m
substituted):

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_async.m \\
        -o /tmp/gqpd_batch_shim_as.o
    clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/gqpd_mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \\
        ../mma_forge/probes/gemm_qkv_proj_dualstream.mojo \\
        -o /tmp/gemm_qkv_proj_dualstream \\
        -Xlinker /tmp/gqpd_batch_shim_as.o -Xlinker /tmp/gqpd_mm8_blob.o \\
        -Xlinker -framework -Xlinker Metal \\
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/gemm_qkv_proj_dualstream
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.ffi import external_call
from std.memory import alloc
from std.time import perf_counter_ns
from metaldispatch.ffi import (
    _mb_alloc_descriptors,
    _mb_set_header,
    _mb_set_arg_ptr,
    _mb_set_arg_int,
)

comptime M: Int = 256
comptime K: Int = 1024
comptime N_FEAT: Int = 4096

comptime N_MAX: Int = 112
comptime REPS: Int = 15
comptime WARMUP: Int = 3

comptime CORR_M: Int = 64
comptime CORR_K: Int = 48
comptime CORR_N: Int = 64


def _as_open_session() -> Int:
    return Int(external_call["algenta_open_session_as", Int64]())


def _as_pipeline_count() -> Int:
    return Int(external_call["algenta_pipeline_count_as", Int64]())


def _as_pipeline_name(idx: Int, mut out: String) -> Int:
    var buf = alloc[UInt8](256)
    var n = external_call[
        "algenta_pipeline_name_as", Int64, Int64, UnsafePointer[UInt8, origin=MutAnyOrigin], Int64
    ](Int64(idx), buf, Int64(256))
    if n < 0:
        buf.free()
        return -1
    var s = String()
    for i in range(Int(n)):
        s += chr(Int(buf[i]))
    out = s
    buf.free()
    return Int(n)


def _as_alloc_buffer(
    nbytes: Int, mut addr: UInt64, mut contents: UnsafePointer[UInt8, origin=MutAnyOrigin]
) -> Int:
    return Int(
        external_call[
            "algenta_alloc_buffer_as", Int64, Int64,
            UnsafePointer[UInt64, origin=MutAnyOrigin],
            UnsafePointer[UnsafePointer[UInt8, origin=MutAnyOrigin], origin=MutAnyOrigin],
        ](Int64(nbytes), UnsafePointer(to=addr), UnsafePointer(to=contents))
    )


def _as_commit_token(descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin], n: Int) -> Int:
    """Encode+n dispatches onto one fresh command buffer, COMMIT without waiting. Returns pending
    slot >= 0 or -1."""
    return Int(
        external_call[
            "algenta_commit_token_as", Int64, UnsafePointer[UInt8, origin=MutAnyOrigin], Int64
        ](descriptors, Int64(n))
    )


def _as_wait_token(
    slot: Int, mut gpu_ms: Float64, mut start_s: Float64, mut end_s: Float64
) -> Int:
    """Wait on slot's command buffer; gpu_ms = whole-buffer GPU-only duration (ms); start_s/end_s
    = raw GPUStartTime/GPUEndTime (seconds, comparable within this process). 0 on success."""
    return Int(
        external_call[
            "algenta_wait_token_as", Int64, Int64,
            UnsafePointer[Float64, origin=MutAnyOrigin],
            UnsafePointer[Float64, origin=MutAnyOrigin],
            UnsafePointer[Float64, origin=MutAnyOrigin],
        ](Int64(slot), UnsafePointer(to=gpu_ms), UnsafePointer(to=start_s), UnsafePointer(to=end_s))
    )


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _sorted_f64(times: List[Float64]) -> List[Float64]:
    var n = len(times)
    var sorted_ = List[Float64](capacity=n)
    for i in range(n):
        sorted_.append(times[i])
    for i in range(1, n):
        var key = sorted_[i]
        var j = i - 1
        while j >= 0 and sorted_[j] > key:
            sorted_[j + 1] = sorted_[j]
            j -= 1
        sorted_[j + 1] = key
    return sorted_^


def _pct(sorted_: List[Float64], frac: Float64) -> Float64:
    var n = len(sorted_)
    var idx = Int(frac * Float64(n - 1))
    if idx < 0:
        idx = 0
    if idx > n - 1:
        idx = n - 1
    return sorted_[idx]


def main() raises:
    print("=== gemm_qkv_proj_dualstream: DUAL-STREAM concurrency test for _qkv_proj_gemm_mma8x8 ===")
    print("=== (does aggregate throughput rise when two batched streams are in flight at once?)   ===")
    print("")

    var opened = _as_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session_as failed")
        return

    var count = _as_pipeline_count()
    var mma_idx = -1
    for i in range(count):
        var name = String()
        _ = _as_pipeline_name(i, name)
        if "qkv_proj_gemm_mma8x8" in name:
            mma_idx = i
    if mma_idx < 0:
        print("FAIL: qkv_proj_gemm_mma8x8 pipeline not discovered among", count, "loaded pipelines")
        return
    print("discovered qkv_proj_gemm_mma8x8 at pipeline index", mma_idx, "(", count, "pipelines total)")

    # ---- plumbing correctness at the small CORR shape, commit/wait via the _as shim ----
    var cxn_addr: UInt64 = 0
    var cxn_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var cw_addr: UInt64 = 0
    var cw_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var cwscale_addr: UInt64 = 0
    var cwscale_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var cy_addr: UInt64 = 0
    var cy_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    if _as_alloc_buffer(CORR_M * CORR_K * 4, cxn_addr, cxn_contents) < 0:
        print("FAIL: alloc corr xn")
        return
    if _as_alloc_buffer(CORR_N * CORR_K, cw_addr, cw_contents) < 0:
        print("FAIL: alloc corr w")
        return
    if _as_alloc_buffer(CORR_N * 4, cwscale_addr, cwscale_contents) < 0:
        print("FAIL: alloc corr wscale")
        return
    if _as_alloc_buffer(CORR_M * CORR_N * 4, cy_addr, cy_contents) < 0:
        print("FAIL: alloc corr y")
        return

    var cxn_f32 = cxn_contents.bitcast[Float32]()
    for i in range(CORR_M * CORR_K):
        cxn_f32[i] = Float32((i * 7 + 3) % 13) / 6.0 - 1.0
    var cw_i8 = cw_contents.bitcast[Int8]()
    for i in range(CORR_N * CORR_K):
        cw_i8[i] = Int8((i * 11 + 5) % 17) - 8
    var cwscale_f32 = cwscale_contents.bitcast[Float32]()
    for i in range(CORR_N):
        cwscale_f32[i] = Float32(0.01) + Float32(i % 5) * Float32(0.001)

    var corr_grid = ((CORR_M + 31) // 32) * ((CORR_N + 31) // 32)
    var corr_descs = _mb_alloc_descriptors(1)
    _mb_set_header(corr_descs, 0, mma_idx, corr_grid, 256, 7)
    _mb_set_arg_ptr(corr_descs, 0, 0, cy_addr)
    _mb_set_arg_ptr(corr_descs, 0, 1, cxn_addr)
    _mb_set_arg_ptr(corr_descs, 0, 2, cw_addr)
    _mb_set_arg_ptr(corr_descs, 0, 3, cwscale_addr)
    _mb_set_arg_int(corr_descs, 0, 4, CORR_M)
    _mb_set_arg_int(corr_descs, 0, 5, CORR_K)
    _mb_set_arg_int(corr_descs, 0, 6, CORR_N)

    var cslot = _as_commit_token(corr_descs, 1)
    if cslot < 0:
        print("FAIL: correctness commit failed")
        return
    var c_gpu: Float64 = 0.0
    var c_s: Float64 = 0.0
    var c_e: Float64 = 0.0
    if _as_wait_token(cslot, c_gpu, c_s, c_e) != 0:
        print("FAIL: correctness wait failed")
        return

    var cy_f32 = cy_contents.bitcast[Float32]()
    var worst = Float32(0.0)
    for mi in range(CORR_M):
        for ni in range(CORR_N):
            var acc = Float64(0.0)
            for kk in range(CORR_K):
                var wq = cw_i8[ni * CORR_K + kk]
                acc += Float64(cxn_f32[mi * CORR_K + kk]) * Float64(Float32(wq) * cwscale_f32[ni])
            var got = cy_f32[mi * CORR_N + ni]
            var want = Float32(acc)
            var d = _abs32(got - want)
            if d > worst:
                worst = d
    print("correctness shape M=", CORR_M, " K=", CORR_K, " N=", CORR_N, " worst delta:", worst)
    if worst > 0.01:
        print("CORRECTNESS: FAIL -- aborting")
        return
    print("CORRECTNESS: PASS")

    # ---- real-shape buffers + one descriptor table of N_MAX identical rows ----
    var xn_addr: UInt64 = 0
    var xn_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_addr: UInt64 = 0
    var y_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    if _as_alloc_buffer(M * K * 4, xn_addr, xn_contents) < 0:
        print("FAIL: alloc xn")
        return
    if _as_alloc_buffer(N_FEAT * K, w_addr, w_contents) < 0:
        print("FAIL: alloc w")
        return
    if _as_alloc_buffer(N_FEAT * 4, wscale_addr, wscale_contents) < 0:
        print("FAIL: alloc wscale")
        return
    if _as_alloc_buffer(M * N_FEAT * 4, y_addr, y_contents) < 0:
        print("FAIL: alloc y")
        return

    var xn_f32 = xn_contents.bitcast[Float32]()
    for i in range(M * K):
        xn_f32[i] = Float32((i * 7 + 3) % 13) / 6.0 - 1.0
    var w_i8 = w_contents.bitcast[Int8]()
    for i in range(N_FEAT * K):
        w_i8[i] = Int8((i * 11 + 5) % 17) - 8
    var wscale_f32 = wscale_contents.bitcast[Float32]()
    for i in range(N_FEAT):
        wscale_f32[i] = Float32(0.01) + Float32(i % 5) * Float32(0.001)

    var grid = ((M + 31) // 32) * ((N_FEAT + 31) // 32)
    print("real shape M=", M, " K=", K, " N=", N_FEAT, " grid=", grid, " block=256")

    var descs = _mb_alloc_descriptors(N_MAX)
    for i in range(N_MAX):
        _mb_set_header(descs, i, mma_idx, grid, 256, 7)
        _mb_set_arg_ptr(descs, i, 0, y_addr)
        _mb_set_arg_ptr(descs, i, 1, xn_addr)
        _mb_set_arg_ptr(descs, i, 2, w_addr)
        _mb_set_arg_ptr(descs, i, 3, wscale_addr)
        _mb_set_arg_int(descs, i, 4, M)
        _mb_set_arg_int(descs, i, 5, K)
        _mb_set_arg_int(descs, i, 6, N_FEAT)

    # ---- global warmup ----
    for _ in range(WARMUP):
        var s = _as_commit_token(descs, N_MAX)
        if s < 0:
            print("FAIL: warmup commit")
            return
        var g: Float64 = 0.0
        var a: Float64 = 0.0
        var b: Float64 = 0.0
        if _as_wait_token(s, g, a, b) != 0:
            print("FAIL: warmup wait")
            return

    print("")
    print("cell,metric,median,p10,p90")

    # ---- S1: single stream N=112 ----
    var s1_totals = List[Float64](capacity=REPS)
    for rep in range(WARMUP + REPS):
        var s = _as_commit_token(descs, N_MAX)
        if s < 0:
            print("FAIL: S1 commit")
            return
        var g: Float64 = 0.0
        var a: Float64 = 0.0
        var b: Float64 = 0.0
        if _as_wait_token(s, g, a, b) != 0:
            print("FAIL: S1 wait")
            return
        if rep >= WARMUP:
            s1_totals.append(g)
    var s1_sorted = _sorted_f64(s1_totals)
    print("S1_single_112,gpu_total_ms,", _pct(s1_sorted, 0.5), ",", _pct(s1_sorted, 0.1), ",", _pct(s1_sorted, 0.9))

    # ---- S2: single stream N=56 ----
    var s2_totals = List[Float64](capacity=REPS)
    for rep in range(WARMUP + REPS):
        var s = _as_commit_token(descs, 56)
        if s < 0:
            print("FAIL: S2 commit")
            return
        var g: Float64 = 0.0
        var a: Float64 = 0.0
        var b: Float64 = 0.0
        if _as_wait_token(s, g, a, b) != 0:
            print("FAIL: S2 wait")
            return
        if rep >= WARMUP:
            s2_totals.append(g)
    var s2_sorted = _sorted_f64(s2_totals)
    print("S2_single_56,gpu_total_ms,", _pct(s2_sorted, 0.5), ",", _pct(s2_sorted, 0.1), ",", _pct(s2_sorted, 0.9))

    # ---- D1: two concurrent streams x 56 ----
    var d1_spans = List[Float64](capacity=REPS)
    var d1_dura = List[Float64](capacity=REPS)
    var d1_durb = List[Float64](capacity=REPS)
    for rep in range(WARMUP + REPS):
        var sa = _as_commit_token(descs, 56)
        var sb = _as_commit_token(descs, 56)
        if sa < 0 or sb < 0:
            print("FAIL: D1 commit")
            return
        var ga: Float64 = 0.0
        var a1: Float64 = 0.0
        var a2: Float64 = 0.0
        var gb: Float64 = 0.0
        var b1: Float64 = 0.0
        var b2: Float64 = 0.0
        if _as_wait_token(sa, ga, a1, a2) != 0:
            print("FAIL: D1 wait A")
            return
        if _as_wait_token(sb, gb, b1, b2) != 0:
            print("FAIL: D1 wait B")
            return
        if rep >= WARMUP:
            var span_start = a1 if a1 < b1 else b1
            var span_end = a2 if a2 > b2 else b2
            d1_spans.append((span_end - span_start) * 1000.0)
            d1_dura.append(ga)
            d1_durb.append(gb)
    var d1_span_sorted = _sorted_f64(d1_spans)
    var d1_dura_sorted = _sorted_f64(d1_dura)
    var d1_durb_sorted = _sorted_f64(d1_durb)
    print("D1_dual_2x56,span_ms,", _pct(d1_span_sorted, 0.5), ",", _pct(d1_span_sorted, 0.1), ",", _pct(d1_span_sorted, 0.9))
    print("D1_dual_2x56,durA_ms,", _pct(d1_dura_sorted, 0.5), ",", _pct(d1_dura_sorted, 0.1), ",", _pct(d1_dura_sorted, 0.9))
    print("D1_dual_2x56,durB_ms,", _pct(d1_durb_sorted, 0.5), ",", _pct(d1_durb_sorted, 0.1), ",", _pct(d1_durb_sorted, 0.9))

    # ---- D2: two concurrent streams x 112 ----
    var d2_spans = List[Float64](capacity=REPS)
    var d2_dura = List[Float64](capacity=REPS)
    var d2_durb = List[Float64](capacity=REPS)
    for rep in range(WARMUP + REPS):
        var sa = _as_commit_token(descs, N_MAX)
        var sb = _as_commit_token(descs, N_MAX)
        if sa < 0 or sb < 0:
            print("FAIL: D2 commit")
            return
        var ga: Float64 = 0.0
        var a1: Float64 = 0.0
        var a2: Float64 = 0.0
        var gb: Float64 = 0.0
        var b1: Float64 = 0.0
        var b2: Float64 = 0.0
        if _as_wait_token(sa, ga, a1, a2) != 0:
            print("FAIL: D2 wait A")
            return
        if _as_wait_token(sb, gb, b1, b2) != 0:
            print("FAIL: D2 wait B")
            return
        if rep >= WARMUP:
            var span_start = a1 if a1 < b1 else b1
            var span_end = a2 if a2 > b2 else b2
            d2_spans.append((span_end - span_start) * 1000.0)
            d2_dura.append(ga)
            d2_durb.append(gb)
    var d2_span_sorted = _sorted_f64(d2_spans)
    var d2_dura_sorted = _sorted_f64(d2_dura)
    var d2_durb_sorted = _sorted_f64(d2_durb)
    print("D2_dual_2x112,span_ms,", _pct(d2_span_sorted, 0.5), ",", _pct(d2_span_sorted, 0.1), ",", _pct(d2_span_sorted, 0.9))
    print("D2_dual_2x112,durA_ms,", _pct(d2_dura_sorted, 0.5), ",", _pct(d2_dura_sorted, 0.1), ",", _pct(d2_dura_sorted, 0.9))
    print("D2_dual_2x112,durB_ms,", _pct(d2_durb_sorted, 0.5), ",", _pct(d2_durb_sorted, 0.1), ",", _pct(d2_durb_sorted, 0.9))

    # ---- verdict arithmetic ----
    var s1_med = _pct(s1_sorted, 0.5)
    var s2_med = _pct(s2_sorted, 0.5)
    var d1_span_med = _pct(d1_span_sorted, 0.5)
    var d2_span_med = _pct(d2_span_sorted, 0.5)
    var d1_dura_med = _pct(d1_dura_sorted, 0.5)
    var d1_durb_med = _pct(d1_durb_sorted, 0.5)
    var d2_dura_med = _pct(d2_dura_sorted, 0.5)
    var d2_durb_med = _pct(d2_durb_sorted, 0.5)

    var single_marginal = s1_med / 112.0
    var d1_aggregate_marginal = d1_span_med / 112.0
    var d2_aggregate_marginal = d2_span_med / 224.0
    var d1_speedup = single_marginal / d1_aggregate_marginal
    var d2_speedup = single_marginal / d2_aggregate_marginal
    var d1_overlap_ms = d1_dura_med + d1_durb_med - d1_span_med
    var d2_overlap_ms = d2_dura_med + d2_durb_med - d2_span_med

    print("")
    print("single-stream marginal:", single_marginal, "ms/dispatch")
    print("D1 aggregate marginal:", d1_aggregate_marginal, "ms/dispatch (speedup vs single:", d1_speedup, "x; overlap:", d1_overlap_ms, "ms )")
    print("D2 aggregate marginal:", d2_aggregate_marginal, "ms/dispatch (speedup vs single:", d2_speedup, "x; overlap:", d2_overlap_ms, "ms )")
    print("paired check: S2 single-56 =", s2_med, "ms vs D1 per-stream durA/durB =", d1_dura_med, "/", d1_durb_med, "ms")
    print("")
    print("VERDICT RULE (pre-registered): aggregate speedup >= 1.15x -> OCCUPANCY HEADROOM (grid/fragment lever exists);")
    print("                              within ~1.10x              -> INNER-LOOP FLOOR (only microkernel restructure moves it)")
    if d1_speedup >= 1.15:
        print("VERDICT: OCCUPANCY HEADROOM -- dual-stream aggregate beats single-stream by", d1_speedup, "x")
    elif d1_speedup <= 1.10:
        print("VERDICT: INNER-LOOP FLOOR -- dual-stream aggregate within noise of single-stream (", d1_speedup, "x )")
    else:
        print("VERDICT: INCONCLUSIVE -- speedup", d1_speedup, "x sits between the two pre-registered thresholds")
