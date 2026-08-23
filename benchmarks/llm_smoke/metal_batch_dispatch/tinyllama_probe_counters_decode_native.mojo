"""tinyllama_probe_counters_decode_native.mojo -- per-role GPU-counter breakdown of ONE TinyLlama
single-stream decode step on the NATIVE FAST PATH (feat/llama-q80gap, 2026-08-13), adapted from
`tinyllama_probe_counters_decode.mojo` (same GPU-counter methodology, unmodified counter shim
`batch_shim_counters.m`).

WHY THE NATIVE PATH: since feat/llama-native-deep (#669) TinyLlama-1.1B (d_head=64, GQA 32:4, no
QK-norm) resolves `PF_ATTN_PARAMETRIC_NATIVE_DECODE` -- parametric OFF-family prefill + packed-F16
native KV + flash-decoding split-K DECODE (the f2u2 d_head=64 partial + the engine merge). That is
the production path the `algenta-gpu-worker-llamanat2` worker runs and the path this probe
dissects; the legacy-path probe stays the reference for `PF_ATTN_OFF`.

ONE descriptor table is exercised (`self.descriptors_decode_native_splitk`,
1 + 7*n_layers + 2 dispatches -- every race depth here is >= _NATIVE_DECODE_SPLITK_THRESHOLD=128):
Roles per layer: [norm_gemv(rms1+qkv GEMV), kvprod_native(AF native KV producer: rope + packed-F16
KV append + Q narrow), splitk_partial(f2u2), splitk_merge, gemv_accum(o_proj),
norm_gemv2_swiglu(rms2+gate/up+swiglu), gemv_accum(down_proj)]. Tail: lmhead_argmax (fused final
rmsnorm + lm_head + per-block argmax), argmax_reduce. The per-step patching mirrors
`_step_native_kv_impl` EXACTLY: token_id arg, depth-adaptive n_splits
(clamp(n_keys//64, _NATIVE_DECODE_N_SPLITS, native_splitk_derived_opt) -> partial header grid +
partial arg 7 + merge arg 4, only when the value changes), per-layer kvprod pos_base + partial
n_keys.

WEIGHTS: loaded from the SDK's quantized-state cache (weights_i8.cache -- the exact post-
quantization device bytes the production warm path restores), header-verified (magic + manifest
SHA-256 + dims + length). KV caches hold whatever allocation left there: timing is shape-driven,
value-independent (same rationale as the legacy probe).

    argv[1] = timed samples per depth (default 7)
    argv[2] = optional single n_keys depth to measure (default: full sweep)
    argv[3] = optional n_splits override (default 0 = production adaptive formula)

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      xcrun --sdk macosx clang -c -fobjc-arc -O2 \
        ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/probe_tinyllama_nat/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -D ALGENTA_STAGE_6144 -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/tinyllama_probe_counters_decode_native.mojo \
        -o /tmp/probe_tinyllama_nat/tinyllama_probe_counters_decode_native \
        -Xlinker /tmp/probe_tinyllama_nat/batch_shim_counters.o \
        $(for o in ../mojo_build/gpu-worker/blobs/*.o; do printf ' -Xlinker %s' "$o"; done) \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    /tmp/probe_tinyllama_nat/tinyllama_probe_counters_decode_native 7
"""

from std.sys import argv
from std.time import perf_counter_ns
from std.memory import alloc
from std.ffi import external_call
from std.math import sqrt
from json.parser import json_get_object, json_get_int, json_get_float
from conv import parse_int
from crypto.pbkdf2 import sha256_bytes
from attnk.rope import rope_table
from metaldispatch.contract import MB_OK, metaldispatch_status_name
from metaldispatch.session import MB_GPU_BUILD
from metaldispatch.ffi import _mb_run_token, _mb_set_arg_int, _mb_set_header
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill, _NATIVE_DECODE_N_SPLITS
from metaldispatch.session_prefill_policy import (
    PF_ATTN_PARAMETRIC_NATIVE_DECODE,
    PF_GEMM_ORIGINAL,
    UnresolvedPrefillConfig,
)

