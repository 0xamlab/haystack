"""graph_nsteps_probe.mojo — isolates whether the CUDA-graph decode path's per-token cost is
length-dependent on the L4. The L4 race showed gen64 = 1.82x over baseline but gen256 = 1.0x
(no benefit) — this probe calls seed_and_run_graph with a sweep of n_steps on ONE session and
reports per-token wall time for each, to tell whether the graph replay itself degrades with
generation length or the gen256 race number is an artifact.

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_89 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/graph_nsteps_probe.mojo -o probe
"""

from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from std.math import sqrt
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_OK, residentk_status_name
from residentk.session import _resident_preflight, _ceil_div
from residentk.session_cuda import CUDA_SESSION_BUILD, _CudaResidentQwen3

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"
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
        raise Error("graph_nsteps_probe: tensor not found: " + name)
    return TensorLoc(offset, n)


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    var f = open(blob_path, "r")
    _ = f.seek(loc.offset * 8)
    var raw = f.read_bytes(loc.n_elements * 8)
    f.close()
    var out = List[Float64](capacity=loc.n_elements)
    var fp = raw.unsafe_ptr().unsafe_bitcast[Float64]()
    for i in range(loc.n_elements):
        out.append(fp[i])
    return out^


def _check(status: Int, ok: Int, ctx_name: String) raises:
    if status != ok:
        raise Error("graph_nsteps_probe: " + ctx_name + " failed status=" + String(status))


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
    var scale = 1.0 / sqrt(Float64(d_head))

    @parameter
    if not CUDA_SESSION_BUILD:
        print("graph_nsteps_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("graph_nsteps_probe: no accelerator")
            return

        var ids_arr = json_get_array(manifest, "input_ids")
        var id_tokens = json_array_tokens(ids_arr)
        var prompt_ids = List[Int]()
        for i in range(len(id_tokens)):
            prompt_ids.append(parse_int(id_tokens[i]))
        var tensors_obj = json_get_object(manifest, "tensors")

        var s = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, MAX_CTX, eps, scale
        )
        print("graph_nsteps_probe: device:", s.device_name())
        var rt = rope_table(d_head, MAX_CTX, theta)
        _check(rt.status, ATTN_OK, "rope_table")
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check(s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, MAX_CTX),
               RESIDENT_OK, "upload_globals")
        for layer in range(n_layers):
            var pfx = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(BLOB_PATH, tensors_obj, pfx + "input_layernorm.weight")
            var ln2 = _load_tensor(BLOB_PATH, tensors_obj, pfx + "post_attention_layernorm.weight")
            var qn = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.q_norm.weight")
            var kn = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.k_norm.weight")
            var wq = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.q_proj.weight")
            var wk = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.k_proj.weight")
            var wv = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.v_proj.weight")
            var wo = _load_tensor(BLOB_PATH, tensors_obj, pfx + "self_attn.o_proj.weight")
            var wg = _load_tensor(BLOB_PATH, tensors_obj, pfx + "mlp.gate_proj.weight")
            var wu = _load_tensor(BLOB_PATH, tensors_obj, pfx + "mlp.up_proj.weight")
            var wd = _load_tensor(BLOB_PATH, tensors_obj, pfx + "mlp.down_proj.weight")
            _check(s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd),
                   RESIDENT_OK, "upload_layer")
        _check(s.seal(), RESIDENT_OK, "seal")

        # one untimed prefill to fill the KV cache + build the graph
        var pf = s.prefill(prompt_ids)
        _check(pf.status, RESIDENT_OK, "prefill")
        var warm = s.seed_and_run_graph(pf.token_id, n_prompt, 64)
        _check(warm, RESIDENT_OK, "warm graph")

        # sweep n_steps, timing the seeded graph run each time (re-prefill each trial so the
        # KV cache starts from the same state and each trial is independent)
        for trial in range(4):
            var n_steps = 0
            if trial == 0:
                n_steps = 32
            elif trial == 1:
                n_steps = 64
            elif trial == 2:
                n_steps = 128
            else:
                n_steps = 256
            var pf2 = s.prefill(prompt_ids)
            _check(pf2.status, RESIDENT_OK, "re-prefill")
            var t0 = perf_counter_ns()
            var st = s.seed_and_run_graph(pf2.token_id, n_prompt, n_steps)
            var t1 = perf_counter_ns()
            _check(st, RESIDENT_OK, "seed_and_run_graph")
            var ms = Float64(t1 - t0) / 1.0e6
            print("  n_steps =", n_steps, "| total", ms, "ms | per-token",
                  ms / Float64(n_steps), "ms |", Float64(n_steps) / (ms / 1000.0), "tok/s")

        print("graph_nsteps_probe: done")
