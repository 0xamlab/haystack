"""qwen3_probe_counters_i8_allsimd6_splitk_deepctx.mojo — the WIDENED-SPLIT (Candidate 1) twin of
`qwen3_probe_counters_i8_allsimd3_splitk_deepctx.mojo` (and the widened-`n_splits` twin of `qwen3_
probe_counters_i8_allsimd5_splitk_deepctx.mojo`): byte-for-byte that file's own methodology (same
`_sample_at_position` shape, same two-position shallow/deep comparison, same GPU-tick calibration,
same per-role breakdown), retargeted at `_MBQwen3I8AllSimd6`'s deep-context descriptor table instead
of `_MBQwen3I8AllSimd3`'s — `_build_descriptors_deep`'s PLAN is otherwise identical between the two
structs (same roles, same order, same argument layout: `_splitk_partial` + `splitk_merge` in place of
the one `sdpa` dispatch, 7 descriptors/layer against the shallow table's 6), with TWO differences:
`splitk_partial`'s own `block_dim` header is `WARP_SIZE` here, not `d_head` (inherited from
`_MBQwen3I8AllSimd5`), AND its grid width is `h_q * _ATTN_SPLITK_N_SPLITS_NATIVE` (80), not `h_q *
_ATTN_SPLITK_N_SPLITS` (16) — this file's own addition, the thing this probe exists to measure.
Running this probe and `qwen3_probe_counters_i8_allsimd3_splitk_deepctx.mojo` (and, for the full
three-way comparison, `qwen3_probe_counters_i8_allsimd5_splitk_deepctx.mojo`) back to back at the
SAME position is this task's own GPU-counter role-level self-comparison: any change in the `splitk_
partial`/`splitk_merge` roles' own GPU time is directly attributable to the widened split count,
since nothing else about the descriptor table, the buffers, or the math differs. See `_ATTN_SPLITK_
N_SPLITS_NATIVE`'s own docstring (`metaldispatch.session`) for the sweep that picked 80 and the full
three-way numbers this probe itself produced.

`s.descriptors_deep` is now built LAZILY (`_MBQwen3I8AllSimd6._ensure_deep_initialized`, called from
`step()`'s own deep branch on first crossing `_ATTN_SPLITK_THRESHOLD` — inherited unchanged from
`_MBQwen3I8AllSimd3`'s own lazy-init fix, sized off `_ATTN_SPLITK_N_SPLITS_NATIVE` instead of `_ATTN_
SPLITK_N_SPLITS`). This probe reaches into `s.descriptors_deep` directly, bypassing `step()` entirely,
so it calls `s._ensure_deep_initialized()` itself, right after weights are uploaded/sealed and before
building the role table -- otherwise `s.descriptors_deep` would still be the null placeholder
`__init__` leaves it at.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_i8_allsimd6_splitk_deepctx.mojo \
        -o /tmp/qwen3_probe_counters_i8_allsimd6_splitk_deepctx \
        -Xlinker /tmp/batch_shim_counters.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      /tmp/qwen3_probe_counters_i8_allsimd6_splitk_deepctx 20 4000 8192
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
from metaldispatch.session import _MBQwen3I8AllSimd6, _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import _mb_set_arg_int, MB_DESC_STRIDE

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime N_SAMPLES: Int = 32
"""Dispatch-and-sample repetitions per requested position, averaged for stability — same as the
original counters probe."""

comptime _R_EMBED: Int = 0
comptime _R_NORM_GEMV: Int = 1
comptime _R_GEMV_ACCUM: Int = 2
comptime _R_NORM_GEMV2_SWIGLU: Int = 3
comptime _R_QK_ROPE: Int = 4
comptime _R_SPLITK_PARTIAL: Int = 5
comptime _R_SPLITK_MERGE: Int = 6
comptime _R_LMHEAD_ARGMAX: Int = 7
comptime _R_ARGMAX_REDUCE: Int = 8
comptime _N_ROLES_DEEP: Int = 9
"""ONE more role than the original probe's 8: the single `sdpa` role there is `splitk_partial` PLUS
`splitk_merge` here — everything else is the same six roles, same order."""


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
        raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: GPU timestamp calibration did not advance")
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
    if role == _R_SPLITK_PARTIAL:
        return "splitk_partial (the split half of the deep-ctx SDPA fix)"
    if role == _R_SPLITK_MERGE:
        return "splitk_merge (the merge half of the deep-ctx SDPA fix)"
    if role == _R_LMHEAD_ARGMAX:
        return "lmhead_argmax"
    if role == _R_ARGMAX_REDUCE:
        return "argmax_reduce"
    return "UNKNOWN"


def _build_role_table_deep(n_layers: Int, n_descriptors: Int) raises -> List[Int]:
    var roles = List[Int](capacity=n_descriptors)
    roles.append(_R_EMBED)
    for _ in range(n_layers):
        roles.append(_R_NORM_GEMV)
        roles.append(_R_QK_ROPE)
        roles.append(_R_SPLITK_PARTIAL)
        roles.append(_R_SPLITK_MERGE)
        roles.append(_R_GEMV_ACCUM)
        roles.append(_R_NORM_GEMV2_SWIGLU)
        roles.append(_R_GEMV_ACCUM)
    roles.append(_R_LMHEAD_ARGMAX)
    roles.append(_R_ARGMAX_REDUCE)
    if len(roles) != n_descriptors:
        raise Error(
            "qwen3_probe_counters_i8_allsimd6_splitk_deepctx: built " + String(len(roles)) + " role slots but "
            + "the session says " + String(n_descriptors) + " descriptors"
        )
    return roles^


def _verify_role_table_deep(mut s: _MBQwen3I8AllSimd6, roles: List[Int]) raises:
    for d in range(len(roles)):
        var stored = Int((s.descriptors_deep + d * MB_DESC_STRIDE).bitcast[Int32]()[0])
        var expected: Int
        if roles[d] == _R_SPLITK_PARTIAL:
            expected = s.pipeline_idx_split
        elif roles[d] == _R_SPLITK_MERGE:
            expected = s.pipeline_idx_merge
        elif roles[d] == _R_EMBED:
            expected = s.pipeline_idx[0]
        elif roles[d] == _R_NORM_GEMV:
            expected = s.pipeline_idx[1]
        elif roles[d] == _R_GEMV_ACCUM:
            expected = s.pipeline_idx[2]
        elif roles[d] == _R_NORM_GEMV2_SWIGLU:
            expected = s.pipeline_idx[3]
        elif roles[d] == _R_QK_ROPE:
            expected = s.pipeline_idx[4]
        elif roles[d] == _R_LMHEAD_ARGMAX:
            expected = s.pipeline_idx[6]
        else:
            expected = s.pipeline_idx[7]
        if stored != expected:
            raise Error(
                "qwen3_probe_counters_i8_allsimd6_splitk_deepctx: slot " + String(d) + " role table says "
                + "pipeline " + String(expected) + " but the descriptor holds " + String(stored)
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
        raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: short read at byte offset " + String(byte_offset))
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
            "qwen3_probe_counters_i8_allsimd6_splitk_deepctx: metaldispatch call failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
        )


def _sample_at_position_deep(
    mut s: _MBQwen3I8AllSimd6,
    pos: Int,
    n_layers: Int,
    n_descriptors: Int,
    roles: List[Int],
    ns_per_tick: Float64,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
    mut role_avg_ms_out: List[Float64],
) raises -> Float64:
    """`qwen3_probe_counters_i8_allsimd6_deepctx.mojo`'s own `_sample_at_position`, retargeted at
    `s.descriptors_deep`/`s.pos_offsets_deep`/`s.nkeys_offsets_deep` and this file's `_N_ROLES_DEEP`-
    sized role table. `_mb_set_arg_int`'s arg index for `n_keys` is 6 here (`_splitk_partial_kernel_
    simd`'s own signature), not 4 (`_sdpa_kernel_simd`'s) — same reason `step()`'s own deep branch
    uses index 6."""
    var role_total_ns = List[Float64](capacity=_N_ROLES_DEEP)
    for _ in range(_N_ROLES_DEEP):
        role_total_ns.append(0.0)
    var n_keys = pos + 1
    _mb_set_arg_int(s.descriptors_deep, s.token_id_offset_deep, 3, 13)  # any valid vocab id
    for layer in range(n_layers):
        _mb_set_arg_int(s.descriptors_deep, s.pos_offsets_deep[layer], 8, pos)
        _mb_set_arg_int(s.descriptors_deep, s.nkeys_offsets_deep[layer], 6, n_keys)
    var wall_total_ms = 0.0
    for _ in range(N_SAMPLES):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors_deep, n_descriptors, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: algenta_run_token_counters failed")
        wall_total_ms += Float64(Int(t1 - t0)) / 1.0e6
        for d in range(n_descriptors):
            var start_tick = out_ticks[2 * d]
            var end_tick = out_ticks[2 * d + 1]
            if end_tick >= start_tick:
                role_total_ns[roles[d]] += Float64(end_tick - start_tick) * ns_per_tick
    for role in range(_N_ROLES_DEEP):
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
        raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))

    print("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: pos_shallow=", pos_shallow, "pos_deep=", pos_deep,
          "max_ctx=", max_ctx, "n_layers=", n_layers)

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 2, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: no accelerator on this host")
            return
        if pos_deep >= max_ctx:
            raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: pos_deep must be < max_ctx")

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _MBQwen3I8AllSimd6(
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

        # `s.descriptors_deep` is built lazily now -- this probe reaches into it directly (never
        # calls `step()`), so it must force that lazy init itself before touching the field. See the
        # module docstring above.
        s._ensure_deep_initialized()

        var roles = _build_role_table_deep(n_layers, s.n_descriptors_deep)
        _verify_role_table_deep(s, roles)
        print("  deep-table role table verified against", s.n_descriptors_deep, "descriptor slots (0 mismatches)")

        var supported = _mb_counters_supported()
        if supported != 1:
            print("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: counter sampling not available, status=", supported)
            return
        var ns_per_tick = _calibrate_gpu_tick_ns(200)
        print("  calibrated ns/tick:", ns_per_tick)
        var counters_rc = _mb_open_counters(2 * s.n_descriptors_deep)
        if counters_rc != 0:
            raise Error("qwen3_probe_counters_i8_allsimd6_splitk_deepctx: algenta_open_counters failed, rc=" + String(counters_rc))
        var out_ticks = alloc[UInt64](2 * s.n_descriptors_deep)

        print("")
        print("═══ sampling at pos_shallow=", pos_shallow, "(", N_SAMPLES, "reps, DEEP/split table) ═══")
        var shallow_roles = List[Float64](capacity=_N_ROLES_DEEP)
        for _ in range(_N_ROLES_DEEP):
            shallow_roles.append(0.0)
        var shallow_wall = _sample_at_position_deep(
            s, pos_shallow, n_layers, s.n_descriptors_deep, roles, ns_per_tick, out_ticks, shallow_roles
        )

        print("═══ sampling at pos_deep=   ", pos_deep, "(", N_SAMPLES, "reps, DEEP/split table) ═══")
        var deep_roles = List[Float64](capacity=_N_ROLES_DEEP)
        for _ in range(_N_ROLES_DEEP):
            deep_roles.append(0.0)
        var deep_wall = _sample_at_position_deep(
            s, pos_deep, n_layers, s.n_descriptors_deep, roles, ns_per_tick, out_ticks, deep_roles
        )

        print("")
        print("═══ per-role GPU dispatch time, summed over all", n_layers, "layers -- shallow vs deep (SPLIT/MERGE table) ═══")
        var shallow_total = 0.0
        var deep_total = 0.0
        for role in range(_N_ROLES_DEEP):
            shallow_total += shallow_roles[role]
            deep_total += deep_roles[role]
        for role in range(_N_ROLES_DEEP):
            var ratio = (deep_roles[role] / shallow_roles[role]) if shallow_roles[role] > 1.0e-9 else -1.0
            print("  ", _role_name(role), ": shallow=", shallow_roles[role], "ms  deep=", deep_roles[role],
                  "ms  deep/shallow ratio=", ratio)
        print("  TOTAL (sum of per-dispatch GPU time): shallow=", shallow_total, "ms  deep=", deep_total,
              "ms  ratio=", deep_total / shallow_total)
        print("")
        print("  whole-token wall time (host-measured, includes dispatch overhead + resolveCounterRange):")
        print("    shallow pos=", pos_shallow, ":", shallow_wall, "ms")
        print("    deep    pos=", pos_deep, ":", deep_wall, "ms")