comptime MANIFEST_PATH: String = "/private/tmp/tinyllama/.algenta-cache/manifest.json"
comptime CACHE_PATH: String = "/private/tmp/tinyllama/.algenta-cache/weights_i8.cache"
comptime MAX_CTX: Int = 2048
comptime HEADER_BYTES: Int = 104
comptime CHUNK_BYTES: Int = 1 << 27


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


def _le64(raw: List[UInt8], off: Int) -> Int:
    var v = 0
    for i in range(8):
        v = v | (Int(raw[off + i]) << (8 * i))
    return v


def _sha256_of_string(s: String) raises -> List[Int]:
    var raw = s.as_bytes()
    var ints = List[Int](capacity=len(raw))
    for i in range(len(raw)):
        ints.append(Int(raw[i]))
    return sha256_bytes(ints^)


def _mb_counters_supported() -> Int:
    return Int(external_call["algenta_counters_supported", Int64]())


def _mb_sample_gpu_timestamp() -> UInt64:
    return external_call["algenta_sample_gpu_timestamp", UInt64]()


def _calibrate_gpu_tick_ns(hold_ms: Int) raises -> Float64:
    var t_wall0 = perf_counter_ns()
    var gpu0 = _mb_sample_gpu_timestamp()
    var deadline = t_wall0 + hold_ms * 1_000_000
    while perf_counter_ns() < deadline:
        pass
    var gpu1 = _mb_sample_gpu_timestamp()
    var t_wall1 = perf_counter_ns()
    if gpu1 <= gpu0:
        raise Error("tinyllama_probe_native: GPU timestamp calibration did not advance")
    var wall_seconds = Float64(Int(t_wall1 - t_wall0)) / 1.0e9
    var tick_rate_hz = Float64(gpu1 - gpu0) / wall_seconds
    return 1.0e9 / tick_rate_hz


def _mb_open_counters(max_samples: Int) -> Int:
    return Int(external_call["algenta_open_counters", Int64, Int64](Int64(max_samples)))


def _mb_run_token_counters(
    descriptors: UnsafePointer[UInt8, origin=MutUntrackedOrigin],
    n: Int,
    out_ticks: UnsafePointer[UInt64, origin=MutUntrackedOrigin],
) -> Int:
    return Int(
        external_call[
            "algenta_run_token_counters", Int64,
            UnsafePointer[UInt8, origin=MutUntrackedOrigin], Int64,
            UnsafePointer[UInt64, origin=MutUntrackedOrigin],
        ](descriptors, Int64(n), out_ticks)
    )


