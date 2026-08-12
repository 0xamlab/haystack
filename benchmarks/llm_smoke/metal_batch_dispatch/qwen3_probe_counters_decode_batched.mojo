"""qwen3_probe_counters_decode_batched.mojo -- per-role GPU-counter breakdown of ONE Slipstream
BATCHED decode step (`_step_batched`'s descriptor table), built to find the limiter the first
3-way concurrent race (REALRACE_RESULTS.md "CONCURRENT AXIS, FIRST 3-WAY BATCHED RACE", 2026-08-12)
could only pin by subtraction: at B=32 the batched step takes ~59 ms of which the batched GEMMs
are ~1.1 ms (Phase-3 M-sweep proven), leaving ~57 ms unattributed; the per-step fit also showed a
~30 ms B-INDEPENDENT fixed cost this probe must either name or rule out. Same GPU-counter
methodology as `qwen3_probe_counters_i8_allsimd7_prefill_af_msl.mojo` (unmodified by this file):
per-dispatch hardware timestamps via `batch_shim_counters.m`'s compute-pass-attached sampling
(start+end sample per dispatch, one command buffer, no CPU sync between dispatches), tick rate
calibrated against wall time.

SAME descriptor path as production, verified not assumed: this probe dispatches the session's OWN
`descriptors_decode_batched` table -- built by the session's own `_ensure_decode_batched_ready(B)`,
the exact table `_step_batched` submits -- through `_mb_run_token_counters` instead of
`_mb_run_token`. The per-sequence state buffers (token ids / poss / n_keys) are filled with a
uniform synthetic depth (argv, default 300) -- the KV caches hold whatever the upload left there,
which changes NOTHING about timing (every kernel's work is shape-driven, value-independent).

Roles per step (1 + n_layers*9 + 3 descriptors): idx 0 = embed; per layer: rms1, qkv GEMM,
kvprod_batched, attn PARTIAL (batched split-K blob), attn MERGE, o_proj accum, rms2, swiglu,
down_proj accum; tail: final rmsnorm, batched lm_head, batched argmax reduce.

    argv[1] = B            (default 32)
    argv[2] = depth/poss   (default 300)
    argv[3] = timed samples (default 5)

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \\
        ../benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_counters_decode_batched.mojo \\
        -o /tmp/probe_db/probe_counters_decode_batched \\
        -Xlinker /tmp/probe_db/batch_shim_counters.o -Xlinker <blob .o set> \\
        -Xlinker -framework -Xlinker Metal -Xlinker -framework -Xlinker Foundation \\
        -Xlinker -framework -Xlinker IOKit
    /tmp/probe_db/probe_counters_decode_batched 32 300 5
"""

from std.sys import argv
from std.time import perf_counter_ns
from std.memory import alloc
from std.ffi import external_call
from std.math import sqrt
from json.parser import json_get_object, json_get_int, json_get_float
from conv import parse_int
from attnk.rope import rope_table
from metaldispatch.contract import MB_OK, metaldispatch_status_name
from metaldispatch.session import _mb_preflight, MB_GPU_BUILD
from metaldispatch.ffi import _mb_run_token
from metaldispatch.session_prefill import _MBQwen3I8AllSimd7Prefill
from metaldispatch.session_prefill_policy import (
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    UnresolvedPrefillConfig,
)
from metaldispatch.qwen3_prefill_decode import qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl

