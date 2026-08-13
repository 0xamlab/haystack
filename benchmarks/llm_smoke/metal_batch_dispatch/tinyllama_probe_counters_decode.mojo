"""tinyllama_probe_counters_decode.mojo -- per-role GPU-counter breakdown of ONE TinyLlama
SINGLE-STREAM decode step on the LEGACY parametric path, adapted from
`qwen3_probe_counters_decode_batched.mojo` (same GPU-counter methodology, unmodified counter shim
`batch_shim_counters.m`).

WHY THE LEGACY PATH: TinyLlama-1.1B (d_head=64, no QK-norm) is gated off the attention-forge/
native fast path (`af_grouped_fa_available` requires d_head == _AF_STRUCTURAL_D_HEAD and
qk_norm == 1), so `_MBQwen3I8AllSimd7Prefill` degrades it onto the runtime-parametric path:
PF_ATTN_OFF prefill + legacy `_sdpa_kernel_simd` decode (`_step_legacy_impl`). That is the path
this probe dissects.

TWO descriptor tables exist on the legacy path (`_step_legacy_impl`'s own router):
  - NAIVE table  (`self.descriptors`,      1 + 6*n_layers + 2 dispatches) for n_keys < 32
  - DEEP table   (`self.descriptors_deep`, 1 + 7*n_layers + 2 dispatches) for n_keys >= 32
    (residentk_splitk_should_split gate, RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS = 32; the deep table
    replaces the single sdpa dispatch with the split-K partial + merge pair)
Roles per layer, NAIVE: [norm_gemv(rms1+qkv GEMV), qk_rope_write(rope+KV-write), sdpa,
gemv_accum(o_proj), norm_gemv2_swiglu(rms2+gate/up+swiglu), gemv_accum(down_proj)].
DEEP swaps sdpa -> [splitk_partial, splitk_merge]. Tail: lmhead_argmax (fused final rmsnorm +
lm_head + per-block argmax), argmax_reduce.

WEIGHTS: loaded from the SDK's quantized-state cache (weights_i8.cache -- the exact post-
quantization device bytes the production warm path restores), header-verified (magic + manifest
SHA-256 + dims + length). KV caches hold whatever allocation left there: timing is shape-driven,
value-independent (same rationale as the batched probe).

    argv[1] = timed samples per depth (default 7)
    argv[2] = optional single n_keys depth to measure (default: full sweep)

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      xcrun --sdk macosx clang -c -fobjc-arc -O2 \
        ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/probe_tinyllama/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -D ALGENTA_STAGE_6144 -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/tinyllama_probe_counters_decode.mojo \
        -o /tmp/probe_tinyllama/tinyllama_probe_counters_decode \
        -Xlinker /tmp/probe_tinyllama/batch_shim_counters.o \
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \
        -Xlinker -framework -Xlinker IOKit
    /tmp/probe_tinyllama/tinyllama_probe_counters_decode 7
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
from metaldispatch.ffi import _mb_run_token, _mb_set_arg_int
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill
from metaldispatch.session_prefill_policy import (
    PF_ATTN_OFF,
    PF_GEMM_ORIGINAL,
    UnresolvedPrefillConfig,
)
from residentk.contract import (
    residentk_splitk_should_split,
    residentk_splitk_policy,
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
    var deadline = t_wall0 + UInt(hold_ms) * 1_000_000
    while perf_counter_ns() < deadline:
        pass
    var gpu1 = _mb_sample_gpu_timestamp()
    var t_wall1 = perf_counter_ns()
    if gpu1 <= gpu0:
        raise Error("tinyllama_probe: GPU timestamp calibration did not advance")
    var wall_seconds = Float64(Int(t_wall1 - t_wall0)) / 1.0e9
    var tick_rate_hz = Float64(gpu1 - gpu0) / wall_seconds
    return 1.0e9 / tick_rate_hz


def _mb_open_counters(max_samples: Int) -> Int:
    return Int(external_call["algenta_open_counters", Int64, Int64](Int64(max_samples)))


def _mb_run_token_counters(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin],
    n: Int,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
) -> Int:
    return Int(
        external_call[
            "algenta_run_token_counters", Int64,
            UnsafePointer[UInt8, origin=MutAnyOrigin], Int64,
            UnsafePointer[UInt64, origin=MutAnyOrigin],
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
    if len(args) > 1:
        n_samples = parse_int(String(args[1]))
    if len(args) > 2:
        single_depth = parse_int(String(args[2]))

    if not MB_GPU_BUILD:
        raise Error("tinyllama_probe: not a GPU build")
    if _mb_counters_supported() == 0:
        raise Error("tinyllama_probe: counter sampling unsupported on this device")

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

    print("tinyllama_probe: d_model =", d_model, "h_q =", h_q, "h_kv =", h_kv,
          "d_head =", d_head, "d_ff =", d_ff, "layers =", n_layers,
          "vocab =", vocab_size, "qk_norm =", has_qk_norm, "tied =", tied)

    var s = _MBQwen3I8AllSimd7Prefill(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale,
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
        qk_norm=has_qk_norm, tied_embeddings=tied,
    )
    print("  resolved plan: attention =", s.plan.attention, " gemm =", s.plan.gemm,
          " decode =", s.plan.decode)
    print("  n_cores =", s.n_cores, " n_descriptors(naive) =", s.n_descriptors,
          " n_descriptors_deep =", s.n_descriptors_deep)

    # ── weights: the production warm path's quantized-state cache ───────────────────────────
    var cf = open(CACHE_PATH, "r")
    var header = cf.read_bytes(HEADER_BYTES)
    if len(header) != HEADER_BYTES:
        cf.close()
        raise Error("tinyllama_probe: cache header short read")
    var magic_ok = (
        header[0] == 65 and header[1] == 76 and header[2] == 71 and header[3] == 73
        and header[4] == 56 and header[5] == 67 and header[6] == 48 and header[7] == 49
    )
    if not magic_ok:
        cf.close()
        raise Error("tinyllama_probe: cache magic mismatch")
    if _le64(header, 40) != n_layers or _le64(header, 48) != d_model
        or _le64(header, 56) != h_q or _le64(header, 64) != h_kv
        or _le64(header, 72) != d_head or _le64(header, 80) != d_ff
        or _le64(header, 88) != vocab_size:
        cf.close()
        raise Error("tinyllama_probe: cache dims disagree with manifest")
    var digest = _sha256_of_string(manifest)
    for i in range(32):
        if Int(header[8 + i]) != digest[i]:
            cf.close()
            raise Error("tinyllama_probe: cache manifest-sha256 mismatch")
    var state_len = _le64(header, 96)
    if state_len != s.quantized_state_bytes():
        cf.close()
        raise Error(
            "tinyllama_probe: cache state length " + String(state_len)
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
            raise Error("tinyllama_probe: cache short read")
        for i in range(take):
            state.append(chunk[i])
        remaining -= take
    cf.close()
    var ls = s.load_quantized_state(state^)
    if ls != MB_OK:
        raise Error(
            "tinyllama_probe: load_quantized_state failed: " + metaldispatch_status_name(ls)
        )
    var rt = rope_table(d_head, MAX_CTX, theta)
    var rs = s.upload_rope_tables(rt.cos_table, rt.sin_table, MAX_CTX)
    if rs != MB_OK:
        raise Error(
            "tinyllama_probe: upload_rope_tables failed: " + metaldispatch_status_name(rs)
        )
    _ = s.seal()
    print("  weights loaded from quantized-state cache + rope tables uploaded")

    # ── depth list ──────────────────────────────────────────────────────────────────────────
    var depths = List[Int]()
    if single_depth > 0:
        depths.append(single_depth)
    else:
        # NAIVE-table depths (n_keys < 32): the short-prompt decode regime (the ledger's 174
        # tok/s was a 6-token prompt generation: first steps are n_keys = 7..).
        depths.append(7)
        depths.append(16)
        depths.append(31)
        # DEEP-table depths (n_keys >= 32): split-K attention regime.
        depths.append(32)
        depths.append(64)
        depths.append(128)
        depths.append(288)
        depths.append(1056)

    # Warm both tables untimed (pipelines' first-dispatch + DVFS ramp), same convention as the
    # batched probe. Deep init is lazy in the session; make it reachable + warm it here.
    s._ensure_deep_initialized()

    var ns_per_tick = _calibrate_gpu_tick_ns(50)
    print("  calibrated ns/tick:", ns_per_tick)

    var max_desc = s.n_descriptors_deep if s.n_descriptors_deep > s.n_descriptors else s.n_descriptors
    if _mb_open_counters(2 * max_desc + 16) != 0:
        raise Error("tinyllama_probe: algenta_open_counters failed")
    var out_ticks = alloc[UInt64](2 * max_desc)

    var last_n_splits = -1

    for di in range(len(depths)):
        var n_keys = depths[di]
        var pos = n_keys - 1
        var deep = residentk_splitk_should_split(n_keys)
        var n_desc = s.n_descriptors_deep if deep else s.n_descriptors
        var table = s.descriptors_deep if deep else s.descriptors

        if deep:
            var n_splits = residentk_splitk_policy(n_keys, s.n_cores, s.h_q)
            if n_splits != last_n_splits:
                s._apply_n_splits(n_splits)
                last_n_splits = n_splits
            _mb_set_arg_int(s.descriptors_deep, s.token_id_offset_deep, 3, 0)
            for layer in range(n_layers):
                _mb_set_arg_int(s.descriptors_deep, s.pos_offsets_deep[layer], 8, pos)
                _mb_set_arg_int(s.descriptors_deep, s.nkeys_offsets_deep[layer], 6, n_keys)
        else:
            _mb_set_arg_int(s.descriptors, s.token_id_offset, 3, 0)
            for layer in range(n_layers):
                _mb_set_arg_int(s.descriptors, s.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(s.descriptors, s.nkeys_offsets[layer], 4, n_keys)

        # Warm this exact table+depth untimed (production-shape single-encoder runs).
        for _w in range(3):
            var rc = _mb_run_token(table, n_desc)
            if rc != 0:
                raise Error("tinyllama_probe: warm run failed rc=" + String(rc))

        # Production-equivalent wall: untimed single-encoder runs (what _step_legacy_impl does).
        var wall_prod_samples = List[Float64](capacity=n_samples)
        for _s in range(n_samples):
            var t0 = perf_counter_ns()
            var rc = _mb_run_token(table, n_desc)
            var t1 = perf_counter_ns()
            if rc != 0:
                raise Error("tinyllama_probe: production-shape run failed rc=" + String(rc))
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
                raise Error("tinyllama_probe: run_token_counters failed rc=" + String(rc))
            wall_instr_samples.append(Float64(Int(t1 - t0)) / 1.0e6)
            for d in range(n_desc):
                var start_tick = out_ticks[2 * d]
                var end_tick = out_ticks[2 * d + 1]
                disp_samples[d].append(Float64(end_tick - start_tick) * ns_per_tick / 1.0e6)
        var wall_instr_med = _median(wall_instr_samples)

        # Role buckets.
        var stride = 7 if deep else 6
        # 0 embed | 1 norm_gemv(qkv) | 2 qk_rope | 3 sdpa | 4 splitk_partial | 5 splitk_merge
        # | 6 o_proj | 7 norm_gemv2_swiglu | 8 down_proj | 9 lmhead_argmax | 10 argmax_reduce
        var role_names = List[String](capacity=11)
        role_names.append("embed")
        role_names.append("norm_gemv_qkv")
        role_names.append("qk_rope_kvwrite")
        role_names.append("sdpa")
        role_names.append("splitk_partial")
        role_names.append("splitk_merge")
        role_names.append("o_proj")
        role_names.append("norm_gemv2_swiglu")
        role_names.append("down_proj")
        role_names.append("lmhead_argmax")
        role_names.append("argmax_reduce")
        var role_sum = List[Float64](capacity=11)
        for r in range(11):
            role_sum.append(0.0)

        for d in range(n_desc):
            var med = _median(disp_samples[d])
            var role = 0
            if d == 0:
                role = 0
            elif d < 1 + n_layers * stride:
                var p = (d - 1) % stride
                if deep:
                    # [norm_gemv, qk_rope, splitk_partial, splitk_merge, o, swiglu, down]
                    role = 1 + p if p < 2 else p + 2
                else:
                    # [norm_gemv, qk_rope, sdpa, o, swiglu, down]
                    # p=0->1, p=1->2, p=2->3(sdpa), p=3->6(o), p=4->7, p=5->8
                    if p == 0:
                        role = 1
                    elif p == 1:
                        role = 2
                    elif p == 2:
                        role = 3
                    elif p == 3:
                        role = 6
                    elif p == 4:
                        role = 7
                    else:
                        role = 8
            elif d == n_desc - 2:
                role = 9
            else:
                role = 10
            role_sum[role] = role_sum[role] + med

        var gpu_sum = 0.0
        for r in range(11):
            gpu_sum = gpu_sum + role_sum[r]

        print("")
        print("DEPTH n_keys =", n_keys, " table =", "deep(split-K)" if deep else "naive(sdpa)",
              " dispatches =", n_desc,
              " n_splits =", last_n_splits if deep else 0)
        print("  per-dispatch medians, layer 0 + tail:")
        for d in range(n_desc):
            if d <= stride or d >= 1 + n_layers * stride:
                print("    d=", d, " median_ms=", _median(disp_samples[d]))
        print("  per-role totals across the step (ms):")
        for r in range(11):
            if role_sum[r] > 0.0:
                print("    ", role_names[r], ":", role_sum[r])
        var gemm_sum = role_sum[1] + role_sum[6] + role_sum[7] + role_sum[8]
        var attn_sum = role_sum[3] + role_sum[4] + role_sum[5]
        print("  BUCKETS: gemm(+fused norms) =", gemm_sum,
              " | attention =", attn_sum,
              " | kvprod/rope =", role_sum[2],
              " | norms/embed/lmhead =", role_sum[0] + role_sum[9] + role_sum[10])
        print("  wall (production-shape, single encoder):", wall_prod_med, "ms")
        print("  wall (instrumented, one encoder/dispatch):", wall_instr_med, "ms")
        print("  GPU-sum:", gpu_sum, "ms")
        print("  gap (instrumented wall - GPU-sum):", wall_instr_med - gpu_sum, "ms")
        print("  implied tok/s from production-shape wall:", 1000.0 / wall_prod_med)
