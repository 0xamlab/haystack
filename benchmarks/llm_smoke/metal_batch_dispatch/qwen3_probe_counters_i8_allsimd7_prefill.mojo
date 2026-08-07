"""qwen3_probe_counters_i8_allsimd7_prefill.mojo -- Phase 1's own measurement gate for the batched
prefill kernel family: does the flattened `_pf_attn_tiled_kernel_simd` (br=1) dispatch's MEASURED
GPU-time share track its ~0.1-6.7% FLOP share (per the implementation plan's own FLOP table), or does
it disproportionately dominate the way `_sdpa_kernel_simd`'s reduction shape did in decode before the
split-K fix? Same GPU-counter methodology as `qwen3_probe_counters_i8_allsimd7_splitk_deepctx.mojo`
(identical calibration, identical per-descriptor start/end tick sampling), retargeted at
`_MBQwen3I8AllSimd7Prefill.descriptors_prefill` at three real prompt lengths.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8_allsimd7_prefill.mojo \
        -o /tmp/probe_counters_prefill \
        -Xlinker /tmp/batch_shim_counters.o -Xlinker /tmp/mm8_blob.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/probe_counters_prefill
"""

from std.ffi import external_call
from std.memory import alloc
from std.builtin.type_aliases import MutAnyOrigin
from std.sys import has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_object, json_get_int, json_get_float
from attnk.rope import rope_table
from metaldispatch.contract import MB_OK, metaldispatch_status_name
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill, PREFILL_MAX_TILE

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime N_SAMPLES: Int = 8
"""Fewer reps than the decode counter probes (32) -- one prefill dispatch batch already spans
`1 + n_layers*6 + 2` descriptors covering up to 512 rows each, so a single sample is already far
more GPU work than one decode token; 8 keeps this probe's own wall time reasonable."""

comptime _R_EMBED: Int = 0
comptime _R_RMSNORM: Int = 1
comptime _R_GEMM_ASSIGN: Int = 2
comptime _R_ROPEWRT: Int = 3
comptime _R_ATTN: Int = 4
comptime _R_GEMV_O: Int = 5
comptime _R_RMSNORM2: Int = 6
comptime _R_SWIGLU: Int = 7
comptime _R_GEMV_DOWN: Int = 8
comptime _R_LMHEAD_ARGMAX: Int = 9
comptime _R_ARGMAX_REDUCE: Int = 10
comptime _N_ROLES_PREFILL: Int = 11


def _mb_counters_supported() -> Int:
    return Int(external_call["algenta_counters_supported", Int64]())


def _mb_timestamp_frequency() -> UInt64:
    return external_call["algenta_timestamp_frequency", UInt64]()


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
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill: GPU timestamp calibration did not advance")
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


def _role_name(role: Int) -> String:
    if role == _R_EMBED:
        return "pf_embed_rows"
    if role == _R_RMSNORM:
        return "pf_rmsnorm_rows"
    if role == _R_GEMM_ASSIGN:
        return "pf_gemm_assign (tiled GEMM, qkv_proj)"
    if role == _R_ROPEWRT:
        return "pf_ropewrt"
    if role == _R_ATTN:
        return "pf_attn_tiled (br=1)"
    if role == _R_GEMV_O:
        return "pf_gemm_accum (tiled GEMM, o_proj)"
    if role == _R_RMSNORM2:
        return "pf_rmsnorm_rows (ffn)"
    if role == _R_SWIGLU:
        return "pf_gemm_swiglu (tiled GEMM, fused gate+up)"
    if role == _R_GEMV_DOWN:
        return "pf_gemm_accum (tiled GEMM, down_proj)"
    if role == _R_LMHEAD_ARGMAX:
        return "lmhead_argmax (unmodified, row M-1)"
    if role == _R_ARGMAX_REDUCE:
        return "argmax_reduce (unmodified)"
    return "UNKNOWN"


def _build_role_table_prefill(n_layers: Int, n_descriptors: Int) raises -> List[Int]:
    var roles = List[Int](capacity=n_descriptors)
    roles.append(_R_EMBED)
    for _ in range(n_layers):
        roles.append(_R_RMSNORM)
        roles.append(_R_GEMM_ASSIGN)
        roles.append(_R_ROPEWRT)
        roles.append(_R_ATTN)
        roles.append(_R_GEMV_O)
        roles.append(_R_RMSNORM2)
        roles.append(_R_SWIGLU)
        roles.append(_R_GEMV_DOWN)
    roles.append(_R_LMHEAD_ARGMAX)
    roles.append(_R_ARGMAX_REDUCE)
    if len(roles) != n_descriptors:
        raise Error(
            "qwen3_probe_counters_i8_allsimd7_prefill: built " + String(len(roles)) + " role slots but "
            + "the session says " + String(n_descriptors) + " descriptors"
        )
    return roles^


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _check_mb(status: Int) raises:
    if status != MB_OK:
        raise Error(
            "qwen3_probe_counters_i8_allsimd7_prefill: metaldispatch call failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
        )