# The SDK's converted checkpoint (prepare_model_checkpoint output): manifest + f64 weights.blob +
# quantized-state cache. /tmp/qwen3smoke carries only the quantized cache on this machine.
comptime MANIFEST_PATH: String = "/private/tmp/qwen3-0.6b-base/.algenta-cache/manifest.json"
comptime BLOB_PATH: String = "/private/tmp/qwen3-0.6b-base/.algenta-cache/weights.blob"
comptime MAX_CTX: Int = 1024


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
        raise Error("probe_counters_decode_batched: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var remaining = n_elements
    alias CHUNK_ELEMS = 1 << 24
    while remaining > 0:
        var take = CHUNK_ELEMS if remaining > CHUNK_ELEMS else remaining
        var raw = f.read_bytes(take * 8)
        if len(raw) != take * 8:
            f.close()
            raise Error("probe_counters_decode_batched: short read at byte offset " + String(byte_offset))
        var fp = raw.unsafe_ptr().bitcast[Float64]()
        for i in range(take):
            out.append(fp[i])
        remaining -= take
    f.close()
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


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
        raise Error("probe_counters_decode_batched: GPU timestamp calibration did not advance")
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


comptime _N_LAYER_ROLES: Int = 9


def main() raises:
    var args = argv()
    # Keep the fresh-process entry reachable from main: AOT DCE otherwise drops the deep split-K
    # kernels `_ensure_deep_initialized` compiles, and the session constructor's discovery guard
    # raises (same discipline qwen3_resident_decode_race.mojo's own ep mode exists for).
    if len(args) > 1 and String(args[1]) == "ep":
        var r = qwen3_i8_allsimd7_prefill_decode_flat_af_nomirror_msl(
            "/tmp/qwen3smoke", 16, True, True, 2
        )
        print("ep status:", r.status)
        return
    var B = 32
    var depth = 300
    var n_samples = 5
    if len(args) > 1:
        B = parse_int(String(args[1]))
    if len(args) > 2:
        depth = parse_int(String(args[2]))
    if len(args) > 3:
        n_samples = parse_int(String(args[3]))

    if not MB_GPU_BUILD:
        raise Error("probe_counters_decode_batched: not a GPU build")
    if _mb_counters_supported() == 0:
        raise Error("probe_counters_decode_batched: counter sampling unsupported on this device")

    print("probe_counters_decode_batched: B =", B, " depth =", depth, " samples =", n_samples)

    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var eps = json_get_float(config, "rms_norm_eps", 1.0e-6)
    var theta = Float64(json_get_float(config, "rope_theta", 1000000.0))
    var scale = 1.0 / sqrt(Float64(d_head))

    var tensors_obj = json_get_object(manifest, "tensors")
    var s = _MBQwen3I8AllSimd7Prefill(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
    )
    s.resolve_plan(UnresolvedPrefillConfig(
        PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_MSL_PARITY_ALL_ROLES
    ))
    print("  resolved plan: attention =", s.plan.attention, " gemm =", s.plan.gemm)
    print("  decode_batched_built:", s.decode_batched_built)
    if not s.decode_batched_built:
        raise Error("probe_counters_decode_batched: batched pipelines not all discovered -- link the batched blobs")

    var rt = rope_table(d_head, MAX_CTX, theta)
    var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
    var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
    var up = s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX)
    if up != MB_OK:
        raise Error("probe_counters_decode_batched: upload_globals failed")
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
        var ls = s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd)
        if ls != MB_OK:
            raise Error("probe_counters_decode_batched: upload_layer failed: " + String(layer))
    _ = s.seal()
    print("  weights loaded + sealed")

    # Build the batched table exactly the way _step_batched's path does.
    s._ensure_decode_batched_ready(B)
    var n_desc = s.n_descriptors_decode_batched
    print("  descriptors_decode_batched:", n_desc, "(expected 1 + ", n_layers, "*9 + 3 =",
          1 + n_layers * 9 + 3, ")")

    # Synthetic uniform state: all B sequences at `depth`, appending one token.
    var ids32 = s.prompt_ids_ptr.bitcast[Int32]()
    var poss64 = s.batch_poss_ptr.bitcast[Int64]()
    var nkeys64 = s.batch_nkeys_ptr.bitcast[Int64]()
    for b in range(B):
        ids32[b] = Int32(374)
        poss64[b] = Int64(depth)
        nkeys64[b] = Int64(depth + 1)

    # Warm the table (untimed) -- pipelines first-dispatch + DVFS ramp, same convention as the
    # race harness's preconditioning.
    for _ in range(3):
        var rc = _mb_run_token(s.descriptors_decode_batched, n_desc)
        if rc != 0:
            raise Error("probe_counters_decode_batched: warm run failed rc=" + String(rc))

    var ns_per_tick = _calibrate_gpu_tick_ns(50)
    print("  calibrated ns/tick:", ns_per_tick)

    if _mb_open_counters(2 * n_desc + 16) != 0:
        raise Error("probe_counters_decode_batched: algenta_open_counters failed")
    var out_ticks = alloc[UInt64](2 * n_desc)

    # Per-dispatch duration samples: [sample][dispatch] ms.
    var wall_samples = List[Float64](capacity=n_samples)
    var disp_samples = List[List[Float64]](capacity=n_desc)
    for d in range(n_desc):
        disp_samples.append(List[Float64](capacity=n_samples))

    for samp in range(n_samples):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors_decode_batched, n_desc, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("probe_counters_decode_batched: run_token_counters failed rc=" + String(rc))
        wall_samples.append(Float64(Int(t1 - t0)) / 1.0e6)
        for d in range(n_desc):
            var start_tick = out_ticks[2 * d]
            var end_tick = out_ticks[2 * d + 1]
            var dur_ms = Float64(end_tick - start_tick) * ns_per_tick / 1.0e6
            disp_samples[d].append(dur_ms)

    var wall_med = _median(wall_samples)

    # Role buckets: 0 embed; per-layer base = 1 + 9*L; tail base = 1 + 9*n_layers.
    var role_names = List[String](capacity=12)
    role_names.append("embed")
    role_names.append("rms1")
    role_names.append("qkv_gemm")
    role_names.append("kvprod_batched")
    role_names.append("attn_PARTIAL")
    role_names.append("attn_merge")
    role_names.append("o_proj_accum")
    role_names.append("rms2")
    role_names.append("swiglu_gemm")
    role_names.append("down_proj_accum")
    role_names.append("rms_final")
    role_names.append("lmhead_batched")
    role_names.append("argmax_reduce")

    var role_sum = List[Float64](capacity=13)
    for r in range(13):
        role_sum.append(0.0)

    print("")
    print("per-dispatch median ms (first layer + tail):")
    for d in range(n_desc):
        var med = _median(disp_samples[d])
        var role = 0
        if d == 0:
            role = 0
        elif d < 1 + n_layers * 9:
            role = 1 + (d - 1) % 9
        else:
            role = 10 + (d - (1 + n_layers * 9))
        role_sum[role] = role_sum[role] + med
        if d <= 10 or d >= 1 + n_layers * 9:
            print("  d=", d, " role=", role_names[role], " median_ms=", med)

    var gpu_sum = 0.0
    print("")
    print("per-role totals (sum of per-dispatch medians across the step):")
    for r in range(13):
        gpu_sum = gpu_sum + role_sum[r]
        print("  ", role_names[r], ":", role_sum[r], "ms")

    print("")
    print("STEP SUMMARY (B =", B, ", depth =", depth, "):")
    print("  wall median:", wall_med, "ms")
    print("  GPU-sum:", gpu_sum, "ms")
    print("  gap (wall - GPU-sum):", wall_med - gpu_sum, "ms")
    print("  n_descriptors:", n_desc)