def _median(vals: List[Float64]) -> Float64:
    var n = len(vals)
    if n == 0:
        return 0.0
    var a = List[Float64](capacity=n)
    for i in range(n):
        a.append(vals[i])
    for i in range(1, n):
        var key = a[i]
        var j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a[n // 2]


def main() raises:
    var args = argv()
    var n_samples = 7
    var single_depth = -1
    var splits_override = 0
    if len(args) > 1:
        n_samples = parse_int(String(args[1]))
    if len(args) > 2:
        single_depth = parse_int(String(args[2]))
    if len(args) > 3:
        splits_override = parse_int(String(args[3]))

    if not MB_GPU_BUILD:
        raise Error("tinyllama_probe_native: not a GPU build")
    if _mb_counters_supported() == 0:
        raise Error("tinyllama_probe_native: counter sampling unsupported on this device")

    # ── model dims from the SDK-converted manifest (never hardcoded) ─────────────────────────
    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var eps = json_get_float(config, "rms_norm_eps", 1.0e-5)
    var theta = Float64(json_get_float(config, "rope_theta", 10000.0))
    var has_qk_norm = json_get_int(config, "has_qk_norm", -1)
    var tied = json_get_int(config, "tie_word_embeddings", -1)
    var scale = 1.0 / sqrt(Float64(d_head))

    print("tinyllama_probe_native: d_model =", d_model, "h_q =", h_q, "h_kv =", h_kv,
          "d_head =", d_head, "d_ff =", d_ff, "layers =", n_layers,
          "vocab =", vocab_size, "qk_norm =", has_qk_norm, "tied =", tied)

    var s = _MBQwen3I8AllSimd7Prefill(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale,
        UnresolvedPrefillConfig(PF_ATTN_PARAMETRIC_NATIVE_DECODE, PF_GEMM_ORIGINAL),
        qk_norm=has_qk_norm, tied_embeddings=tied,
    )
    print("  resolved plan: attention =", s.plan.attention, " gemm =", s.plan.gemm,
          " kv_contract =", s.plan.kv_contract, " decode =", s.plan.decode)
    if s.plan.attention != PF_ATTN_PARAMETRIC_NATIVE_DECODE:
        raise Error(
            "tinyllama_probe_native: plan degraded off the native fast path, attention="
            + String(s.plan.attention)
        )
    if not s.native_decode_splitk_built:
        raise Error("tinyllama_probe_native: split-K native decode table not built (blob missing?)")
    print("  n_cores =", s.n_cores,
          " n_descriptors_decode_native_splitk =", s.n_descriptors_decode_native_splitk,
          " derived_opt_n_splits =", s.native_splitk_derived_opt,
          " partial_eff_threads =", s.native_splitk_partial_eff_threads)

    # ── weights: the production warm path's quantized-state cache ───────────────────────────
    var cf = open(CACHE_PATH, "r")
    var header = cf.read_bytes(HEADER_BYTES)
    if len(header) != HEADER_BYTES:
        cf.close()
        raise Error("tinyllama_probe_native: cache header short read")
    var magic_ok = (
        header[0] == 65 and header[1] == 76 and header[2] == 71 and header[3] == 73
        and header[4] == 56 and header[5] == 67 and header[6] == 48 and header[7] == 49
    )
    if not magic_ok:
        cf.close()
        raise Error("tinyllama_probe_native: cache magic mismatch")
    if _le64(header, 40) != n_layers or _le64(header, 48) != d_model
        or _le64(header, 56) != h_q or _le64(header, 64) != h_kv
        or _le64(header, 72) != d_head or _le64(header, 80) != d_ff
        or _le64(header, 88) != vocab_size:
        cf.close()
        raise Error("tinyllama_probe_native: cache dims disagree with manifest")
    var digest = _sha256_of_string(manifest)
    for i in range(32):
        if Int(header[8 + i]) != digest[i]:
            cf.close()
            raise Error("tinyllama_probe_native: cache manifest-sha256 mismatch")
    var state_len = _le64(header, 96)
    if state_len != s.quantized_state_bytes():
        cf.close()
        raise Error(
            "tinyllama_probe_native: cache state length " + String(state_len)
            + " != session quantized_state_bytes " + String(s.quantized_state_bytes())
        )
    var state = List[UInt8](capacity=state_len)
    var remaining = state_len
    while remaining > 0:
        var take = CHUNK_BYTES
        if remaining < take:
            take = remaining
        var chunk = cf.read_bytes(take)
        if len(chunk) != take:
            cf.close()
            raise Error("tinyllama_probe_native: cache short read")
        for i in range(take):
            state.append(chunk[i])
        remaining -= take
    cf.close()
    var ls = s.load_quantized_state(state^)
    if ls != MB_OK:
        raise Error(
            "tinyllama_probe_native: load_quantized_state failed: " + metaldispatch_status_name(ls)
        )
    var rt = rope_table(d_head, MAX_CTX, theta)
    var rs = s.upload_rope_tables(rt.cos_table, rt.sin_table, MAX_CTX)
    if rs != MB_OK:
        raise Error("tinyllama_probe_native: upload_rope_tables failed: " + metaldispatch_status_name(rs))
    _ = s.seal()
    print("  weights loaded from quantized-state cache + rope tables uploaded")

    # Keep the legacy-deep split-K MTLBs reachable (AOT DCE otherwise drops the compile_function
    # targets the ctor's discovery guard needs -- same discipline as the legacy probe).
    s._ensure_deep_initialized()

    # ── depth list ──────────────────────────────────────────────────────────────────────────
    var depths = List[Int]()
    if single_depth > 0:
        depths.append(single_depth)
    else:
        # All >= _NATIVE_DECODE_SPLITK_THRESHOLD (128) -> the split-K table this probe dissects.
        # 288/1056 = the MID-decode n_keys of the deep_bench 256/1024 prompt runs (n_keys grows
        # depth+1..depth+64 during the timed window).
        depths.append(128)
        depths.append(256)
        depths.append(288)
        depths.append(512)
        depths.append(1024)
        depths.append(1056)

    var ns_per_tick = _calibrate_gpu_tick_ns(50)
    print("  calibrated ns/tick:", ns_per_tick)

    var n_desc = s.n_descriptors_decode_native_splitk
    if _mb_open_counters(2 * n_desc + 16) != 0:
        raise Error("tinyllama_probe_native: algenta_open_counters failed")
    var out_ticks = alloc[UInt64](2 * n_desc)

    var last_n_splits = -1
    # feat/metal-beat (2026-08-23): the kvprod-FUSED f2s4k table has 6 per-layer roles (the
    # kvprod dispatch is folded into the partial's prologue), the partial binds 18 args, and the
    # per-step `pos` patch lands on the partial's own arg 16 -- mirror `_step_native_kv_impl`.
    var stride = 6 if s.native_splitk_partial_kvfused else 7
    var partial_args = 18 if s.native_splitk_partial_kvfused else 14
    var pos_arg = 16 if s.native_splitk_partial_kvfused else 8

    for di in range(len(depths)):
        var n_keys = depths[di]
        var pos = n_keys - 1
        var table = s.descriptors_decode_native_splitk

        # ── per-step patching, byte-for-byte `_step_native_kv_impl`'s own (use_splitk branch) ──
        var n_splits_adapt = n_keys // 64
        if n_splits_adapt < _NATIVE_DECODE_N_SPLITS:
            n_splits_adapt = _NATIVE_DECODE_N_SPLITS
        if n_splits_adapt > s.native_splitk_derived_opt:
            n_splits_adapt = s.native_splitk_derived_opt
        if splits_override > 0:
            n_splits_adapt = splits_override
        if n_splits_adapt != last_n_splits:
            for lyr in range(n_layers):
                var d_partial = s.nkeys_offsets_native_splitk[lyr]
                _mb_set_header(
                    table, d_partial, s.native_splitk_partial_eff_idx,
                    s.h_q * n_splits_adapt, s.native_splitk_partial_eff_threads, partial_args,
                )
                _mb_set_arg_int(table, d_partial, 7, n_splits_adapt)
                _mb_set_arg_int(table, d_partial + 1, 4, n_splits_adapt)
            last_n_splits = n_splits_adapt
        _mb_set_arg_int(table, s.token_id_offset_native_splitk, 3, 0)
        for lyr in range(n_layers):
            _mb_set_arg_int(table, s.pos_offsets_native_splitk[lyr], pos_arg, pos)
            _mb_set_arg_int(table, s.nkeys_offsets_native_splitk[lyr], 6, n_keys)

        # Warm this exact table+depth untimed (production-shape single-encoder runs).
        for _w in range(3):
            var rc = _mb_run_token(table, n_desc)
            if rc != 0:
                raise Error("tinyllama_probe_native: warm run failed rc=" + String(rc))

        # Production-equivalent wall: untimed single-encoder runs (what _step_native_kv_impl does).
        var wall_prod_samples = List[Float64](capacity=n_samples)
        for _s in range(n_samples):
            var t0 = perf_counter_ns()
            var rc = _mb_run_token(table, n_desc)
            var t1 = perf_counter_ns()
            if rc != 0:
                raise Error("tinyllama_probe_native: production-shape run failed rc=" + String(rc))
            wall_prod_samples.append(Float64(Int(t1 - t0)) / 1.0e6)
        var wall_prod_med = _median(wall_prod_samples)

        # Instrumented runs: per-dispatch GPU timestamps (one encoder per dispatch).
        var wall_instr_samples = List[Float64](capacity=n_samples)
        var disp_samples = List[List[Float64]](capacity=n_desc)
        for d in range(n_desc):
            disp_samples.append(List[Float64](capacity=n_samples))
        for samp in range(n_samples):
            var t0 = perf_counter_ns()
            var rc = _mb_run_token_counters(table, n_desc, out_ticks)
            var t1 = perf_counter_ns()
            if rc != 0:
                raise Error("tinyllama_probe_native: run_token_counters failed rc=" + String(rc))
            wall_instr_samples.append(Float64(Int(t1 - t0)) / 1.0e6)
            for d in range(n_desc):
                var start_tick = out_ticks[2 * d]
                var end_tick = out_ticks[2 * d + 1]
                disp_samples[d].append(Float64(end_tick - start_tick) * ns_per_tick / 1.0e6)
        var wall_instr_med = _median(wall_instr_samples)

        # Role buckets.
        # 0 embed | 1 norm_gemv_qkv | 2 kvprod_native | 3 splitk_partial | 4 splitk_merge
        # | 5 o_proj | 6 norm_gemv2_swiglu | 7 down_proj | 8 lmhead_argmax | 9 argmax_reduce
        var role_names = List[String](capacity=10)
        role_names.append("embed")
        role_names.append("norm_gemv_qkv")
        role_names.append("kvprod_native")
        role_names.append("splitk_partial")
        role_names.append("splitk_merge")
        role_names.append("o_proj")
        role_names.append("norm_gemv2_swiglu")
        role_names.append("down_proj")
        role_names.append("lmhead_argmax")
        role_names.append("argmax_reduce")
        var role_sum = List[Float64](capacity=10)
        for r in range(10):
            role_sum.append(0.0)

        for d in range(n_desc):
            var med = _median(disp_samples[d])
            var role = 0
            if d == 0:
                role = 0
            elif d < 1 + n_layers * stride:
                var p = (d - 1) % stride
                if s.native_splitk_partial_kvfused:
                    # per-layer positions: norm_gemv_qkv | splitk_partial(f2s4k) | merge |
                    # o_proj | swiglu | down  -> map onto the classic role indices above.
                    if p == 0:
                        role = 1
                    elif p == 1:
                        role = 3
                    elif p == 2:
                        role = 4
                    else:
                        role = 2 + p  # 3->5 o_proj, 4->6 swiglu, 5->7 down
                else:
                    role = 1 + p
            elif d == n_desc - 2:
                role = 8
            else:
                role = 9
            role_sum[role] = role_sum[role] + med

        var gpu_sum = 0.0
        for r in range(10):
            gpu_sum = gpu_sum + role_sum[r]

        print("")
        print("DEPTH n_keys =", n_keys, " table = native-splitk(f2u2+merge)",
              " dispatches =", n_desc, " n_splits =", last_n_splits)
        print("  per-dispatch medians, layer 0 + tail:")
        for d in range(n_desc):
            if d <= stride or d >= 1 + n_layers * stride:
                print("    d=", d, " median_ms=", _median(disp_samples[d]))
        print("  per-role totals across the step (ms):")
        for r in range(10):
            if role_sum[r] > 0.0:
                print("    ", role_names[r], ":", role_sum[r])
        var gemm_sum = role_sum[1] + role_sum[5] + role_sum[6] + role_sum[7]
        var attn_sum = role_sum[3] + role_sum[4]
        print("  BUCKETS: gemv(+fused norms) =", gemm_sum,
              " | attention =", attn_sum,
              " | kvprod/rope =", role_sum[2],
              " | norms/embed/lmhead =", role_sum[0] + role_sum[8] + role_sum[9])
        print("  wall (production-shape, single encoder):", wall_prod_med, "ms")
        print("  wall (instrumented, one encoder/dispatch):", wall_instr_med, "ms")
        print("  GPU-sum:", gpu_sum, "ms")
        print("  gap (wall_prod - GPU-sum):", wall_prod_med - gpu_sum, "ms")
        print("  implied tok/s from production-shape wall:", 1000.0 / wall_prod_med)
