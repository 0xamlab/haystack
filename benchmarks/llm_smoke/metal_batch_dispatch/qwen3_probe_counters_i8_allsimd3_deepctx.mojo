"""qwen3_probe_counters_i8_allsimd3_deepctx.mojo — DIAGNOSTIC-ONLY per-dispatch GPU timing for the
standing-best race arm (`_MBQwen3I8AllSimd3`), sampled at TWO chosen KV-cache positions (a shallow
one and a deep one, both given on argv) instead of only the shallow 5-19 range every other counters
probe in this directory replays. Built for exactly one question the long-context race raised: when
per-token decode time grows with position, WHICH of the 8 dispatch roles is responsible — only
`sdpa` (expected: it is the one role whose own work is `O(pos)` by design, reading further into the
KV cache as the cache grows) or something else too (which would mean a cost this design's own
docstring says should not exist).

Methodology: reuses `qwen3_probe_counters_i8_sdpasimd.mojo`'s own counter-sampling machinery
(`batch_shim_counters.m`, `algenta_run_token_counters`, GPU-tick calibration) and role table
unchanged (the two files' role layouts are IDENTICAL — `_MBQwen3I8AllSimd3` differs from
`_MBQwen3I8SDPASimd` only in which kernel the `argmax_reduce` role dispatches to, not in the layout
or count of the 171 descriptor slots), but does NOT replay a short recorded sequence. Instead, for
each of the two requested positions `pos`, it directly overwrites every layer's `pos_offset` and
`nkeys_offset` descriptor argument (`_mb_set_arg_int`, the exact mechanism
`qwen3_probe_counters_i8_sdpasimd.mojo`'s own ON-phase already uses) to `pos` / `pos + 1` and
dispatches `N_SAMPLES` times, averaging. This is safe and race-methodology-consistent with that
file's own module docstring: `_sdpa_kernel_simd` for a query at position `pos` only ever reads keys
`[0, pos]`; rewriting the SAME slot with SAME/garbage bytes repeatedly is deterministic and does not
depend on those slots holding a real generation's actual content — only `pos` (and therefore how
much of the cache the `sdpa` dispatch reads) is asked to vary, which is exactly what this probe is
measuring the cost of. `max_ctx` must be large enough to hold the deeper of the two requested
positions (session opened at argv[3], defaulting to 8192).

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8_allsimd3_deepctx.mojo \
        -o /tmp/qwen3_probe_counters_i8_allsimd3_deepctx \
        -Xlinker /tmp/batch_shim_counters.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      /tmp/qwen3_probe_counters_i8_allsimd3_deepctx 20 4000 8192
"""

from std.ffi import external_call
from std.memory import alloc
from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from std.sys import argv, has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_DEFAULT_CONTEXT
from metaldispatch.contract import MB_OK, metaldispatch_dispatch_budget, metaldispatch_status_name
from metaldispatch.session import _MBQwen3I8AllSimd3, _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import _mb_set_arg_int, MB_DESC_STRIDE

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime N_SAMPLES: Int = 32
"""Dispatch-and-sample repetitions per requested position, averaged for stability."""

comptime _R_EMBED: Int = 0
comptime _R_NORM_GEMV: Int = 1
comptime _R_GEMV_ACCUM: Int = 2
comptime _R_NORM_GEMV2_SWIGLU: Int = 3
comptime _R_QK_ROPE: Int = 4
comptime _R_SDPA: Int = 5
comptime _R_LMHEAD_ARGMAX: Int = 6
comptime _R_ARGMAX_REDUCE: Int = 7


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
        raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: GPU timestamp calibration did not advance")
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
        return "embed_row"
    if role == _R_NORM_GEMV:
        return "norm_gemv (QKV-proj)"
    if role == _R_GEMV_ACCUM:
        return "gemv_accum"
    if role == _R_NORM_GEMV2_SWIGLU:
        return "norm_gemv2_swiglu (gate-up)"
    if role == _R_QK_ROPE:
        return "qk_rope_write"
    if role == _R_SDPA:
        return "sdpa"
    if role == _R_LMHEAD_ARGMAX:
        return "lmhead_argmax"
    if role == _R_ARGMAX_REDUCE:
        return "argmax_reduce"
    return "UNKNOWN"


def _build_role_table(n_layers: Int, n_descriptors: Int) raises -> List[Int]:
    var roles = List[Int](capacity=n_descriptors)
    roles.append(_R_EMBED)
    for _ in range(n_layers):
        roles.append(_R_NORM_GEMV)
        roles.append(_R_QK_ROPE)
        roles.append(_R_SDPA)
        roles.append(_R_GEMV_ACCUM)
        roles.append(_R_NORM_GEMV2_SWIGLU)
        roles.append(_R_GEMV_ACCUM)
    roles.append(_R_LMHEAD_ARGMAX)
    roles.append(_R_ARGMAX_REDUCE)
    if len(roles) != n_descriptors:
        raise Error(
            "qwen3_probe_counters_i8_allsimd3_deepctx: built " + String(len(roles)) + " role slots but the "
            + "session says " + String(n_descriptors) + " descriptors"
        )
    return roles^


def _verify_role_table(mut s: _MBQwen3I8AllSimd3, roles: List[Int]) raises:
    for d in range(len(roles)):
        var stored = Int((s.descriptors + d * MB_DESC_STRIDE).bitcast[Int32]()[0])
        var expected = s.pipeline_idx[roles[d]]
        if stored != expected:
            raise Error(
                "qwen3_probe_counters_i8_allsimd3_deepctx: slot " + String(d) + " role table says pipeline "
                + String(expected) + " but the descriptor holds " + String(stored)
            )


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
        raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: short read at byte offset " + String(byte_offset))
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
            "qwen3_probe_counters_i8_allsimd3_deepctx: metaldispatch call failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
        )


