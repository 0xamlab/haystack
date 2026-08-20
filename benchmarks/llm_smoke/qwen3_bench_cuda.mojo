"""qwen3_bench_cuda.mojo — the CUDA-native session benchmarked, with the same methodology
discipline the GPU-matrix work uses: ONE resident session, one untimed warmup generation, then
three timed generations of the SAME race prompt + generation length (replayed on the same
session — every KV slot a replay reads is rewritten by the replay before it is read, so runs are
self-consistent), per-phase medians of three, and nvidia-smi clock evidence captured alongside
by the calling script.

Timed phases, stated precisely:
  * PREFILL tok/s = n_prompt / (time for the chunked batched prefill, which INCLUDES the
    lm_head + argmax that produces the first generated token).
  * DECODE tok/s  = gen / (time for `gen` decode steps AFTER prefill; each step is one
    per-dispatch-enqueue token, exactly the decode path `qwen3_generate_cuda.mojo` runs).

Generation length is a build-time selection — the pinned compiler's defines carry presence, not
values: default is 64; build with -D ALGENTA_GEN_256 for 256. Weights are read from the same
`/tmp/qwen3smoke/{manifest.json,weights.blob}` dump as every other arm.
"""

from std.math import sqrt
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import (
    RESIDENT_OK,
    residentk_dispatch_budget,
    residentk_status_name,
)
from residentk.session import _resident_preflight
from residentk.session_cuda import CUDA_PREFILL_TILE, CUDA_SESSION_BUILD, _CudaResidentQwen3

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"

comptime GEN_256: Bool = is_defined["ALGENTA_GEN_256"]()
comptime N_NEW_MAX: Int = 256 if GEN_256 else 64
comptime MAX_CTX: Int = 1024
comptime N_RUNS: Int = 3


def _check(status: Int, ok: Int, ctx: String) raises:
    if status != ok:
        raise Error("qwen3_bench_cuda: " + ctx + " failed, status=" + String(status))


def _check_resident(status: Int, ctx: String) raises:
    if status != RESIDENT_OK:
        raise Error(
            "qwen3_bench_cuda: " + ctx + " failed, status=" + String(status)
            + " (" + residentk_status_name(status) + ")"
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
        raise Error("qwen3_bench_cuda: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(byte_offset)
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_bench_cuda: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _ms(ns: Int) -> Float64:
    return Float64(ns) / 1.0e6


def _median3(a: Float64, b: Float64, c: Float64) -> Float64:
    var x = a
    var y = b
    var z = c
    if x > y:
        var t = x
        x = y
        y = t
    if y > z:
        var t = y
        y = z
        z = t
    if x > y:
        var t = x
        x = y
        y = t
    return y


@fieldwise_init
struct RunTimes(Copyable, Movable):
    var prefill_ms: Float64
    var decode_ms: Float64
    var first_token: Int


def run_generation(
    mut s: _CudaResidentQwen3, prompt_ids: List[Int], n_prompt: Int, n_layers: Int, timed: Bool
) raises -> RunTimes:
    """One full generation: batched prefill then N_NEW_MAX decode steps. `timed=False` is the
    warmup — same code path, numbers discarded."""
    var tp0 = perf_counter_ns()
    var pf = s.prefill(prompt_ids)
    var tp1 = perf_counter_ns()
    _check_resident(pf.status, "prefill")

    var last = pf.token_id
    var td0 = perf_counter_ns()
    for step in range(N_NEW_MAX):
        var pos = n_prompt + step
        var r = s.step(last, pos)
        _check_resident(r.status, "step(decode pos " + String(pos) + ")")
        if r.dispatches != residentk_dispatch_budget(n_layers):
            raise Error("qwen3_bench_cuda: dispatch budget disagreement")
        last = r.token_id
    var td1 = perf_counter_ns()

    return RunTimes(_ms(tp1 - tp0), _ms(td1 - td0), pf.token_id)


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
        raise Error("qwen3_bench_cuda: manifest config did not parse")

    var scale = 1.0 / sqrt(Float64(d_head))
    print("qwen3_bench_cuda: gen =", N_NEW_MAX, "| runs =", N_RUNS,
          "| prefill_tile =", CUDA_PREFILL_TILE, "| n_prompt =", n_prompt)

    var pre = _resident_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, N_NEW_MAX, MAX_CTX, eps, scale
    )
    if pre != RESIDENT_OK:
        print("qwen3_bench_cuda: cannot run here:", residentk_status_name(pre))
        return

    @parameter
    if not CUDA_SESSION_BUILD:
        print("qwen3_bench_cuda: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("qwen3_bench_cuda: no accelerator on this host")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        if len(prompt_ids) != n_prompt:
            raise Error("qwen3_bench_cuda: input_ids length does not match config.n_tokens")

        var tensors_obj = json_get_object(manifest, "tensors")

        # ═══ ONE-TIME weight cost (NOT part of any timed phase) ═══
        var tw0 = perf_counter_ns()
        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("  device:", s.device_name())
        var rt = rope_table(d_head, MAX_CTX, theta)
        _check(rt.status, ATTN_OK, "rope_table")
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check_resident(
            s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
            "upload_globals",
        )
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
            _check_resident(
                s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                "upload_layer " + String(layer),
            )
        _check_resident(s.seal(), "seal")
        var tw1 = perf_counter_ns()
        print("  ONE-TIME weight load + upload (untimed):", _ms(tw1 - tw0), "ms")

        # ═══ warmup: same code path, numbers discarded ═══
        var warm = run_generation(s, prompt_ids, n_prompt, n_layers, False)
        print("  warmup: prefill", warm.prefill_ms, "ms, decode", warm.decode_ms,
              "ms, first_token =", warm.first_token)

        # ═══ three timed runs ═══
        var p1 = run_generation(s, prompt_ids, n_prompt, n_layers, True)
        var p2 = run_generation(s, prompt_ids, n_prompt, n_layers, True)
        var p3 = run_generation(s, prompt_ids, n_prompt, n_layers, True)
        print("  run 1: prefill", p1.prefill_ms, "ms decode", p1.decode_ms, "ms")
        print("  run 2: prefill", p2.prefill_ms, "ms decode", p2.decode_ms, "ms")
        print("  run 3: prefill", p3.prefill_ms, "ms decode", p3.decode_ms, "ms")
        if p1.first_token != p2.first_token or p2.first_token != p3.first_token \
           or p1.first_token != warm.first_token:
            raise Error("qwen3_bench_cuda: runs disagree on the first generated token")
        print("  all runs agree on first generated token:", p1.first_token)

        var pf_med = _median3(p1.prefill_ms, p2.prefill_ms, p3.prefill_ms)
        var dc_med = _median3(p1.decode_ms, p2.decode_ms, p3.decode_ms)
        print("RESULT prefill_tok_per_s:", Float64(n_prompt) / (pf_med / 1000.0),
              "(median prefill", pf_med, "ms over", n_prompt, "prompt tokens)")
        print("RESULT decode_tok_per_s:", Float64(N_NEW_MAX) / (dc_med / 1000.0),
              "(median decode", dc_med, "ms over", N_NEW_MAX, "generated tokens)")