def _sample_at_m_rows(
    mut s: _MBQwen3I8AllSimd7Prefill,
    m_rows: Int,
    n_layers: Int,
    n_descriptors: Int,
    roles: List[Int],
    ns_per_tick: Float64,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
    mut role_avg_ms_out: List[Float64],
) raises -> Float64:
    var role_total_ns = List[Float64](capacity=_N_ROLES_PREFILL)
    for _ in range(_N_ROLES_PREFILL):
        role_total_ns.append(0.0)
    s._apply_m_rows(m_rows, 0)
    var ids_i32 = s.prompt_ids_ptr.bitcast[Int32]()
    for m in range(m_rows):
        ids_i32[m] = Int32(13)  # any valid vocab id -- correctness is not this probe's question
    var wall_total_ms = 0.0
    for _ in range(N_SAMPLES):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors_prefill, n_descriptors, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd7_prefill: algenta_run_token_counters failed")
        wall_total_ms += Float64(Int(t1 - t0)) / 1.0e6
        for d in range(n_descriptors):
            var start_tick = out_ticks[2 * d]
            var end_tick = out_ticks[2 * d + 1]
            if end_tick >= start_tick:
                role_total_ns[roles[d]] += Float64(end_tick - start_tick) * ns_per_tick
    for role in range(_N_ROLES_PREFILL):
        role_avg_ms_out[role] = role_total_ns[role] / Float64(N_SAMPLES) / 1.0e6
    return wall_total_ms / Float64(N_SAMPLES)


def main() raises:
    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var theta = json_get_float(config, "rope_theta", -1.0)
    var eps = json_get_float(config, "rms_norm_eps", -1.0)
    var n_prompt = json_get_int(config, "n_tokens", -1)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1 or n_prompt < 1:
        raise Error("qwen3_probe_counters_i8_allsimd7_prefill: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))
    var max_ctx = 8192

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 2, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_probe_counters_i8_allsimd7_prefill: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_probe_counters_i8_allsimd7_prefill: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_probe_counters_i8_allsimd7_prefill: no accelerator on this host")
            return

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _MBQwen3I8AllSimd7Prefill(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        print("  n_cores detected:", s.n_cores)

        var rt = rope_table(d_head, max_ctx, theta)
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check_mb(s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx))

        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "input_layernorm.weight")
            var ln2 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "post_attention_layernorm.weight")
            var qn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_norm.weight")
            var kn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_norm.weight")
            var wq = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_proj.weight")
            var wk = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_proj.weight")
            var wv = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.v_proj.weight")
            var wo = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.o_proj.weight")
            var wg = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.gate_proj.weight")
            var wu = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.up_proj.weight")
            var wd = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.down_proj.weight")
            _check_mb(s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd))
        _ = s.seal()
        print("  weights loaded + sealed")

        # `_ensure_deep_initialized`'s compile_function_unchecked calls are what makes the two
        # split-K kernels statically reachable from THIS binary's own main() -- shader embedding is
        # a whole-binary, compile-time decision, independent of whether this call actually runs
        # before `_mb_open_session()`'s scan (it does, chronologically, since `__init__` already ran
        # above) -- see `_MBQwen3I8AllSimd7Prefill.__init__`'s own unconditional pipeline_idx_split/
        # merge check, which every construction of this struct must satisfy, exactly mirroring
        # `qwen3_probe_counters_i8_allsimd7_splitk_deepctx.mojo`'s own identical call.
        s._ensure_deep_initialized()

        var roles = _build_role_table_prefill(n_layers, s.n_descriptors_prefill)

        var supported = _mb_counters_supported()
        if supported != 1:
            print("qwen3_probe_counters_i8_allsimd7_prefill: counter sampling not available, status=", supported)
            return
        var ns_per_tick = _calibrate_gpu_tick_ns(200)
        print("  calibrated ns/tick:", ns_per_tick)
        var counters_rc = _mb_open_counters(2 * s.n_descriptors_prefill)
        if counters_rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd7_prefill: algenta_open_counters failed, rc=" + String(counters_rc))
        var out_ticks = alloc[UInt64](2 * s.n_descriptors_prefill)

        # 32 and 256 added for the Attention Compiler Plan's Phase 0A: the headline RealRace runs a
        # 256-token prompt, so the Amdahl-law attention share that calibrates every speedup target
        # (f_256) must come from m_rows=256, not be extrapolated from the 128/512 endpoints.
        var m_values = List[Int]()
        m_values.append(8)
        m_values.append(32)
        m_values.append(128)
        m_values.append(256)
        m_values.append(512)

        for mi in range(len(m_values)):
            var m_rows = m_values[mi]
            print("")
            print("=== sampling at m_rows=", m_rows, "(", N_SAMPLES, "reps) ===")
            var role_ms = List[Float64](capacity=_N_ROLES_PREFILL)
            for _ in range(_N_ROLES_PREFILL):
                role_ms.append(0.0)
            var wall_ms = _sample_at_m_rows(
                s, m_rows, n_layers, s.n_descriptors_prefill, roles, ns_per_tick, out_ticks, role_ms
            )
            var total_ms = 0.0
            for role in range(_N_ROLES_PREFILL):
                total_ms += role_ms[role]
            for role in range(_N_ROLES_PREFILL):
                var pct = (role_ms[role] / total_ms * 100.0) if total_ms > 1.0e-9 else -1.0
                print("  ", _role_name(role), ":", role_ms[role], "ms  (", pct, "% of GPU-time total)")
            print("  TOTAL (sum of per-dispatch GPU time):", total_ms, "ms")
            print("  whole-batch wall time (host-measured):", wall_ms, "ms")
            var tok_per_sec = Float64(m_rows) / (wall_ms / 1000.0)
            print("  implied tok/s at this m_rows in isolation:", tok_per_sec)