def _sample_at_position(
    mut s: _MBQwen3I8AllSimd3,
    pos: Int,
    n_layers: Int,
    n_descriptors: Int,
    roles: List[Int],
    ns_per_tick: Float64,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
    mut role_avg_ms_out: List[Float64],
) raises -> Float64:
    """Dispatches `N_SAMPLES` full tokens with EVERY layer's pos/nkeys forced to `pos`, fills
    `role_avg_ms_out` (per-role avg ms summed across layers/token) and returns whole-token avg wall
    ms."""
    var role_total_ns = List[Float64](capacity=8)
    for _ in range(8):
        role_total_ns.append(0.0)
    var n_keys = pos + 1
    _mb_set_arg_int(s.descriptors, s.token_id_offset, 3, 13)  # any valid vocab id; not used for timing
    for layer in range(n_layers):
        _mb_set_arg_int(s.descriptors, s.pos_offsets[layer], 8, pos)
        _mb_set_arg_int(s.descriptors, s.nkeys_offsets[layer], 4, n_keys)
    var wall_total_ms = 0.0
    for _ in range(N_SAMPLES):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors, n_descriptors, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: algenta_run_token_counters failed")
        wall_total_ms += Float64(Int(t1 - t0)) / 1.0e6
        for d in range(n_descriptors):
            var start_tick = out_ticks[2 * d]
            var end_tick = out_ticks[2 * d + 1]
            if end_tick >= start_tick:
                role_total_ns[roles[d]] += Float64(end_tick - start_tick) * ns_per_tick
    for role in range(8):
        role_avg_ms_out[role] = role_total_ns[role] / Float64(N_SAMPLES) / 1.0e6
    return wall_total_ms / Float64(N_SAMPLES)


def main() raises:
    var args = argv()
    var pos_shallow = 20
    var pos_deep = 4000
    var max_ctx = 8192
    if len(args) > 1:
        pos_shallow = parse_int(String(args[1]))
    if len(args) > 2:
        pos_deep = parse_int(String(args[2]))
    if len(args) > 3:
        max_ctx = parse_int(String(args[3]))

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
        raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))

    print("qwen3_probe_counters_i8_allsimd3_deepctx: pos_shallow=", pos_shallow, "pos_deep=", pos_deep,
          "max_ctx=", max_ctx, "n_layers=", n_layers)

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 2, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_probe_counters_i8_allsimd3_deepctx: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_probe_counters_i8_allsimd3_deepctx: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_probe_counters_i8_allsimd3_deepctx: no accelerator on this host")
            return
        if pos_deep >= max_ctx:
            raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: pos_deep must be < max_ctx")

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _MBQwen3I8AllSimd3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale
        )
        print("  device:", s.device_name())

        var rt = rope_table(d_head, max_ctx, theta)
        _ = ATTN_OK
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

        var roles = _build_role_table(n_layers, s.n_descriptors)
        _verify_role_table(s, roles)
        print("  role table verified against", s.n_descriptors, "descriptor slots (0 mismatches)")

        var supported = _mb_counters_supported()
        if supported != 1:
            print("qwen3_probe_counters_i8_allsimd3_deepctx: counter sampling not available, status=", supported)
            return
        var ns_per_tick = _calibrate_gpu_tick_ns(200)
        print("  calibrated ns/tick:", ns_per_tick)
        var counters_rc = _mb_open_counters(2 * s.n_descriptors)
        if counters_rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd3_deepctx: algenta_open_counters failed, rc=" + String(counters_rc))
        var out_ticks = alloc[UInt64](2 * s.n_descriptors)

        print("")
        print("═══ sampling at pos_shallow=", pos_shallow, "(", N_SAMPLES, "reps) ═══")
        var shallow_roles = List[Float64](capacity=8)
        for _ in range(8):
            shallow_roles.append(0.0)
        var shallow_wall = _sample_at_position(
            s, pos_shallow, n_layers, s.n_descriptors, roles, ns_per_tick, out_ticks, shallow_roles
        )

        print("═══ sampling at pos_deep=   ", pos_deep, "(", N_SAMPLES, "reps) ═══")
        var deep_roles = List[Float64](capacity=8)
        for _ in range(8):
            deep_roles.append(0.0)
        var deep_wall = _sample_at_position(
            s, pos_deep, n_layers, s.n_descriptors, roles, ns_per_tick, out_ticks, deep_roles
        )

        print("")
        print("═══ per-role GPU dispatch time, summed over all", n_layers, "layers -- shallow vs deep ═══")
        var shallow_total = 0.0
        var deep_total = 0.0
        for role in range(8):
            shallow_total += shallow_roles[role]
            deep_total += deep_roles[role]
        for role in range(8):
            var ratio = (deep_roles[role] / shallow_roles[role]) if shallow_roles[role] > 1.0e-9 else -1.0
            print("  ", _role_name(role), ": shallow=", shallow_roles[role], "ms  deep=", deep_roles[role],
                  "ms  deep/shallow ratio=", ratio)
        print("  TOTAL (sum of per-dispatch GPU time): shallow=", shallow_total, "ms  deep=", deep_total,
              "ms  ratio=", deep_total / shallow_total)
        print("")
        print("  whole-token wall time (host-measured, includes dispatch overhead + resolveCounterRange):")
        print("    shallow pos=", pos_shallow, ":", shallow_wall, "ms")
        print("    deep    pos=", pos_deep, ":", deep_wall, "ms")
